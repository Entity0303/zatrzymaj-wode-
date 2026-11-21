"""Zgodność źródeł gleby i wybór kategorii do obliczeń (A5b-1, D49).

Trzy źródła mówią o tym samym (jak lekka jest gleba), każde inną skalą:
- mapa glebowo-rolnicza 1:5000 (GUGiK) – gatunek gleby (uziarnienie) z badań terenowych, kilka punktów w działce,
- mapa IUNG (katgl_landuse2024, 5 m) – kategoria podatności na suszę I–IV, uogólniona z map 1:25 000,
- SoilGrids (ISRIC, 250 m) – model globalny frakcji (klasa uziarnienia USDA).
Wspólna skala = kategorie agronomiczne gleb (PTG 1989), na których IUNG opiera kategorie podatności:
I bardzo lekka (piaski luźne i słabogliniaste), II lekka (piaski gliniaste), III średnia (gliny lekkie, pyły),
IV ciężka (gliny średnie i ciężkie, iły, pyły ilaste).

Kolejność ważności (D49): mapa glebowo-rolnicza (gdy jest kontur rolny) > IUNG > SoilGrids. Mapa (9 punktów)
i IUNG (komórki 5 m) dają UDZIAŁY w działce – konflikt, gdy udział gleb lekkich (I–II) różni się o > 40 p.p.
(działka na dwóch konturach to nie konflikt). Inne pary źródeł – konflikt, gdy różni się grupa dominującej
kategorii (lekka I–II vs średnia/ciężka III–IV). Przy konflikcie do modelu
wody bierzemy kategorię ze źródła ważniejszego (WOD = wartość typowa IUNG dla tej kategorii), pewność wyniku
niższa, krótkie wyjaśnienie dla rolnika. Gdy źródła są zgodne – WOD z IUNG (udziały komórek 5 m w całej
działce, spójne z metodyką IUNG SMSR). Las / woda / zabudowa – zawsze wg IUNG (aktualne użytkowanie 2024).
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from app.analysis.soil import CATEGORY_SHORT, CATEGORY_STATUS, SoilAssessment
from app.schemas.analysis import Indicator, SoilCategoryVote, SoilConsistency, SoilTexture, SourceTag
from app.sources.iung import REPRESENTATIVE_WOD_MM
from app.sources.soil_map import COMPLEXES, SoilMapResult, label as species_name

# gatunek z mapy glebowo-rolniczej -> kategoria agronomiczna (PTG 1989)
MAP_CATEGORY = {
    "pl": 1, "plp": 1, "ps": 1, "psp": 1, "ż": 1, "żp": 1,
    "pgl": 2, "pglp": 2, "pgm": 2, "pgmp": 2, "żg": 2,
    "gl": 3, "glp": 3, "płz": 3, "l": 3,
    "gs": 4, "gsp": 4, "gc": 4, "gcp": 4, "płi": 4, "i": 4, "ip": 4, "li": 4,
}
# klasa uziarnienia USDA (SoilGrids) -> kategoria (wg zawartości iłu i piasku)
USDA_CATEGORY = {
    "sand": 1, "loamy_sand": 1, "sandy_loam": 2, "loam": 3, "silt_loam": 3, "silt": 3,
    "sandy_clay_loam": 4, "clay_loam": 4, "silty_clay_loam": 4, "sandy_clay": 4, "silty_clay": 4, "clay": 4,
}
CAT_WORD = {1: "bardzo lekka", 2: "lekka", 3: "średnia", 4: "ciężka"}
CAT_ACC = {1: "bardzo lekką", 2: "lekką", 3: "średnią", 4: "ciężką"}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}
LABELS = {"mapa_glebowo_rolnicza": "Mapa glebowo-rolnicza 1:5000 (GUGiK)", "iung": "Mapa gleb IUNG-PIB",
          "soilgrids": "SoilGrids (ISRIC), model 250 m"}
IN_TEXT = {"mapa_glebowo_rolnicza": "mapa glebowo-rolnicza (GUGiK)", "iung": "mapa gleb IUNG",
           "soilgrids": "model SoilGrids (250 m)"}
LIGHT_SHARE_TOLERANCE = 0.4  # mapa vs IUNG: różnica udziału gleb lekkich (I–II) w działce > 40 p.p. = konflikt
_SPECIES_KEYS = sorted(MAP_CATEGORY, key=len, reverse=True)


def species_category(code: str | None) -> int | None:
    """Kategoria z kodu gatunku (bierze najdłuższy pasujący początek, np. 'pgl.ps' -> pgl)."""
    if not code:
        return None
    c = code.strip().lower()
    if c in MAP_CATEGORY:
        return MAP_CATEGORY[c]
    head = re.split(r"[^a-ząćęłńóśźż]", c)[0]
    return next((MAP_CATEGORY[k] for k in _SPECIES_KEYS if head == k), None)


def light(cat: int) -> bool:
    return cat <= 2


@dataclass
class MapSummary:
    category: int | None
    counts: dict[int, int]
    valid: int
    total: int
    representative: SoilMapResult | None  # kontur z dominującą kategorią (do opisu w `soil.soil_map`)
    by_category: dict[int, SoilMapResult] = field(default_factory=dict)  # przykładowy kontur każdej kategorii

    @property
    def light_share(self) -> float | None:
        n = sum(self.counts.values())
        return None if not n else sum(k for c, k in self.counts.items() if light(c)) / n


def summarize_map(results: list[SoilMapResult | None]) -> MapSummary:
    """Punkty z konturem rolnym (kompleks przydatności) i znanym gatunkiem -> rozkład kategorii."""
    cats: list[tuple[int, SoilMapResult]] = []
    for r in results:
        if r is None or (r.complex_code or "") not in COMPLEXES:
            continue
        c = species_category(r.species_code)
        if c is not None:
            cats.append((c, r))
    first = next((r for r in results if r is not None), None)
    if not cats:
        return MapSummary(None, {}, 0, len(results), first)
    counts = Counter(c for c, _ in cats)
    top = max(counts.values())
    dom = min(c for c, n in counts.items() if n == top)  # remis -> lżejsza (ostrożniej)
    by_cat: dict[int, SoilMapResult] = {}
    for c, r in cats:
        by_cat.setdefault(c, r)
    return MapSummary(dom, dict(counts), len(cats), len(results), by_cat[dom], by_cat)


def iung_light_share(soil: SoilAssessment) -> float | None:
    mineral = [s for s in soil.shares if s.code in (1, 2, 3, 4)]
    total = sum(s.share for s in mineral)
    return None if total <= 0 else sum(s.share for s in mineral if s.code <= 2) / total


@dataclass
class ConsistencyResult:
    contract: SoilConsistency | None
    conflict: bool = False
    category_used: int | None = None
    wod_used: float | None = None
    substituted: bool = False  # WOD / kategoria inne niż z IUNG


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def assess(soil: SoilAssessment, map_sum: MapSummary | None, tex: SoilTexture | None) -> ConsistencyResult:
    if soil.not_agricultural:
        return ConsistencyResult(None)
    votes: list[SoilCategoryVote] = []
    map_light = map_sum.light_share if map_sum else None
    if map_sum and map_sum.category:
        parts = []
        for c in sorted(map_sum.counts, key=lambda k: -map_sum.counts[k]):
            r = map_sum.by_category[c]
            name = species_name(r.species_code) or r.species_code
            pts = f" ({map_sum.counts[c]} z {map_sum.total} punktów)" if map_sum.total > 1 else ""
            parts.append(f"{name} – gleba {CAT_WORD[c]}{pts}")
        votes.append(SoilCategoryVote(source="mapa_glebowo_rolnicza", source_label=LABELS["mapa_glebowo_rolnicza"],
                                      category=map_sum.category, description="; ".join(parts)))
    iung_cat = soil.dominant_mineral
    iung_light = iung_light_share(soil)
    if iung_cat:
        mineral = [s for s in soil.shares if s.code in (1, 2, 3, 4)]
        desc = ", ".join(f"kat. {ROMAN[s.code]} {_pct(s.share)}" for s in sorted(mineral, key=lambda s: -s.share))
        votes.append(SoilCategoryVote(source="iung", source_label=LABELS["iung"], category=iung_cat,
                                      description=f"{desc} działki – {CATEGORY_SHORT[iung_cat].split('– ')[1]}"))
    sg_cat = USDA_CATEGORY.get(tex.texture_code) if tex else None
    if sg_cat:
        votes.append(SoilCategoryVote(source="soilgrids", source_label=LABELS["soilgrids"], category=sg_cat,
                                      description=f"{tex.texture_class} – gleba {CAT_WORD[sg_cat]}"))
    if not votes:
        return ConsistencyResult(None)

    basis, other = votes[0], (votes[1] if len(votes) > 1 else None)
    if basis.source == "mapa_glebowo_rolnicza" and other is not None and other.source == "iung" \
            and map_light is not None and iung_light is not None:
        # obie mapy dają udziały w działce – porównujemy udział gleb lekkich (I–II), nie tylko dominującą
        conflict = abs(map_light - iung_light) > LIGHT_SHARE_TOLERANCE
    else:
        conflict = other is not None and light(basis.category) != light(other.category)
    substituted = (conflict and basis.source != "iung") or soil.wod_mm is None
    if not substituted:  # źródła zgodne (albo rozstrzyga IUNG) – WOD z udziałów komórek IUNG w całej działce
        used, wod = iung_cat, soil.wod_mm
    elif basis.source == "mapa_glebowo_rolnicza" and map_sum:
        n = sum(map_sum.counts.values())
        used, wod = basis.category, round(sum(REPRESENTATIVE_WOD_MM[c] * k for c, k in map_sum.counts.items()) / n, 1)
    else:
        used, wod = basis.category, REPRESENTATIVE_WOD_MM[basis.category]

    two_soils = map_light is not None and 0 < map_light < 1
    if len(votes) == 1:
        note = f"Gleba tylko z jednego źródła ({IN_TEXT[basis.source]}) – nie było z czym porównać."
    elif conflict:
        why = ("dokładniejsza, wykonana na podstawie badań w terenie" if basis.source == "mapa_glebowo_rolnicza"
               else "dokładniejsza niż model globalny")
        third = votes[2] if len(votes) > 2 else None
        also = ""
        if third:
            agree = light(third.category) == light(basis.category)
            also = f" {IN_TEXT[third.source][0].upper() + IN_TEXT[third.source][1:]} {'też wskazuje' if agree else 'wskazuje'} glebę {CAT_ACC[third.category]}."
        note = (f"Źródła się różnią: {IN_TEXT[basis.source]} pokazuje {basis.description}, "
                f"a {IN_TEXT[other.source]} – {other.description}.{also} "
                f"Do obliczeń przyjęto {_acc(basis.source)} ({why}) – sprawdź glebę na polu; pewność wyniku niższa.")
    elif two_soils and other is not None and other.source == "iung":
        note = (f"Źródła zgodne: na działce są dwie gleby – według mapy glebowo-rolniczej lżejsza w "
                f"{_pct(map_light)} punktów, według mapy IUNG gleby lekkie (kat. I–II) to {_pct(iung_light)} działki. "
                f"W obliczeniach – średnia ważona dla całej działki (IUNG).")
    else:
        note = f"Źródła zgodne: {IN_TEXT[votes[0].source]} i {IN_TEXT[votes[1].source]} wskazują glebę {CAT_ACC[basis.category]}."
    if len(votes) > 2 and not conflict and light(votes[2].category) != light(basis.category):
        note += f" Model SoilGrids (250 m) wskazuje glebę {CAT_ACC[votes[2].category]} – jest najmniej dokładny, pominięty."
    if soil.wod_mm is None and substituted:
        note += f" Mapa IUNG niedostępna – kategorię gleby i WOD przyjęto z: {IN_TEXT[basis.source]}."
    contract = SoilConsistency(status="conflict" if conflict else "ok", note=note, basis=basis.source,
                               category_used=used, by_source=votes)
    return ConsistencyResult(contract, conflict, used, wod, substituted)


def _acc(source: str) -> str:
    return {"mapa_glebowo_rolnicza": "mapę glebowo-rolniczą", "iung": "mapę IUNG", "soilgrids": "model SoilGrids"}[source]


def apply(soil: SoilAssessment, c: ConsistencyResult) -> None:
    """Kategoria i WOD do modelu wody (zmienia `soil` w miejscu); wskaźnik `soil_capacity` z opisem źródła."""
    if c.contract is None or not c.substituted or c.wod_used is None:
        return
    basis = c.contract.basis
    soil.wod_mm = c.wod_used
    soil.dominant_mineral = c.category_used
    src = LABELS[basis]
    kind = "szacunek_modelu" if basis == "soilgrids" else "pomiar"
    soil.soil_capacity = Indicator(
        value=round(c.wod_used), unit="mm", label=CATEGORY_SHORT[c.category_used],
        status=CATEGORY_STATUS[c.category_used],
        note=f"woda dostępna dla roślin (WOD) – wartość typowa dla kat. {ROMAN[c.category_used]}; kategoria wg: {src}",
        source_tag=SourceTag(kind=kind, source=src),
    )
    if soil.method is None:  # IUNG nie odpowiedział – WOD z zastępczego źródła, nie „nie wiadomo”
        soil.limitations = [x for x in soil.limitations if "IUNG nie odpowiada" not in x]
        soil.limitations.append("Brak mapy gleb IUNG (usługa nie odpowiada) – pewność wyniku obniżona.")
    soil.limitations.append(
        f"Kategoria gleby i WOD w obliczeniach wg: {src} (kat. {ROMAN[c.category_used]}) – "
        + ("źródła gleby się różnią." if c.conflict else "mapa IUNG niedostępna.")
    )
