"""Uprawy: 15 upraw IUNG SMSR z parametrami do modelu wody w glebie FAO-56 i kalendarzem w Polsce.

Identyfikatory = kontrakt (schemas/analysis.py CropId = frontend/src/lib/crops.ts).

Źródła (Allen i in., 1998, FAO Irrigation and Drainage Paper 56):
- Kc ini / mid / end – tab. 12 („single crop coefficients”), bez korekty klimatycznej (D24),
- proporcje faz (ini / dev / mid / late) – tab. 11; długości PRZESKALOWANE do okresu
  start → typowy zbiór w Polsce (D23, D31),
- maks. głębokość korzeni Zr i frakcja p – tab. 22.
Terminy: start (siew / wznowienie wegetacji) i zbiór – typowy kalendarz w Polsce (A3, A3b, D31).
„ZAŁOŻENIE” = brak w tabelach FAO-56 lub w zadaniu, wartość przez analogię (D23).

Kalendarz dnia (`day_info`) obejmuje cały rok: przed siewem i po zbiorze – goła gleba
(parowanie z gołej gleby, D30); ozime – wschody jesienne i spoczynek zimowy; wieloletnie –
spoczynek zimowy poza 1 IV–31 X. Korzenie rosną liniowo od startu do końca fazy rozwoju (D30).
"""

import csv
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

ZE_M = 0.12  # warstwa parowania gołej gleby / korzenie po siewie (FAO-56 rozdz. 7: Ze 0,10–0,15 m)
ZR_DORMANT_M = 0.30  # korzenie ozimin przed zimą (ZAŁOŻENIE, D30)
KC_DORMANT = 0.40  # spoczynek zimowy: FAO-56 tab. 12, pszenica ozima „with frozen soils” Kc 0,4
KC_BARE = 0.35  # goła gleba (FAO-56 rys. 29 dla rzadkiego zwilżania: 0,3–0,4; D30)

PHASE_LABELS = {
    "przed_siewem": "przed siewem",
    "wschody_jesienne": "wschody jesienne",
    "spoczynek_zimowy": "spoczynek zimowy",
    "poczatkowa": "faza początkowa",
    "rozwoj": "faza rozwoju",
    "pelnia": "pełnia rozwoju",
    "dojrzewanie": "dojrzewanie",
    "po_zbiorze": "po zbiorze",
}
SENSITIVE_PHASES = {"poczatkowa", "rozwoj", "pelnia"}  # stres liczony, możliwe nawadnianie (D32)
BARE_PHASES = {"przed_siewem", "po_zbiorze"}


@dataclass(frozen=True)
class DayInfo:
    phase: str
    kc: float
    zr: float  # głębokość korzeni / warstwy czynnej [m]
    sensitive: bool
    bare: bool
    season_year: int  # sezon, którego dotyczy dzień (dla dni stresu)
    day_of_season: int | None  # 0 = start sezonu (tylko fazy uprawy)


@dataclass(frozen=True)
class Crop:
    id: str
    label: str
    kc_ini: float
    kc_mid: float
    kc_end: float
    base_phases: tuple[int, int, int, int]  # proporcje faz z FAO-56 tab. 11 (dni w źródle)
    root_depth_m: float  # Zr max
    p: float  # frakcja TAW łatwo dostępna (RAW = p · TAW)
    start: tuple[int, int]  # siew / wznowienie wegetacji (miesiąc, dzień)
    harvest: tuple[int, int]  # typowy zbiór (koniec sezonu modelu)
    kind: str  # "jara" | "ozima" | "jesienna" | "wieloletnia"
    source: str
    autumn_sowing: tuple[int, int] | None = None  # ozime: siew jesienny następnego sezonu
    irrigation_practice: str = "optional"  # "not_practiced" | "optional" | "common" (D48)
    # ── ranking „Co tu posiać?” i płodozmian (crops.csv, A5b-2a) ──
    group_id: str = ""  # uprawa IUNG SMSR, której modelem wody liczymy gatunek
    in_backend: bool = True  # jedna z 15 upraw kontraktu (CropId)
    in_ranking: bool = False
    ky_total: float = 1.0  # FAO-33: 1 − Ya/Ym = Ky · (1 − ETa/ETc)
    ky_phases: dict = field(default_factory=dict, hash=False, compare=False)  # faza → Ky (gdy znane)
    sensitivity: str = "srednia"  # wrażliwość na suszę: niska / srednia / wysoka
    min_break_years: int = 0  # ile lat przerwy w uprawie po sobie
    bad_previous: tuple[str, ...] = ()
    good_previous: tuple[str, ...] = ()
    soils_ok_iung: frozenset = frozenset()
    soils_ok_complex: frozenset = frozenset()
    soils_bad_iung: frozenset = frozenset()
    soils_bad_complex: frozenset = frozenset()
    estimated: tuple[str, ...] = ()  # parametry szacunkowe (np. Ky) – niższa pewność w rankingu
    _info: dict = field(default_factory=dict, init=False, repr=False, hash=False, compare=False)
    phases: tuple[int, int, int, int] = field(init=False)

    def __post_init__(self) -> None:
        total = (date(2001, *self.harvest) - date(2001, *self.start)).days + 1
        base = sum(self.base_phases)
        ph = [max(1, round(b * total / base)) for b in self.base_phases]
        ph[2] += total - sum(ph)  # dopasowanie zaokrągleń w fazie pełni
        object.__setattr__(self, "phases", tuple(ph))

    @property
    def length(self) -> int:
        return sum(self.phases)

    def season(self, year: int) -> tuple[date, date]:
        """Start (siew / wznowienie) i typowy zbiór w danym roku."""
        return date(year, *self.start), date(year, *self.harvest)

    def stage(self, day: int) -> str | None:
        """Faza dla dnia sezonu (0 = start)."""
        if day < 0 or day >= self.length:
            return None
        a, b, c, _ = self.phases
        if day < a:
            return "poczatkowa"
        if day < a + b:
            return "rozwoj"
        if day < a + b + c:
            return "pelnia"
        return "dojrzewanie"

    def kc(self, day: int) -> float | None:
        """Kc wg FAO-56 (rys. 25): stały w fazie początkowej i pełni, liniowy w rozwoju i dojrzewaniu."""
        if day < 0 or day >= self.length:
            return None
        a, b, c, d = self.phases
        if day < a:
            return self.kc_ini
        if day < a + b:
            return self.kc_ini + (self.kc_mid - self.kc_ini) * (day - a + 1) / b
        if day < a + b + c:
            return self.kc_mid
        return self.kc_mid + (self.kc_end - self.kc_mid) * (day - a - b - c + 1) / d

    @property
    def zr_start(self) -> float:
        return {"ozima": ZR_DORMANT_M, "wieloletnia": self.root_depth_m}.get(self.kind, ZE_M)

    def root_depth(self, day: int) -> float:
        """Korzenie rosną liniowo od startu do końca fazy rozwoju, potem stałe (D30)."""
        grow = self.phases[0] + self.phases[1]
        if self.kind == "wieloletnia" or day >= grow:
            return self.root_depth_m
        return self.zr_start + (self.root_depth_m - self.zr_start) * max(day, 0) / grow

    def season_year_for(self, d: date) -> int:
        """Rok ostatniego sezonu, który już się zaczął (do statystyk i okna modelu)."""
        return d.year if d >= date(d.year, *self.start) else d.year - 1

    def day_info(self, d: date) -> DayInfo:
        """Kalendarz dnia – z pamięcią (ranking liczy 17 upraw × 10 sezonów dzień po dniu)."""
        hit = self._info.get(d)
        if hit is None:
            hit = self._info[d] = self._day_info(d)
        return hit

    def _day_info(self, d: date) -> DayInfo:
        y = d.year
        s, h = self.season(y)
        if s <= d <= h:
            k = (d - s).days
            ph = self.stage(k)
            return DayInfo(ph, self.kc(k), self.root_depth(k), ph in SENSITIVE_PHASES, False, y, k)
        dormant = DayInfo("spoczynek_zimowy", KC_DORMANT, self.root_depth_m, False, False, y, None)
        bare_before = DayInfo("przed_siewem", KC_BARE, ZE_M, False, True, y, None)
        bare_after = DayInfo("po_zbiorze", KC_BARE, ZE_M, False, True, y, None)
        if self.kind == "jara":
            return bare_before if d < s else bare_after
        if self.kind == "wieloletnia":
            return dormant
        if self.kind == "ozima":
            if d < s:
                return DayInfo("spoczynek_zimowy", KC_DORMANT, ZR_DORMANT_M, False, False, y, None)
            a = date(y, *self.autumn_sowing) if self.autumn_sowing else date(y, 9, 25)
            nov1 = date(y, 11, 1)
            if d < a:
                return bare_after
            if d < nov1:
                frac = (d - a).days / max(1, (nov1 - a).days)
                return DayInfo("wschody_jesienne", self.kc_ini, ZE_M + (ZR_DORMANT_M - ZE_M) * frac, False, False, y + 1, None)
            return DayInfo("spoczynek_zimowy", KC_DORMANT, ZR_DORMANT_M, False, False, y + 1, None)
        # jesienna (rzepak – okres jesienny): przed siewem goła gleba od 1 III, po okresie jesiennym spoczynek
        if d < date(y, 3, 1):
            return DayInfo("spoczynek_zimowy", KC_DORMANT, self.root_depth_m, False, False, y - 1, None)
        if d < s:
            return bare_before
        return DayInfo("spoczynek_zimowy", KC_DORMANT, self.root_depth_m, False, False, y, None)


# ── data siewu podana przez rolnika (A21) ───────────────────────────────────────────────────
SOWING_MAX_SHIFT_DAYS = 30  # o ile najwyżej data siewu może odbiegać od typowej dla uprawy
SOWING_OUT_OF_RANGE = "data siewu poza typowym zakresem – użyto typowej"


def typical_sowing(crop: "Crop") -> tuple[int, int] | None:
    """(miesiąc, dzień) typowego siewu: ozime – siew jesienny, jare i rzepak jesienny – start sezonu;
    wieloletnie – brak (None)."""
    if crop.kind == "wieloletnia":
        return None
    return (crop.autumn_sowing or (9, 25)) if crop.kind == "ozima" else crop.start


def with_sowing(crop: "Crop", sowing: date | None) -> tuple["Crop", str | None]:
    """(uprawa do modelu wody, nota). Data siewu w granicach ± `SOWING_MAX_SHIFT_DAYS` od typowej → kopia uprawy
    z przesuniętym siewem (fazy przeliczone na okres siew–zbiór); poza zakresem – uprawa typowa i nota."""
    typ = typical_sowing(crop)
    if sowing is None:
        return crop, None
    if typ is None:
        return crop, "uprawa wieloletnia – data siewu nie dotyczy"
    if (sowing.month, sowing.day) == typ:
        return crop, None
    ref = date(sowing.year, *typ)
    if abs((sowing - ref).days) > SOWING_MAX_SHIFT_DAYS:
        return crop, SOWING_OUT_OF_RANGE
    md = (sowing.month, sowing.day) if (sowing.month, sowing.day) != (2, 29) else (2, 28)
    shifted = replace(crop, autumn_sowing=md) if crop.kind == "ozima" else replace(crop, start=md)
    return shifted, None


# ── Konfiguracja upraw: JEDNO ŹRÓDŁO PRAWDY = app/data/crops/crops.csv (A5b-2a, D60) ─────────
# Plik osoby C (research/data/crops.csv, gałąź c/research) + dwie kolumny backendu: `root_depth_m` (jedna wartość
# z zakresu FAO-56 tab. 22 używana w modelu) i `typ` (jara / ozima / jesienna / wieloletnia).
# CROPS – 15 upraw IUNG SMSR (kontrakt CropId: wybór rolnika, analiza); ALL_CROPS – dodatkowo 7 gatunków do
# rankingu „Co tu posiać?” (pszenica ozima, żyto, pszenżyto, jęczmienie, owies, łubin) liczonych modelem wody
# swojej grupy (`group_id`) z własnymi terminami, Ky i wymaganiami glebowymi.
CROPS_CSV = Path(__file__).parents[1] / "data" / "crops" / "crops.csv"
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
# Ky potwierdzone w tabeli FAO-33 (research/data/README.md); pozostałe – szacunek (niższa pewność w rankingu)
KY_VERIFIED = {"zboza_ozime", "pszenica_ozima", "kukurydza_ziarno", "ziemniak", "burak_cukrowy", "straczkowe"}


def _md(text: str) -> tuple[int, int]:
    m, d = text.split("-")
    return int(m), int(d)


def _ids(text: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in (text or "").split(";") if x.strip())


def _soils(text: str) -> tuple[frozenset[int], frozenset[str]]:
    """'iung:II,III;kompleksy:1,2' → ({2, 3}, {'1', '2'})."""
    iung: set[int] = set()
    komp: set[str] = set()
    for part in (text or "").split(";"):
        key, _, vals = part.partition(":")
        items = [v.strip() for v in vals.split(",") if v.strip()]
        if key.strip() == "iung":
            iung |= {_ROMAN[v] for v in items}
        elif key.strip() == "kompleksy":
            komp |= set(items)
    return frozenset(iung), frozenset(komp)


def _ky_phases(text: str) -> dict[str, float]:
    names = {"ini": "poczatkowa", "dev": "rozwoj", "mid": "pelnia", "late": "dojrzewanie"}
    out = {}
    for part in (text or "").split(";"):
        k, _, v = part.partition(":")
        if k.strip() in names and v.strip():
            out[names[k.strip()]] = float(v)
    return out


def _load(path: Path = CROPS_CSV) -> dict[str, Crop]:
    out: dict[str, Crop] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            kind = r["typ"]
            ok_i, ok_k = _soils(r["gleby_odpowiednie"])
            bad_i, bad_k = _soils(r["gleby_nieodpowiednie"])
            out[r["crop_id"]] = Crop(
                id=r["crop_id"], label=r["name_pl"], kc_ini=float(r["kc_ini"]), kc_mid=float(r["kc_mid"]),
                kc_end=float(r["kc_end"]),
                base_phases=tuple(int(r[k]) for k in ("faza_ini_dni", "faza_dev_dni", "faza_mid_dni", "faza_late_dni")),
                root_depth_m=float(r["root_depth_m"]), p=float(r["p_depletion"]), start=_md(r["start_wegetacji"]),
                harvest=_md(r["typowy_zbior"]), kind=kind, source=r["zrodla"],
                autumn_sowing=_md(r["typowy_siew"]) if kind == "ozima" else None,
                irrigation_practice=r["irrigation_practice"], group_id=r["group_id"],
                in_backend=bool(r["backend_id"]), in_ranking=r["in_ranking"] == "tak", ky_total=float(r["ky_total"]),
                ky_phases=_ky_phases(r["ky_fazy"]), sensitivity=r["wrazliwosc_na_susze"],
                min_break_years=int(r["min_przerwa_lat"]), bad_previous=_ids(r["zle_przedplony"]),
                good_previous=_ids(r["dobre_przedplony"]), soils_ok_iung=ok_i, soils_ok_complex=ok_k,
                soils_bad_iung=bad_i, soils_bad_complex=bad_k,
                estimated=() if r["crop_id"] in KY_VERIFIED else ("Ky",),
            )
    return out


ALL_CROPS: dict[str, Crop] = _load()
CROPS: dict[str, Crop] = {k: c for k, c in ALL_CROPS.items() if c.in_backend}
RANKING_CROPS: tuple[Crop, ...] = tuple(c for c in ALL_CROPS.values() if c.in_ranking)
CEREAL_GROUPS = {"zboza_ozime", "zboza_jare"}

# ── Praktyka nawadniania w Polsce (D48, D60) – kolumna `irrigation_practice` w crops.csv ────
# not_practiced – w Polsce się nie nawadnia: zero o nawadnianiu, w zamian zatrzymanie wody w glebie;
# optional – nawadnia się rzadko: bez dawek, najwyżej informacja o niedoborze wody w sezonie (D64);
# common – nawadnianie to typowa praktyka: plan dawek.
IRRIGATION_PRACTICE: dict[str, str] = {c.id: c.irrigation_practice for c in CROPS.values()}
# dopełniacz do zdania „… w Polsce się nie nawadnia” (wymóg A5b-1)
NOT_IRRIGATED_GENITIVE = {"zboza_ozime": "Zbóż", "zboza_jare": "Zbóż", "rzepak": "Rzepaku",
                          "rzepak_jesien": "Rzepaku", "straczkowe": "Roślin strączkowych",
                          "burak_cukrowy": "Buraków cukrowych"}


def no_irrigation_sentence(crop: "Crop") -> str | None:
    """„Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie” (tylko not_practiced)."""
    if crop.irrigation_practice != "not_practiced":
        return None
    who = NOT_IRRIGATED_GENITIVE.get(crop.id) or NOT_IRRIGATED_GENITIVE.get(crop.group_id, crop.label)
    return f"{who} w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie"


def get_crop(crop_id: str) -> Crop:
    """Uprawa do analizy (15 upraw kontraktu); gatunki rankingu – przez ALL_CROPS."""
    try:
        return CROPS[crop_id]
    except KeyError as exc:
        raise ValueError(f"Nieznana uprawa: {crop_id}") from exc
