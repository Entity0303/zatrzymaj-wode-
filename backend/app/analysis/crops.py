"""Uprawy: 15 upraw IUNG SMSR z parametrami do modelu wody w glebie FAO-56.

Identyfikatory = kontrakt (schemas/analysis.py CropId = frontend/src/lib/crops.ts).

Źródła (Allen i in., 1998, FAO Irrigation and Drainage Paper 56):
- Kc ini / mid / end – tab. 12 („single crop coefficients”), wartości dla klimatu
  sub-humid (RHmin ≈ 45%, u2 ≈ 2 m/s) – BEZ korekty klimatycznej Kc_mid/Kc_end (D24),
- długości faz (ini / dev / mid / late, dni) – tab. 11, wiersz najbliższy klimatowi
  umiarkowanemu, dopasowany do kalendarza PL (D23) – zaznaczone „dopasowane”,
- maks. głębokość korzeni Zr i frakcja p (łatwo dostępna woda) – tab. 22
  (zakres Zr → przyjęta wartość ze środka/dolnej części zakresu; p dla ETc ≈ 5 mm/d).
Start sezonu – typowy kalendarz w Polsce (zadanie A3, D23). „ZAŁOŻENIE” = brak uprawy w
tabelach FAO-56, przyjęto wartość analogiczną (D23).
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Crop:
    id: str
    label: str
    kc_ini: float
    kc_mid: float
    kc_end: float
    l_ini: int  # dni
    l_dev: int
    l_mid: int
    l_late: int
    root_depth_m: float  # Zr max
    p: float  # frakcja TAW łatwo dostępna (RAW = p · TAW)
    start: tuple[int, int]  # (miesiąc, dzień) startu sezonu modelu
    source: str  # skąd parametry (do „Szczegółów”)

    @property
    def length(self) -> int:
        return self.l_ini + self.l_dev + self.l_mid + self.l_late

    def season(self, year: int) -> tuple[date, date]:
        """Pierwszy i ostatni dzień sezonu modelu w danym roku."""
        s = date(year, *self.start)
        return s, s + timedelta(days=self.length - 1)

    def stage(self, day: int) -> str | None:
        """Faza dla dnia sezonu (0 = pierwszy dzień)."""
        if day < 0 or day >= self.length:
            return None
        bounds = [(self.l_ini, "początkowa"), (self.l_ini + self.l_dev, "rozwoju"),
                  (self.l_ini + self.l_dev + self.l_mid, "pełni rozwoju"), (self.length, "dojrzewania")]
        return next(name for b, name in bounds if day < b)

    def kc(self, day: int) -> float | None:
        """Kc wg FAO-56 (rys. 25): stały w fazie początkowej i pełni, liniowy w rozwoju i dojrzewaniu."""
        if day < 0 or day >= self.length:
            return None
        a = self.l_ini
        b = a + self.l_dev
        c = b + self.l_mid
        if day < a:
            return self.kc_ini
        if day < b:
            return self.kc_ini + (self.kc_mid - self.kc_ini) * (day - a + 1) / self.l_dev
        if day < c:
            return self.kc_mid
        return self.kc_mid + (self.kc_end - self.kc_mid) * (day - c + 1) / self.l_late


# fmt: off
CROPS: dict[str, Crop] = {c.id: c for c in [
    # Pszenica ozima. Kc: tab. 12 „Wheat, Winter” (Kc_ini z regeneracji wiosennej 0,7; mid 1,15; end 0,25–0,4 → 0,3).
    # Fazy: tab. 11 pszenica ozima, dopasowane do wegetacji od 1 III (żniwa ok. 7 VIII). Zr: tab. 22 Wheat 1,5–1,8 → 1,5; p 0,55.
    Crop("zboza_ozime", "Zboża ozime", 0.70, 1.15, 0.30, 20, 60, 50, 30, 1.5, 0.55, (3, 1),
         "FAO-56 tab. 12, 11 (dopasowane), 22 – pszenica ozima"),
    # Zboża jare (pszenica/jęczmień jary). Kc: tab. 12 „Wheat, Spring”/„Barley” 0,3 / 1,15 / 0,25.
    # Fazy: tab. 11 „Barley/Oats/Wheat” 20/25/60/30 (siew III/IV, 35–45°N). Zr: tab. 22 Barley 1,0–1,5 → 1,2; p 0,55.
    Crop("zboza_jare", "Zboża jare", 0.30, 1.15, 0.25, 20, 25, 60, 30, 1.2, 0.55, (4, 8),
         "FAO-56 tab. 12, 11, 22 – zboża jare (siew 1–15 IV)"),
    # Kukurydza na ziarno. Kc: tab. 12 „Maize, Field (grain)” 0,3 / 1,20 / 0,35 (suche ziarno).
    # Fazy: tab. 11 maize grain 30/40/50/50 (siew IV, klimat umiarkowany). Zr: tab. 22 Maize 1,0–1,7 → 1,2; p 0,55.
    Crop("kukurydza_ziarno", "Kukurydza na ziarno", 0.30, 1.20, 0.35, 30, 40, 50, 50, 1.2, 0.55, (5, 1),
         "FAO-56 tab. 12, 11, 22 – kukurydza na ziarno"),
    # Kukurydza na kiszonkę. Kc_ini/mid jak ziarno (tab. 12); ZAŁOŻENIE: Kc_end 0,50 (zbiór zielonej masy przed
    # pełną dojrzałością) i krótsza faza dojrzewania 30 dni. Zr, p: tab. 22 Maize → 1,2; 0,55.
    Crop("kukurydza_kiszonka", "Kukurydza na kiszonkę", 0.30, 1.20, 0.50, 30, 40, 50, 30, 1.2, 0.55, (5, 1),
         "FAO-56 tab. 12, 11, 22 – kukurydza; Kc_end i faza dojrzewania – założenie (zbiór na kiszonkę)"),
    # Rzepak ozimy (wegetacja wiosenna). Kc: tab. 12 „Rapeseed, Canola” 0,35 / 1,0–1,15 → 1,10 / 0,35.
    # Fazy: tab. 11 rzepak, dopasowane do wegetacji od 1 III (zbiór ok. 24 VII). Zr: tab. 22 Rapeseed 1,0–1,5 → 1,2; p 0,6.
    Crop("rzepak", "Rzepak i rzepik", 0.35, 1.10, 0.35, 20, 35, 55, 35, 1.2, 0.60, (3, 1),
         "FAO-56 tab. 12, 11 (dopasowane), 22 – rzepak ozimy, wegetacja wiosenna"),
    # Rzepak – okres jesienny (siew ok. 20 VIII do spoczynku zimowego). ZAŁOŻENIE: Kc_mid 0,80 (rozeta, niepełne
    # pokrycie), bez fazy dojrzewania – Kc_end = Kc_mid; fazy 25/45/30/1 dni (do ok. 28 XI). Kc_ini, Zr, p – tab. 12, 22.
    Crop("rzepak_jesien", "Rzepak i rzepik (jesień)", 0.35, 0.80, 0.80, 25, 45, 30, 1, 1.0, 0.60, (8, 20),
         "FAO-56 tab. 12, 22 – rzepak; Kc_mid i fazy jesienne – założenie"),
    # Ziemniak. Kc: tab. 12 „Potato” 0,5 / 1,15 / 0,75. Fazy: tab. 11 potato „Europe” 25/30/45/30 (sadzenie IV/V).
    # Zr: tab. 22 Potato 0,4–0,6 → 0,5; p 0,35.
    Crop("ziemniak", "Ziemniak", 0.50, 1.15, 0.75, 25, 30, 45, 30, 0.5, 0.35, (4, 20),
         "FAO-56 tab. 12, 11, 22 – ziemniak"),
    # Burak cukrowy. Kc: tab. 12 „Sugar Beet” 0,35 / 1,20 / 0,70. Fazy: tab. 11 sugar beet, dopasowane do
    # siewu 1 IV i zbioru ok. X: 25/35/90/40. Zr: tab. 22 Sugar beet 0,7–1,2 → 1,0; p 0,55.
    Crop("burak_cukrowy", "Burak cukrowy", 0.35, 1.20, 0.70, 25, 35, 90, 40, 1.0, 0.55, (4, 1),
         "FAO-56 tab. 12, 11 (dopasowane), 22 – burak cukrowy"),
    # Rośliny strączkowe (fasola/groch na suche nasiona). Kc: tab. 12 „Beans, dry” 0,4 / 1,15 / 0,35.
    # Fazy: tab. 11 beans dry „Continental” 20/30/40/20. Zr: tab. 22 Beans 0,6–0,9 → 0,7; p 0,45.
    # ZAŁOŻENIE: siew 15 IV (A3 nie podaje terminu).
    Crop("straczkowe", "Rośliny strączkowe", 0.40, 1.15, 0.35, 20, 30, 40, 20, 0.7, 0.45, (4, 15),
         "FAO-56 tab. 12, 11, 22 – fasola na suche nasiona; termin siewu – założenie"),
    # Warzywa gruntowe (ogólnie). Kc: tab. 12 grupa „Small Vegetables” 0,7 / 1,05 / 0,95.
    # ZAŁOŻENIE: fazy 20/30/50/20, start 20 IV; Zr 0,5 m, p 0,4 (środek zakresów warzyw z tab. 22).
    Crop("warzywa", "Warzywa gruntowe", 0.70, 1.05, 0.95, 20, 30, 50, 20, 0.5, 0.40, (4, 20),
         "FAO-56 tab. 12 (small vegetables), 22; fazy i start – założenie"),
    # Drzewa owocowe (jabłoń, wiśnia, grusza bez okrywy, z mrozami). Kc: tab. 12 0,45 / 0,95 / 0,70.
    # Fazy: tab. 11 apples/cherries/pears 20/70/90/30, dopasowane do sezonu 1 IV–31 X (214 dni) → mid 94.
    # Zr: tab. 22 Apples, cherries, pears 1,0–2,0 → 1,5; p 0,5.
    Crop("drzewa_owocowe", "Drzewa owocowe", 0.45, 0.95, 0.70, 20, 70, 94, 30, 1.5, 0.50, (4, 1),
         "FAO-56 tab. 12, 11 (dopasowane do 1 IV–31 X), 22 – jabłoń/wiśnia/grusza"),
    # Krzewy owocowe. Kc: tab. 12 „Berries (bushes)” 0,30 / 1,05 / 0,50. ZAŁOŻENIE: fazy 20/50/110/34 (1 IV–31 X).
    # Zr: tab. 22 Berries 0,6–1,2 → 0,8; p 0,5.
    Crop("krzewy_owocowe", "Krzewy owocowe", 0.30, 1.05, 0.50, 20, 50, 110, 34, 0.8, 0.50, (4, 1),
         "FAO-56 tab. 12, 22 – krzewy jagodowe; fazy – założenie (1 IV–31 X)"),
    # Truskawki. Kc: tab. 12 „Strawberries” 0,40 / 0,85 / 0,75. ZAŁOŻENIE: fazy 20/40/120/34 (1 IV–31 X).
    # Zr: tab. 22 Strawberries 0,2–0,3 → 0,3; p 0,2.
    Crop("truskawki", "Truskawki", 0.40, 0.85, 0.75, 20, 40, 120, 34, 0.3, 0.20, (4, 1),
         "FAO-56 tab. 12, 22 – truskawka; fazy – założenie (1 IV–31 X)"),
    # Chmiel. Kc: tab. 12 „Hops” 0,3 / 1,05 / 0,85. Fazy: tab. 11 hops 25/40/80/10, faza dojrzewania wydłużona
    # do 31 X (69 dni, ZAŁOŻENIE: roślina transpiruje po zbiorze). Zr: tab. 22 Hops 1,0–1,2 → 1,0; p 0,5.
    Crop("chmiel", "Chmiel", 0.30, 1.05, 0.85, 25, 40, 80, 69, 1.0, 0.50, (4, 1),
         "FAO-56 tab. 12, 11 (dopasowane do 1 IV–31 X), 22 – chmiel"),
    # Tytoń. ZAŁOŻENIE: brak w tab. 12 i 22 FAO-56 – Kc 0,4 / 1,05 / 0,80, fazy 20/35/45/30 od 15 V
    # (wysadzanie rozsady), Zr 0,8 m, p 0,5 (analogia do upraw rzędowych liściastych).
    Crop("tyton", "Tytoń", 0.40, 1.05, 0.80, 20, 35, 45, 30, 0.8, 0.50, (5, 15),
         "Założenie – tytoń nie występuje w tab. 12/22 FAO-56"),
]}
# fmt: on


def get_crop(crop_id: str) -> Crop:
    try:
        return CROPS[crop_id]
    except KeyError as exc:
        raise ValueError(f"Nieznana uprawa: {crop_id}") from exc
