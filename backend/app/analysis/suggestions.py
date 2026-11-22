"""Ranking „Co tu posiać?” (A5b-2a): symulacja upraw z crops.csv na pogodzie 10 lat dla TEJ działki i gleby.

Dla każdej uprawy z `in_ranking`:
1. model wody w glebie FAO-56 (ten sam `run` co w analizie, parametry z crops.csv, WOD działki) dla każdego
   z 10 ostatnich PEŁNYCH sezonów (okno od 1 XI roku poprzedniego do typowego zbioru; bez nawadniania),
2. plon względny FAO-33 (Doorenbos i Kassam 1979): 1 − Ya/Ym = Ky · (1 − ETa/ETc); gdy są Ky faz –
   iloczyn po fazach Π (1 − Ky_f · (1 − ETa_f/ETc_f)),
3. plon potencjalny Ym = 90. percentyl plonów GUS w województwie działki (10 lat) × współczynnik gleby (D61),
4. typowy plon (mediana), plon w słabym roku (najgorszy + rok), ryzyko suszy (lata ze stratą > 20%),
5. płodozmian z historii upraw (twarda przerwa, złe / dobre przedplony, zboże po zbożu),
6. kategoria: polecane / możliwe / odradzane + jedno zdanie uzasadnienia z liczb (D62).
Uprawy wieloletnie – osobna grupa. Współczynniki i progi: rules/ranking.yaml.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml

from app.core.format import num
from app.analysis.crops import ALL_CROPS, CEREAL_GROUPS, RANKING_CROPS, Crop
from app.analysis.et0 import DailyWeather
from app.analysis.water_balance import (
    INIT_DAYS,
    MAX_MISSING_YEAR,
    _days,
    _idx,
    _observed,
    initial_state,
    last_usable_day,
    run,
    window_start,
)
from app.schemas.analysis import (
    CropSuggestion,
    CropSuggestions,
    CultivatedArea,
    PerennialSection,
    PerennialSuggestion,
    RotationCheck,
    SourceTag,
    SuggestionGroup,
    YearYield,
)

DATA = Path(__file__).parents[1] / "data" / "crops"
RULES = Path(__file__).parent / "rules" / "ranking.yaml"
GUS_SOURCE = "GUS BDL – plony z 1 ha wg województw"
MODEL_SOURCE = "Model wody w glebie FAO-56 + plon FAO-33"
SEASON_PHASES = ("poczatkowa", "rozwoj", "pelnia", "dojrzewanie")
PERENNIAL_NOTE = "Uprawa wieloletnia – decyzja na wiele lat; plon dotyczy plantacji w pełni owocowania."
PERENNIAL_LABEL = "Uprawy wieloletnie – inwestycja na lata"
PERENNIAL_SECTION_NOTE = ("Sady, krzewy i truskawki wymagają osobnej analizy opłacalności (nakłady, rynek, nawadnianie) – "
                          "nie oceniamy ich jak upraw polowych; liczby to tylko orientacja.")
CATEGORY_LABEL = {"polecane": "polecane", "mozliwe": "możliwe", "odradzane": "odradzane"}
# A15: zboża na glebie kat. I–IV z wodą ≥ 150 mm nigdy nie dostają „nie siej – gleba nie pasuje” (najwyżej „możliwe”
# z powodem ekonomicznym); kompleks z mapy glebowo-rolniczej może być słabszy niż ocena IUNG – zdanie mówi to wprost
CEREALS = frozenset({"pszenica_ozima", "zyto", "pszenzyto_ozime", "owies", "jeczmien_ozimy", "jeczmien_jary"})
CEREAL_GOOD_SOIL_WOD_MM = 150.0
COMPLEX_NAME = {
    "1": "pszenny bardzo dobry", "2": "pszenny dobry", "3": "pszenny wadliwy", "4": "żytni bardzo dobry",
    "5": "żytni dobry", "6": "żytni słaby", "7": "żytni bardzo słaby", "8": "zbożowo-pastewny mocny",
    "9": "zbożowo-pastewny słaby", "10": "pszenny górski", "11": "zbożowy górski", "12": "owsiano-ziemniaczany górski",
    "13": "owsiano-pastewny górski", "14": "gleby orne przeznaczone pod użytki zielone",
}
# która uprawa lepiej się opłaca na kompleksie „złym” dla zboża (powód ekonomiczny w zdaniu)
COMPLEX_BETTER = {"5": "żyto lub pszenżyto", "6": "żyto", "7": "żyto", "8": "pszenica lub rzepak",
                  "9": "owies lub pszenżyto"}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

SUIT_LABEL = {"odpowiednia": "gleba odpowiednia", "neutralna": "gleba przeciętna dla tej uprawy",
              "nieodpowiednia": "gleba nieodpowiednia"}
# powód przerwy w uprawie po sobie (zalecenia agrotechniczne; README danych osoby C + decyzja D63)
BREAK_REASON = {"rzepak": "kiła kapusty", "owies": "mątwik owsiany", "lubin": "choroby odglebowe łubinu",
                "straczkowe": "choroby odglebowe", "ziemniak": "mątwik ziemniaczany i choroby",
                "burak_cukrowy": "mątwik burakowy"}
SAME_FAMILY = [{"rzepak", "rzepak_jesien"}]
YIELD_NOTE = {"kukurydza_kiszonka": "plon zielonej masy", "burak_cukrowy": "plon korzeni"}
GUS_SUBSTITUTE = {"lubin": "plon roślin strączkowych razem (łubinu nie ma w GUS BDL)",
                  "jeczmien_ozimy": "plon jęczmienia ogółem", "jeczmien_jary": "plon jęczmienia ogółem"}
HISTORY_UNKNOWN = "nie_wiem"
# Ky faz potwierdzone w tabeli FAO-33 (README danych C): pszenica, ziemniak, fasola. Dla kukurydzy i zbóż jarych
# Ky faz to szacunek – liczymy Ky sezonowym (D61).
KY_PHASES_VERIFIED = {"zboza_ozime", "pszenica_ozima", "ziemniak", "straczkowe"}
# Gleba odniesienia do kalibracji (D61): WOD 167,5 mm = środek między kat. II i III IUNG („przeciętna gleba”).
REFERENCE_WOD_MM = 167.5


@lru_cache
def config() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["ranking"]


@lru_cache
def gus_yields() -> dict[tuple[str, str], dict[int, float]]:
    """(crop_id, województwo małymi literami) → {rok: plon t/ha}; klucz (crop_id, '') = wszystkie województwa."""
    out: dict[tuple[str, str], dict[int, float]] = {}
    with open(DATA / "gus_yields_woj.csv", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                v = float(r["plon_dt_ha"]) / 10.0
            except ValueError:
                continue
            out.setdefault((r["crop_id"], r["woj_nazwa"].strip().lower()), {})[int(r["rok"])] = v
    return out


@dataclass
class Potential:
    ym_t_ha: float | None  # percentyl GUS (bez współczynnika gleby)
    mean_t_ha: float | None
    years: int
    scope: str  # "wojewodztwo" | "kraj" | "brak"


def potential(crop_id: str, voivodeship: str | None) -> Potential:
    data = gus_yields()
    vals = list((data.get((crop_id, (voivodeship or "").strip().lower())) or {}).values())
    scope = "wojewodztwo"
    if len(vals) < 3:  # brak danych dla województwa (np. uprawa lokalna) – wszystkie województwa
        vals = [v for (c, _w), d in data.items() if c == crop_id for v in d.values()]
        scope = "kraj" if vals else "brak"
    if not vals:
        return Potential(None, None, 0, "brak")
    adjust = float(config().get("ym_adjust", {}).get(crop_id, 1.0))  # A7 (D84): korekta progu Ym po zmianie opadu
    return Potential(float(np.percentile(vals, config()["gus_percentile"])) * adjust, float(np.mean(vals)), len(vals),
                     scope)


# ── symulacja ───────────────────────────────────────────────────────────────────────────────


def relative_yield(crop: Crop, phases: list[str], eta: np.ndarray, etc: np.ndarray) -> float | None:
    """Ya/Ym z ETa i ETc dni sezonu (fazy uprawy). Z Ky faz – iloczyn po fazach, inaczej Ky sezonowe."""
    ph = np.array(phases)
    season = np.isin(ph, SEASON_PHASES)
    if not season.any() or etc[season].sum() <= 0:
        return None
    if crop.ky_phases and crop.id in KY_PHASES_VERIFIED:
        rel = 1.0
        for name, ky in crop.ky_phases.items():
            m = ph == name
            tot = etc[m].sum()
            if tot > 0:
                rel *= max(0.0, 1.0 - ky * (1.0 - eta[m].sum() / tot))
    else:
        rel = 1.0 - crop.ky_total * (1.0 - eta[season].sum() / etc[season].sum())
    return float(min(1.0, max(0.0, rel)))


def last_full_season(crop: Crop, last: date) -> int:
    """Rok ostatniego sezonu zakończonego (typowy zbiór) nie później niż `last`."""
    return last.year if date(last.year, *crop.harvest) <= last else last.year - 1


_sim_memo: dict[tuple, list[tuple[int, float, float]]] = {}


def simulate(w: DailyWeather, crop: Crop, wod_mm: float, last: date, years: int = 10) -> list[tuple[int, float, float]]:
    """[(rok sezonu, plon względny Ya/Ym, niedobór wody ETc − ETa w sezonie [mm])] dla ≤ `years` pełnych sezonów."""
    y_last = last_full_season(crop, last)
    key = (crop.id, w.source, round(w.lat, 2), round(w.lon, 2), str(w.dates[0]), len(w.dates), round(wod_mm, 1),
           y_last, years)
    if key in _sim_memo:
        return _sim_memo[key]
    out = []
    for y in range(y_last - years + 1, y_last + 1):
        ws, harvest = window_start(crop, y), date(y, *crop.harvest)
        obs = _observed(w, ws, harvest)
        if obs is None or _idx(w, ws) - INIT_DAYS < 0 or np.isnan(obs[0] + obs[1]).mean() > MAX_MISSING_YEAR:
            continue
        st, _bal = initial_state(w, crop, wod_mm, ws)
        tr = run(crop, wod_mm, _days(ws, harvest), obs[0], obs[1], st)
        rel = relative_yield(crop, tr.phase, tr.eta, tr.etc)
        if rel is None:
            continue
        season = np.isin(np.array(tr.phase), SEASON_PHASES)
        out.append((y, rel, float((tr.etc[season] - tr.eta[season]).sum())))
    if len(_sim_memo) > 2000:
        _sim_memo.clear()
    _sim_memo[key] = out
    return out


def reference_level(w: DailyWeather, crop: Crop, last: date, years: int = 10) -> float:
    """Kalibracja (D61): plon względny modelu w DOBRYM roku (90. percentyl z 10 sezonów) na przeciętnej glebie
    (WOD 167,5 mm) w tej samej pogodzie. Temu poziomowi odpowiada 90. percentyl plonów GUS w województwie –
    „zwykły” niedobór wody uprawy (np. ziemniaka o płytkich korzeniach) jest już w plonach GUS."""
    ref = [r for _y, r, _d in simulate(w, crop, REFERENCE_WOD_MM, last, years)]
    if not ref:
        return 1.0
    return float(max(0.3, np.percentile(ref, config()["gus_percentile"])))


# ── gleba ───────────────────────────────────────────────────────────────────────────────────


def soil_suitability(crop: Crop, category: int | None, complex_code: str | None) -> str:
    """odpowiednia / neutralna / nieodpowiednia. Znany kompleks przydatności (mapa glebowo-rolnicza 1:5000, badania
    terenowe) decyduje sam – jak w kolejności źródeł gleby D49; kategoria IUNG – gdy kompleksu nie ma (D70)."""
    k = (complex_code or "").strip()
    if k.isdigit():  # kompleksy gruntów ornych 1–14
        if k in crop.soils_bad_complex:
            return "nieodpowiednia"
        return "odpowiednia" if k in crop.soils_ok_complex else "neutralna"
    if category is not None and category in crop.soils_bad_iung:
        return "nieodpowiednia"
    if category is not None and category in crop.soils_ok_iung:
        return "odpowiednia"
    return "neutralna"


# ── płodozmian ──────────────────────────────────────────────────────────────────────────────


def parse_history(text: str | None) -> list[str]:
    """'rzepak,nie_wiem,zyto' → lista 1–3 pozycji (indeks 0 = rok temu). Nieznany identyfikator → ValueError."""
    if not text or not text.strip():
        return []
    items = [x.strip() for x in text.split(",")][:3]
    for x in items:
        if x and x != HISTORY_UNKNOWN and x not in ALL_CROPS:
            raise ValueError(x)
    return [x or HISTORY_UNKNOWN for x in items]


def _same(a: str, b: str) -> bool:
    return a == b or any(a in fam and b in fam for fam in SAME_FAMILY)


def _is_cereal(crop_id: str) -> bool:
    c = ALL_CROPS.get(crop_id)
    return bool(c and c.group_id in CEREAL_GROUPS)


def _ago(k: int) -> str:
    return "rok temu" if k == 1 else f"{k} lata temu"


def _years(n: int) -> str:
    return "1 roku" if n == 1 else f"{n} lat"


def years_break(n: int) -> str:
    """„rok” / „2 lata” / „5 lat” – do „lepiej zrobić … przerwy”."""
    if n <= 1:
        return "rok"
    return f"{n} lata" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else f"{n} lat"


def grew(crop_id: str) -> str:
    """„rosła” / „rósł” / „rosło” / „rosły” – wg rodzaju nazwy uprawy (rules/verdict.yaml: gender)."""
    from app.analysis import verdict as verdict_mod

    g = verdict_mod.cfg().get("gender", {}).get(crop_id, "pl")
    return {"f": "rosła", "m": "rósł", "n": "rosło"}.get(g, "rosły")


def rotation(crop: Crop, history: list[str]) -> RotationCheck:
    known = [(k + 1, h) for k, h in enumerate(history) if h != HISTORY_UNKNOWN]
    if not known:
        return RotationCheck(status="brak_historii", notes=[])
    notes: list[str] = []
    status = "ok"
    for k, h in known:  # twarda reguła: ta sama uprawa przed upływem min. przerwy
        if _same(h, crop.id) and k <= crop.min_break_years:
            why = BREAK_REASON.get(crop.id) or BREAK_REASON.get(crop.group_id)
            notes.append(f"{crop.label} {grew(crop.id)} tu {_ago(k)} – po sobie częściej chorują"
                         + (f" ({why})" if why else "") + f", lepiej zrobić {years_break(crop.min_break_years)} przerwy.")
            return RotationCheck(status="naruszenie", notes=notes)
    last = history[0]
    if last != HISTORY_UNKNOWN:
        prev = ALL_CROPS[last]
        good_txt = (f"Dobry przedplon – rok temu {grew(last)} tu {prev.label.lower()}"
                    + (" (owies przerywa choroby zbóż)" if last == "owies" and _is_cereal(crop.id) else "") + ".")
        bad_txt = (f"Słaby przedplon – rok temu {grew(last)} tu {prev.label.lower()}; więcej chorób i szkodników, "
                   "niższy plon.")
        if _same(last, crop.id) and crop.min_break_years == 0:
            notes.append(f"{crop.label} znosi uprawę po sobie – przerwa nie jest konieczna.")  # A5e-2: bez zmian
        elif last in crop.good_previous:  # dokładny gatunek ma pierwszeństwo przed grupą (owies przed pszenicą)
            status = "plus"
            notes.append(good_txt)
        elif last in crop.bad_previous or prev.group_id in crop.bad_previous:
            status = "ostrzezenie"
            notes.append(bad_txt)
        elif _is_cereal(last) and _is_cereal(crop.id):
            status = "ostrzezenie"
            notes.append("Zboże po zbożu – więcej chorób i niższy plon; można, ale lepiej zmienić uprawę.")
        elif prev.group_id in crop.good_previous:
            status = "plus"
            notes.append(good_txt)
    return RotationCheck(status=status, notes=notes)


# ── ocena i zdanie ──────────────────────────────────────────────────────────────────────────


def _n(v: float, nd: int = 1) -> str:
    return num(v, nd)


def category(suit: str, risk: int, median_rel: float, rot: RotationCheck) -> str:
    c = config()
    if rot.status == "naruszenie" or suit == "nieodpowiednia":
        return "odradzane"
    if suit != "odpowiednia" and (risk >= c["discouraged"]["min_risk_years"]
                                  or median_rel < c["discouraged"]["max_median_relative"]):
        return "odradzane"
    if (suit == "odpowiednia" and risk <= c["recommended"]["max_risk_years"]
            and median_rel >= c["recommended"]["min_median_relative"]):
        return "polecane"
    return "mozliwe"


def reason(crop: Crop, cat: str, suit: str, risk: int, n: int, typ: float | None, weak: float | None, weak_year: int,
           worst_loss_pct: int, rot: RotationCheck, light_soil: bool, soil_txt: str,
           complex_code: str | None = None, category_iung: int | None = None, cereal_override: bool = False) -> str:
    """JEDNO zdanie prostym językiem – wyłącznie z policzonych liczb; powód zgodny z opisem gleby (A15)."""
    name = crop.label.lower()
    yld = f"typowo {_n(typ)} t/ha" if typ is not None else "plon bez danych GUS"
    k = (complex_code or "").strip()
    kname = COMPLEX_NAME.get(k)
    if rot.status == "naruszenie":
        return rot.notes[0]
    if cereal_override and cat == "mozliwe":  # A15: zboże na dobrej glebie, kompleks z mapy słabszy dla tej uprawy
        better = COMPLEX_BETTER.get(k, "pszenica lub rzepak")
        return (f"Da się uprawiać – {yld}; mapa glebowo-rolnicza podaje tu kompleks „{kname}”, słabszy dla tej uprawy niż "
                f"wskazuje gleba ({soil_txt}), więc lepiej opłaca się {better}.")
    if suit == "nieodpowiednia" and kname and k in crop.soils_bad_complex and not light_soil:
        iung = (f" (mapa IUNG ocenia glebę lepiej – kat. {ROMAN[category_iung]})"
                if category_iung is not None and category_iung >= 3 else "")
        return (f"Mapa glebowo-rolnicza podaje tu kompleks „{kname}” – {name} plonuje na nim wyraźnie słabiej niż zwykle w "
                f"okolicy{iung}.")
    if suit == "nieodpowiednia":
        if light_soil and risk > 0:
            return (f"Słaba, lekka ziemia trzyma mało wody – {name}: w {risk} z {n} lat strata ponad 20% plonu "
                    f"({soil_txt}).")
        if light_soil:
            return f"Słaba, lekka ziemia ({soil_txt}) nie nadaje się pod tę uprawę – plon będzie dużo niższy niż zwykle."
        return f"Ta gleba ({soil_txt}) nie pasuje do tej uprawy – plon będzie wyraźnie niższy niż zwykle w okolicy."
    if cat == "odradzane":
        return (f"Za mało wody dla tej uprawy: w {risk} z {n} lat susza zabrałaby ponad 20% plonu, w najgorszym roku "
                f"({weak_year}) {worst_loss_pct}%.")
    if cat == "polecane":
        if risk == 0:
            return (f"Gleba pasuje i wody wystarcza – {yld}, a nawet w najsuchszym roku ({weak_year}) plon spadłby "
                    f"tylko o {worst_loss_pct}%.")
        return (f"Gleba pasuje – {yld}; strata ponad 20% plonu zdarzyłaby się w {risk} z {n} lat "
                f"(najgorszy rok: {weak_year}).")
    if suit == "odpowiednia":
        return (f"Gleba pasuje, ale wody bywa za mało – {yld}, strata ponad 20% plonu w {risk} z {n} lat "
                f"(najgorszy rok: {weak_year}).")
    tail = (f"strata ponad 20% plonu w {risk} z {n} lat" if risk else
            f"w najsuchszym roku ({weak_year}) plon niższy o {worst_loss_pct}%")
    return f"Da się uprawiać, choć ta gleba nie jest dla tej uprawy najlepsza – {yld}, {tail}."


@dataclass
class Context:
    wod_mm: float
    category: int | None  # kategoria gleby użyta w modelu (I–IV)
    complex_code: str | None  # kompleks przydatności rolniczej (mapa glebowo-rolnicza)
    voivodeship: str | None
    area_ha: float
    area_estimated: bool
    area_note: str
    history: list[str] = field(default_factory=list)
    soil_txt: str = "gleba"
    soil_group: str | None = None  # etykieta ważona (analysis/soil_label.py); None – z kategorii / kompleksu


def build(w: DailyWeather, analysis_date: date, ctx: Context, years: int = 10) -> CropSuggestions | None:
    t0 = perf_counter()
    cfg = config()
    last = last_usable_day(analysis_date)
    light_soil = (ctx.soil_group == "lekka" if ctx.soil_group not in (None, "nieznana")
                  else ctx.category in (1, 2) or (ctx.complex_code or "") in ("6", "7"))
    groups: dict[str, list[CropSuggestion]] = {"polowe": [], "wieloletnie": []}
    seasons: set[int] = set()
    for crop in RANKING_CROPS:
        raw = simulate(w, crop, ctx.wod_mm, last, years)
        if len(raw) < cfg["min_seasons"]:
            continue
        ref = reference_level(w, crop, last, years)
        sim = [(y, min(1.0, r / ref), d) for y, r, d in raw]  # plon względem dobrego roku na przeciętnej glebie
        rels = np.array([r for _y, r, _d in sim])
        seasons |= {y for y, _r, _d in sim}
        n = len(sim)
        median_rel = float(np.median(rels))
        k_min = int(rels.argmin())
        weak_year, weak_rel = sim[k_min][0], float(rels[k_min])
        risk = int((rels < 1.0 - cfg["loss_threshold"]).sum())
        suit = soil_suitability(crop, ctx.category, ctx.complex_code)
        cereal_override = (suit == "nieodpowiednia" and crop.id in CEREALS and ctx.category in (1, 2, 3, 4)
                           and ctx.wod_mm >= CEREAL_GOOD_SOIL_WOD_MM)
        if cereal_override:  # A15: nie „nie siej – gleba nie pasuje”, najwyżej „możliwe” (powód ekonomiczny)
            suit = "neutralna"
        pot = potential(crop.id, ctx.voivodeship)
        ym = None if pot.ym_t_ha is None else pot.ym_t_ha * cfg["soil_factor"][suit]
        typ = None if ym is None else ym * median_rel
        weak = None if ym is None else ym * weak_rel
        rot = rotation(crop, ctx.history)
        cat = category(suit, risk, median_rel, rot)
        if cereal_override and cat == "polecane":
            cat = "mozliwe"
        sc = cfg["score"]
        score = (100 * median_rel - sc["risk_year_penalty"] * risk * 10 / n + sc["soil_bonus"][suit]
                 + (sc["rotation_plus"] if rot.status == "plus" else sc["rotation_warning"] if rot.status == "ostrzezenie" else 0))
        low = []
        if crop.estimated:
            low.append("współczynnik Ky (reakcja plonu na brak wody) to szacunek")
        if crop.id in GUS_SUBSTITUTE:
            low.append(f"plon potencjalny: {GUS_SUBSTITUTE[crop.id]}")
        if pot.scope != "wojewodztwo" or pot.years < 8:
            low.append("krótka albo niepełna seria plonów GUS dla województwa")
        if n < 8:
            low.append(f"tylko {n} pełnych sezonów z danymi pogodowymi")
        notes = ([PERENNIAL_NOTE] if crop.kind == "wieloletnia" else []) + \
                ([YIELD_NOTE[crop.id].capitalize() + "."] if crop.id in YIELD_NOTE else [])
        item = CropSuggestion(
            crop_id=crop.id, label=crop.label, group_id=crop.group_id, category=cat, category_label=CATEGORY_LABEL[cat],
            rank=0, score=round(score, 1),
            reason=reason(crop, cat, suit, risk, n, typ, weak, weak_year, round(100 * (1 - weak_rel)), rot, light_soil,
                          ctx.soil_txt, ctx.complex_code, ctx.category, cereal_override),
            yield_typical_t_ha=None if typ is None else round(typ, 1),
            yield_weak_t_ha=None if weak is None else round(weak, 1), weak_year=weak_year,
            yield_potential_t_ha=None if ym is None else round(ym, 1),
            gus_mean_t_ha=None if pot.mean_t_ha is None else round(pot.mean_t_ha, 1),
            relative_yield_median=round(median_rel, 2), relative_yield_weak=round(weak_rel, 2),
            drought_risk_years=risk, years_simulated=n,
            total_typical_t=None if typ is None else round(typ * ctx.area_ha, 1),
            total_weak_t=None if weak is None else round(weak * ctx.area_ha, 1), price=None,
            soil_suitability=suit, soil_suitability_label=SUIT_LABEL[suit], rotation=rot,
            irrigation_practice=crop.irrigation_practice, drought_sensitivity=crop.sensitivity,
            confidence="ograniczona" if low else "srednia", confidence_note="; ".join(low) or None, notes=notes,
            yields_by_year=[YearYield(year=y, relative=round(r, 2), yield_t_ha=None if ym is None else round(ym * r, 1),
                                      water_deficit_mm=round(d)) for y, r, d in sim],
            source_tags=[
                SourceTag(kind="szacunek_modelu", date=last, source=f"{MODEL_SOURCE} (Ky {_n(crop.ky_total, 2)})"),
                SourceTag(kind="pomiar" if pot.scope == "wojewodztwo" else "brak_danych" if pot.scope == "brak" else "obliczenia",
                          source=f"{GUS_SOURCE}" + (f" ({ctx.voivodeship}, 2016–2025)" if pot.scope == "wojewodztwo"
                                                    else " (wszystkie województwa)" if pot.scope == "kraj" else "")),
            ],
        )
        groups["wieloletnie" if crop.kind == "wieloletnia" else "polowe"].append(item)
    order = {"polecane": 0, "mozliwe": 1, "odradzane": 2}
    perennials = None
    if groups["wieloletnie"]:  # D67: bez kategorii, osobna sekcja, niska pewność, poza werdyktem
        per = sorted(groups["wieloletnie"], key=lambda i: -i.score)
        perennials = PerennialSection(label=PERENNIAL_LABEL, note=PERENNIAL_SECTION_NOTE, items=[PerennialSuggestion(
            crop_id=i.crop_id, label=i.label, yield_typical_t_ha=i.yield_typical_t_ha, yield_weak_t_ha=i.yield_weak_t_ha,
            weak_year=i.weak_year, drought_risk_years=i.drought_risk_years, years_simulated=i.years_simulated,
            total_typical_t=i.total_typical_t, total_weak_t=i.total_weak_t, soil_suitability=i.soil_suitability,
            soil_suitability_label=i.soil_suitability_label, irrigation_practice=i.irrigation_practice,
            confidence="ograniczona",
            note=f"{i.soil_suitability_label.capitalize()}; strata ponad 20% plonu w {i.drought_risk_years} na "
                 f"{i.years_simulated} lat. Wymaga osobnej analizy opłacalności.",
            source_tags=i.source_tags) for i in per])
    out_groups = []
    for key, label in (("polowe", "uprawy polowe"),):
        items = sorted(groups[key], key=lambda i: (order[i.category], -i.score))
        items = [i.model_copy(update={"rank": k + 1}) for k, i in enumerate(items)]
        if items:
            out_groups.append(SuggestionGroup(key=key, label=label, items=items))
    if not out_groups:  # za mało pełnych sezonów z pogodą – brak rankingu (null), nie pusta lista
        return None
    has_history = any(h != HISTORY_UNKNOWN for h in ctx.history)
    return CropSuggestions(
        seasons=sorted(seasons), groups=out_groups, perennials=perennials,
        area=CultivatedArea(value_ha=round(ctx.area_ha, 2), estimated=ctx.area_estimated, note=ctx.area_note),
        crop_history=ctx.history,
        rotation_hint=None if has_history else "Podaj, co rosło w ostatnich latach – uwzględnimy płodozmian.",
        note="Plony bez nawadniania. Symulacja na pogodzie z ostatnich 10 sezonów dla tej działki i tej gleby; "
             "nie uwzględnia nawożenia, odmiany, chorób ani cen.",
        limitations=[
            "Plon potencjalny z plonów GUS w województwie (90. percentyl z 10 lat) i szacunkowego współczynnika "
            "przydatności gleby – to rząd wielkości, nie prognoza.",
            "Spadek plonu przy suszy liczymy metodą FAO, inną dla każdej uprawy (FAO-33, współczynnik Ky); dla części upraw "
            "to szacunek – oznaczone niższą pewnością.",
            "Wymagania glebowe i płodozmian – ogólne zalecenia agrotechniczne (szacunek, do weryfikacji z doradcą).",
        ],
        compute_ms=int((perf_counter() - t0) * 1000),
        source_tag=SourceTag(kind="szacunek_modelu", date=last, source=f"{MODEL_SOURCE}; {GUS_SOURCE}"),
    )
