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

from dataclasses import dataclass, field
from datetime import date

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


# fmt: off
CROPS: dict[str, Crop] = {c.id: c for c in [
    # Pszenica ozima. Kc: tab. 12 „Wheat, Winter” (regeneracja wiosenna 0,7; mid 1,15; end 0,25–0,4 → 0,3).
    # Proporcje faz: tab. 11 pszenica ozima 20/60/50/30. Zr: tab. 22 Wheat 1,5–1,8 → 1,5; p 0,55.
    # Wegetacja od 1 III, zbiór ok. 20 VII, siew jesienny ok. 25 IX (D31).
    Crop("zboza_ozime", "Zboża ozime", 0.70, 1.15, 0.30, (20, 60, 50, 30), 1.5, 0.55, (3, 1), (7, 20), "ozima",
         "FAO-56 tab. 12, 11, 22 – pszenica ozima; kalendarz PL", autumn_sowing=(9, 25)),
    # Zboża jare. Kc: tab. 12 „Wheat, Spring”/„Barley” 0,3 / 1,15 / 0,25. Faza: tab. 11 20/25/60/30.
    # Zr: tab. 22 Barley 1,0–1,5 → 1,2; p 0,55. Siew ok. 8 IV (1–15 IV), zbiór ok. 5 VIII.
    Crop("zboza_jare", "Zboża jare", 0.30, 1.15, 0.25, (20, 25, 60, 30), 1.2, 0.55, (4, 8), (8, 5), "jara",
         "FAO-56 tab. 12, 11, 22 – zboża jare; kalendarz PL"),
    # Kukurydza na ziarno. Kc: tab. 12 „Maize, Field (grain)” 0,3 / 1,20 / 0,35. Fazy: tab. 11 30/40/50/50.
    # Zr: tab. 22 Maize 1,0–1,7 → 1,2; p 0,55. Siew ok. 1 V, zbiór ok. 10 X.
    Crop("kukurydza_ziarno", "Kukurydza na ziarno", 0.30, 1.20, 0.35, (30, 40, 50, 50), 1.2, 0.55, (5, 1), (10, 10), "jara",
         "FAO-56 tab. 12, 11, 22 – kukurydza na ziarno; kalendarz PL"),
    # Kukurydza na kiszonkę. Kc_ini/mid jak ziarno; ZAŁOŻENIE Kc_end 0,50 i krótsza faza dojrzewania (30).
    # Siew ok. 1 V, zbiór ok. 15 IX.
    Crop("kukurydza_kiszonka", "Kukurydza na kiszonkę", 0.30, 1.20, 0.50, (30, 40, 50, 30), 1.2, 0.55, (5, 1), (9, 15), "jara",
         "FAO-56 tab. 12, 11, 22 – kukurydza; Kc_end i faza dojrzewania – założenie"),
    # Rzepak ozimy (wegetacja wiosenna). Kc: tab. 12 „Rapeseed, Canola” 0,35 / 1,0–1,15 → 1,10 / 0,35.
    # Fazy: tab. 11 20/35/55/35. Zr: tab. 22 1,0–1,5 → 1,2; p 0,6. Od 1 III, zbiór ok. 15 VII, siew ok. 25 VIII.
    Crop("rzepak", "Rzepak i rzepik", 0.35, 1.10, 0.35, (20, 35, 55, 35), 1.2, 0.60, (3, 1), (7, 15), "ozima",
         "FAO-56 tab. 12, 11, 22 – rzepak ozimy; kalendarz PL", autumn_sowing=(8, 25)),
    # Rzepak – okres jesienny (siew ok. 20 VIII do spoczynku ok. 30 XI). ZAŁOŻENIE: Kc_mid 0,80 (rozeta),
    # Kc_end = Kc_mid, proporcje faz 25/45/32/1.
    Crop("rzepak_jesien", "Rzepak i rzepik (jesień)", 0.35, 0.80, 0.80, (25, 45, 32, 1), 1.0, 0.60, (8, 20), (11, 30), "jesienna",
         "FAO-56 tab. 12, 22 – rzepak; Kc_mid i fazy jesienne – założenie"),
    # Ziemniak. Kc: tab. 12 „Potato” 0,5 / 1,15 / 0,75. Fazy: tab. 11 „Europe” 25/30/45/30.
    # Zr: tab. 22 0,4–0,6 → 0,5; p 0,35. Sadzenie ok. 20 IV, zbiór ok. 15 IX.
    Crop("ziemniak", "Ziemniak", 0.50, 1.15, 0.75, (25, 30, 45, 30), 0.5, 0.35, (4, 20), (9, 15), "jara",
         "FAO-56 tab. 12, 11, 22 – ziemniak; kalendarz PL"),
    # Burak cukrowy. Kc: tab. 12 0,35 / 1,20 / 0,70. Fazy: tab. 11 25/35/90/40. Zr: tab. 22 0,7–1,2 → 1,0; p 0,55.
    # Siew ok. 1 IV, zbiór ok. 20 X.
    Crop("burak_cukrowy", "Burak cukrowy", 0.35, 1.20, 0.70, (25, 35, 90, 40), 1.0, 0.55, (4, 1), (10, 20), "jara",
         "FAO-56 tab. 12, 11, 22 – burak cukrowy; kalendarz PL"),
    # Rośliny strączkowe. Kc: tab. 12 „Beans, dry” 0,4 / 1,15 / 0,35. Fazy: tab. 11 20/30/40/20.
    # Zr: tab. 22 0,6–0,9 → 0,7; p 0,45. ZAŁOŻENIE: siew 15 IV, zbiór 10 VIII.
    Crop("straczkowe", "Rośliny strączkowe", 0.40, 1.15, 0.35, (20, 30, 40, 20), 0.7, 0.45, (4, 15), (8, 10), "jara",
         "FAO-56 tab. 12, 11, 22 – fasola na suche nasiona; terminy – założenie"),
    # Warzywa gruntowe. Kc: tab. 12 „Small Vegetables” 0,7 / 1,05 / 0,95. ZAŁOŻENIE: fazy 20/30/50/20,
    # Zr 0,5 m, p 0,4, start 20 IV, koniec 31 VIII.
    Crop("warzywa", "Warzywa gruntowe", 0.70, 1.05, 0.95, (20, 30, 50, 20), 0.5, 0.40, (4, 20), (8, 31), "jara",
         "FAO-56 tab. 12 (small vegetables), 22; fazy i terminy – założenie"),
    # Drzewa owocowe. Kc: tab. 12 jabłoń/wiśnia/grusza bez okrywy 0,45 / 0,95 / 0,70. Fazy: tab. 11 20/70/90/30.
    # Zr: tab. 22 1,0–2,0 → 1,5; p 0,5. Sezon 1 IV–31 X, poza nim spoczynek.
    Crop("drzewa_owocowe", "Drzewa owocowe", 0.45, 0.95, 0.70, (20, 70, 90, 30), 1.5, 0.50, (4, 1), (10, 31), "wieloletnia",
         "FAO-56 tab. 12, 11, 22 – jabłoń/wiśnia/grusza; sezon 1 IV–31 X"),
    # Krzewy owocowe. Kc: tab. 12 „Berries (bushes)” 0,30 / 1,05 / 0,50. ZAŁOŻENIE fazy 20/50/110/34.
    # Zr: tab. 22 0,6–1,2 → 0,8; p 0,5.
    Crop("krzewy_owocowe", "Krzewy owocowe", 0.30, 1.05, 0.50, (20, 50, 110, 34), 0.8, 0.50, (4, 1), (10, 31), "wieloletnia",
         "FAO-56 tab. 12, 22 – krzewy jagodowe; fazy – założenie"),
    # Truskawki. Kc: tab. 12 0,40 / 0,85 / 0,75. ZAŁOŻENIE fazy 20/40/120/34. Zr: tab. 22 0,2–0,3 → 0,3; p 0,2.
    Crop("truskawki", "Truskawki", 0.40, 0.85, 0.75, (20, 40, 120, 34), 0.3, 0.20, (4, 1), (10, 31), "wieloletnia",
         "FAO-56 tab. 12, 22 – truskawka; fazy – założenie"),
    # Chmiel. Kc: tab. 12 „Hops” 0,3 / 1,05 / 0,85. Fazy: tab. 11 25/40/80/10, dojrzewanie wydłużone (ZAŁOŻENIE).
    # Zr: tab. 22 1,0–1,2 → 1,0; p 0,5.
    Crop("chmiel", "Chmiel", 0.30, 1.05, 0.85, (25, 40, 80, 69), 1.0, 0.50, (4, 1), (10, 31), "wieloletnia",
         "FAO-56 tab. 12, 11, 22 – chmiel; sezon 1 IV–31 X"),
    # Tytoń. ZAŁOŻENIE: brak w tab. 12 i 22 – Kc 0,4 / 1,05 / 0,80, fazy 20/35/45/30, Zr 0,8 m, p 0,5,
    # wysadzanie 15 V, zbiór 15 IX.
    Crop("tyton", "Tytoń", 0.40, 1.05, 0.80, (20, 35, 45, 30), 0.8, 0.50, (5, 15), (9, 15), "jara",
         "Założenie – tytoń nie występuje w tab. 12/22 FAO-56"),
]}
# fmt: on


# ── Praktyka nawadniania w Polsce (D48) ─────────────────────────────────────────────────────
# not_practiced – w Polsce się nie nawadnia: brak planu dawek i rekomendacji nawadniania, w zamian
#   zatrzymanie wody w glebie, ograniczenie parowania i termin zabiegów;
# optional – nawadnia się rzadko (gdy jest woda i sprzęt) – plan dawek z dopiskiem;
# common – nawadnianie to typowa praktyka.
IRRIGATION_PRACTICE: dict[str, str] = {
    "zboza_ozime": "not_practiced", "zboza_jare": "not_practiced",
    "rzepak": "not_practiced", "rzepak_jesien": "not_practiced",
    "straczkowe": "not_practiced",  # groch, bobik, łubin, soja na nasiona – w PL bez nawadniania
    "kukurydza_ziarno": "optional", "kukurydza_kiszonka": "optional",
    "burak_cukrowy": "optional",  # deszczownie tylko w części plantacji (gleby lekkie)
    "tyton": "optional",  # nawadniany doraźnie przy wysadzaniu i w suszy
    "ziemniak": "common", "warzywa": "common", "drzewa_owocowe": "common", "krzewy_owocowe": "common",
    "truskawki": "common",
    "chmiel": "common",  # plantacje chmielu (Lubelszczyzna) zwykle z nawadnianiem kroplowym
}
# dopełniacz do zdania „… w Polsce się nie nawadnia” (wymóg A5b-1)
NOT_IRRIGATED_GENITIVE = {"zboza_ozime": "Zbóż", "zboza_jare": "Zbóż", "rzepak": "Rzepaku",
                          "rzepak_jesien": "Rzepaku", "straczkowe": "Roślin strączkowych"}
for _c in CROPS.values():
    object.__setattr__(_c, "irrigation_practice", IRRIGATION_PRACTICE[_c.id])


def no_irrigation_sentence(crop: "Crop") -> str | None:
    """„Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie” (tylko not_practiced)."""
    if crop.irrigation_practice != "not_practiced":
        return None
    who = NOT_IRRIGATED_GENITIVE.get(crop.id, crop.label)
    return f"{who} w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie"


def get_crop(crop_id: str) -> Crop:
    try:
        return CROPS[crop_id]
    except KeyError as exc:
        raise ValueError(f"Nieznana uprawa: {crop_id}") from exc
