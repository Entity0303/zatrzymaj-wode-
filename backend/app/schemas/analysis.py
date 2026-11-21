"""KONTRAKT API: wynik analizy wodnej działki – GET /api/analysis?parcel_id=&crop=&date=

Źródło prawdy dla backendu (osoba A) i frontendu (osoba B). Odpowiednik TypeScript:
frontend/src/api/types.ts (AnalysisResponse i typy składowe), przykład:
frontend/src/mocks/analysis.sample.json (walidowany testem tests/test_contract.py).
Zmiany tylko po uzgodnieniu i w obu miejscach naraz (CLAUDE.md – Praca zespołowa).

Zasady (CLAUDE.md, design/SPEC_UI.md 15):
- każda liczba ma `source_tag` (pochodzenie: pomiar / satelita+data / obliczenia /
  szacunek_modelu / prognoza / brak_danych),
- brak danych = `value: null` + `source_tag.kind = "brak_danych"` – nigdy 0 ani wymyślona wartość,
- dla daty historycznej używamy wyłącznie danych sprzed `analysis_date`,
- wszystko liczone z pobranych danych; teksty rekomendacji generowane z reguł i liczb.
"""

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.parcel import Parcel

# ── Słowniki ────────────────────────────────────────────────────────────────────────────────

StatusLevel = Literal["ok", "warn", "risk", "danger", "no_data"]
"""Dobrze / Uwaga / Ryzyko / Susza / Brak danych (SPEC 2.2)."""

SourceKind = Literal["pomiar", "satelita", "obliczenia", "szacunek_modelu", "prognoza", "brak_danych"]
"""Etykiety pochodzenia liczb (SPEC 15.2)."""

Confidence = Literal["wysoka", "srednia", "ograniczona"]

RecommendationCategory = Literal["retencja", "agrotechnika", "nawadnianie"]
"""Kolejność w odpowiedzi zawsze: retencja → agrotechnika → nawadnianie."""

CropId = Literal[
    "zboza_ozime",
    "zboza_jare",
    "kukurydza_ziarno",
    "kukurydza_kiszonka",
    "rzepak",
    "rzepak_jesien",
    "ziemniak",
    "burak_cukrowy",
    "straczkowe",
    "warzywa",
    "drzewa_owocowe",
    "krzewy_owocowe",
    "truskawki",
    "chmiel",
    "tyton",
]
"""15 upraw IUNG SMSR (lista etykiet: frontend/src/lib/crops.ts)."""

PreviousCropId = Literal[
    "zboza_ozime", "zboza_jare", "kukurydza_ziarno", "kukurydza_kiszonka", "rzepak", "rzepak_jesien", "ziemniak",
    "burak_cukrowy", "straczkowe", "warzywa", "drzewa_owocowe", "krzewy_owocowe", "truskawki", "chmiel", "tyton",
    "nie_wiem",
]
"""Uprawa w poprzednim roku (przedplon): 15 upraw IUNG + „nie wiem”."""

PermitLevel = Literal["none", "maybe", "required"]
"""Formalności: none – bez formalności; maybe – może wymagać zgłoszenia wodnoprawnego;
required – wymaga pozwolenia wodnoprawnego (Wody Polskie)."""

RecommendationWhen = Literal["teraz", "po_zbiorze", "przed_sezonem"]
"""Kiedy działać: teraz / po zbiorze / przed następnym sezonem."""

RainRetention = Literal["ucieka", "zatrzymuje", "splywa"]
"""Co dzieje się z wodą z ulewy: szybko wsiąka i ucieka w głąb / dobrze ją zatrzymuje / ryzyko spływu i zastoisk."""

StepState = Literal["done", "active", "error", "pending"]
SourceAvailability = Literal["ok", "czesciowo", "brak"]
CauseFactor = Literal["opady", "parowanie", "gleba", "teren", "uprawa", "inne"]


class Contract(BaseModel):
    # nieznane pola = błąd: przykład w frontend/src/mocks nie może rozjechać się z kontraktem
    model_config = ConfigDict(extra="forbid")


# ── Pochodzenie i wskaźniki ─────────────────────────────────────────────────────────────────


class SourceTag(Contract):
    kind: SourceKind
    date: dt.date | None = Field(None, description="Data danych, np. zdjęcia satelitarnego (wymagana dla 'satelita')")
    source: str | None = Field(None, description="Nazwa źródła, np. 'Sentinel-2 L2A', 'NASA POWER'")


class Indicator(Contract):
    value: float | None = Field(description="null = brak danych (nigdy 0 zamiast braku)")
    unit: str | None = Field(None, description="mm, %, dni, pkt …")
    label: str | None = Field(None, description="Opis słowny, np. 'Dobra', 'Średnie'")
    status: StatusLevel = "no_data"
    note: str | None = Field(None, description="Krótki dopisek, np. 'stres za ok. 6 dni'")
    source_tag: SourceTag


class RiskIndicator(Indicator):
    days_to_stress: int | None = Field(None, description="Za ile dni rośliny zaczną odczuwać brak wody")


class SatelliteIndicator(Indicator):
    index_value: float | None = Field(None, description="Surowy wskaźnik (NDVI / NDMI) – tylko do 'Szczegółów'")


class Indicators(Contract):
    """Kluczowe wskaźniki (SPEC 6.4, 7.A)."""

    soil_water_pct: Indicator = Field(description="Woda w glebie, % wody dostępnej – szacunek_modelu")
    soil_water_mm: Indicator = Field(description="Woda w glebie, mm – szacunek_modelu")
    risk_7d: RiskIndicator = Field(description="Ryzyko niedoboru na 7 dni – prognoza")
    crop_health: SatelliteIndicator = Field(description="Kondycja upraw 0–100 (NDVI) – satelita + data")
    plant_moisture: SatelliteIndicator = Field(description="Wilgotność roślin (NDMI) – satelita + data")
    water_balance_season: Indicator = Field(description="Bilans wody od początku sezonu, mm – obliczenia")
    soil_capacity: Indicator = Field(description="Ile wody zmieści gleba (WOD), mm – kategoria IUNG")


class OverallStatus(Contract):
    """Karta stanu (SPEC 6.3) i wskaźnik w okręgu paszportu (SPEC 7.A)."""

    level: StatusLevel
    score: int | None = Field(None, ge=0, le=100, description="Ogólny stan wodny 0–100")
    headline: str = Field(description="Np. 'Uwaga – rośnie ryzyko suszy'")
    summary: str = Field(description="Jedno zdanie z liczbami")


# ── Gleba (IUNG + EGiB) ─────────────────────────────────────────────────────────────────────

NonAgriculturalReason = Literal["las", "woda", "zabudowa", "drogi", "gleby_organiczne"]
"""Dlaczego ocena suszy rolniczej nie ma zastosowania (kody IUNG 11, 12, 13, 14, 5 łącznie > 50%)."""


class SoilShareItem(Contract):
    code: int = Field(description="Kod IUNG: 1–4 kategorie podatności, 5 organiczne, 11 las, 12 woda, 13 zabudowa, 14 drogi/nieużytki")
    label: str
    share: float = Field(ge=0, le=1)


class Soil(Contract):
    """Gleba działki (SPEC 7.A „ile wody zmieści gleba”, 15.1 „to nie jest grunt rolny”, 15.3)."""

    dominant_code: int | None
    dominant_label: str | None
    shares: list[SoilShareItem] = Field(description="Udziały kodów IUNG w obrysie, od największego")
    agricultural_share: float | None = Field(None, ge=0, le=1, description="Udział gleb mineralnych użytków rolnych (kody 1–4)")
    wod_mm: float | None = Field(None, description="Woda dostępna dla roślin (WOD), średnia ważona dla części mineralnej")
    classes: list[str] | None = Field(None, description="Klasy bonitacyjne EGiB, np. ['RIIIa', 'PsIII'] – tylko informacyjnie")
    classes_note: str | None = Field(None, description="Powód braku klas, np. 'Powiat nie udostępnia klas…'")
    non_agricultural: bool = False
    non_agricultural_reason: NonAgriculturalReason | None = None
    non_agricultural_note: str | None = Field(None, description="Gotowy komunikat dla rolnika (SPEC 15.1)")
    texture: "SoilTexture | None" = Field(None, description="Frakcje i klasa uziarnienia 0–30 cm (SoilGrids)")
    permeability: "SoilPermeability | None" = Field(None, description="Przepuszczalność i zachowanie wody przy ulewie")
    soil_map: "SoilMapInfo | None" = Field(None, description="Mapa glebowo-rolnicza (GUGiK): kompleks i gatunek gleby")
    texture_note: str | None = Field(None, description="Powód braku frakcji / mapy glebowo-rolniczej, np. 'SoilGrids nie odpowiada'")
    source_tag: SourceTag


class SoilTexture(Contract):
    """Uziarnienie wierzchniej warstwy gleby (0–30 cm) – SoilGrids 250 m (ISRIC), średnia ważona 0–5, 5–15, 15–30 cm."""

    sand_pct: float = Field(ge=0, le=100, description="Piasek (0,05–2 mm), %")
    silt_pct: float = Field(ge=0, le=100, description="Pył (0,002–0,05 mm), %")
    clay_pct: float = Field(ge=0, le=100, description="Ił (< 0,002 mm), %")
    organic_carbon_pct: float | None = Field(None, description="Węgiel organiczny, % (próchnica ≈ 1,72 × węgiel)")
    texture_class: str = Field(description="Klasa uziarnienia po polsku (trójkąt USDA), np. 'glina piaszczysta'")
    texture_code: str = Field(description="Kod klasy USDA, np. 'sandy_loam'")
    depth: str = Field(description="Głębokość, np. '0–30 cm'")
    source_tag: SourceTag


class SoilPermeability(Contract):
    """Przepuszczalność gleby (Ksat) z frakcji i węgla organicznego – Saxton i Rawls (2006)."""

    ksat_mm_h: float = Field(ge=0, description="Przewodnictwo wodne w stanie nasycenia, mm/h")
    label: str = Field(description="Opis: bardzo duża / duża / średnia / mała / bardzo mała")
    rain_retention: RainRetention
    description: str = Field(description="Co dzieje się z wodą z ulewy – zdanie dla rolnika")
    method: str = Field(description="Np. 'Saxton i Rawls (2006), frakcje z SoilGrids'")
    source_tag: SourceTag


class SoilMapInfo(Contract):
    """Mapa glebowo-rolnicza 1:5000 (PZGiK, usługa WMS Geoportalu) – kontur w środku działki."""

    complex_code: str | None = Field(None, description="Kompleks przydatności rolniczej, np. '2', '5', '2z'")
    complex_label: str | None = Field(None, description="Np. 'pszenny dobry'")
    species_code: str | None = Field(None, description="Gatunek (uziarnienie) wierzchniej warstwy, np. 'pgl'")
    species_label: str | None = Field(None, description="Np. 'piasek gliniasty lekki'")
    deeper: list[str] = Field(default_factory=list, description="Utwory głębszych warstw (opisy), od góry")
    soil_type_code: str | None = Field(None, description="Typ/podtyp gleby, np. 'Bw' (brunatna wyługowana)")
    mapped_year: int | None = Field(None, description="Rok opracowania mapy (aktualność)")
    source_tag: SourceTag


# ── B. Na tle 10 lat ────────────────────────────────────────────────────────────────────────


class SeriesPoint(Contract):
    date: dt.date
    value: float | None


class BandPoint(Contract):
    """Pasmo z 10 lat dla tego samego dnia sezonu (oś X jak w serii bieżącego roku)."""

    date: dt.date
    min: float | None
    max: float | None
    mean: float | None


class YearStress(Contract):
    year: int
    stress_days: int | None
    is_current: bool = False


class MonthlyPrecip(Contract):
    month: int = Field(ge=1, le=12)
    current_mm: float | None
    mean_mm: float | None


class BalanceRank(Contract):
    """Pozycja bieżącego bilansu na tle lat porównawczych."""

    lower_years: int = Field(ge=0, description="W ilu latach porównawczych bilans był NIŻSZY niż teraz (0 = najgorszy)")
    of_years: int = Field(ge=0, description="Z ilu lat porównawczych (lata z niepełnymi danymi pominięte)")


class DrySpell(Contract):
    """Najdłuższy okres bez opadu (opad < 1 mm) w bieżącym sezonie."""

    days: int = Field(ge=0)
    end_date: dt.date | None = Field(None, description="Ostatni dzień tego okresu")


class History(Contract):
    period_start: dt.date
    period_end: dt.date
    season_start: dt.date
    balance_cumulative: list[SeriesPoint] = Field(description="Bilans wody narastająco – bieżący sezon, mm")
    balance_band: list[BandPoint] = Field(description="Pasmo min/max/średnia z 10 lat, mm")
    stress_days_by_year: list[YearStress]
    monthly_precip: list[MonthlyPrecip]
    summary: str | None = Field(None, description="Np. 'W 6 z 10 ostatnich lat w maju–lipcu brakowało wody.'")
    balance_deviation_mm: float | None = Field(None, description="Bieżący bilans − średnia z lat porównawczych, mm")
    balance_rank: BalanceRank | None = None
    longest_dry_spell: DrySpell | None = None
    band_years: list[int] = Field(default_factory=list, description="Lata użyte w paśmie porównawczym")
    source_tag: SourceTag


# ── Uprawa, stan wody, nawadnianie (A3b) ────────────────────────────────────────────────────

CropPhase = Literal[
    "przed_siewem",
    "wschody_jesienne",
    "spoczynek_zimowy",
    "poczatkowa",
    "rozwoj",
    "pelnia",
    "dojrzewanie",
    "po_zbiorze",
]
"""Faza uprawy w dacie analizy. Wrażliwe na niedobór (stres, nawadnianie): poczatkowa, rozwoj, pelnia."""

IrrigationStatus = Literal["zalecane", "niepotrzebne", "nieuzasadnione_w_fazie", "brak_danych"]


class CropSeason(Contract):
    phase: CropPhase
    phase_label: str = Field(description="Np. 'pełnia rozwoju', 'po zbiorze'")
    season_year: int = Field(description="Rok sezonu, którego dotyczą dni stresu")
    season_start: dt.date = Field(description="Siew / wznowienie wegetacji")
    harvest: dt.date = Field(description="Typowy termin zbioru w Polsce (koniec sezonu modelu)")
    day_of_season: int | None = Field(None, description="Dzień sezonu w dacie analizy (1 = siew / wznowienie)")
    sensitive: bool = Field(description="Faza wrażliwa na niedobór wody – liczymy stres, możliwe zalecenie nawadniania")
    root_depth_m: float | None = Field(None, description="Głębokość korzeni w modelu w dacie analizy")


class SeasonSummary(Contract):
    """Podsumowanie zakończonego sezonu uprawy."""

    year: int
    stress_days: int | None
    mean_prev_stress_days: float | None = Field(None, description="Średnia z 10 poprzednich sezonów")


class SoilWaterState(Contract):
    """Stan wody w glebie w dacie analizy – także poza sezonem (dane do rekomendacji jesienno-zimowych)."""

    scope: Literal["strefa_korzeni", "profil"] = Field(
        description="strefa_korzeni – w fazach uprawy; profil – ok. 1 m, poza sezonem (goła gleba / spoczynek)"
    )
    depth_m: float
    description: str = Field(description="Np. 'poza sezonem – gleba odbudowuje zapas wody'")
    rank: BalanceRank | None = Field(
        None, description="Ten sam dzień w 10 poprzednich latach: w ilu latach było MNIEJ wody niż teraz, z ilu"
    )
    last_season: SeasonSummary | None = Field(None, description="Zakończony sezon (po zbiorze / przed siewem)")


class IrrigationPlan(Contract):
    status: IrrigationStatus
    message: str = Field(description="Np. '25 mm teraz, powtórz za ok. 5 dni'")
    dose_mm: float | None = Field(None, le=35, description="Dawka jednorazowa zależna od gleby, nigdy > 35 mm")
    first_date: dt.date | None = None
    interval_days: int | None = Field(None, description="Co ile dni powtarzać, by utrzymać wodę powyżej progu stresu")
    total_7d_mm: float | None = Field(None, description="Łączny niedobór do uzupełnienia w 7 dniach")
    doses_7d: int | None = None
    source_tag: SourceTag


# ── C. Dlaczego? ────────────────────────────────────────────────────────────────────────────


class Cause(Contract):
    factor: CauseFactor
    title: str = Field(description="Np. 'Mało opadów'")
    share: float = Field(ge=0, le=1, description="Udział w problemie (paski od największego)")
    description: str = Field(description="Z liczbą, np. 'od marca 212 mm, zwykle 296 mm'")
    source_tag: SourceTag


# ── D. Co mogę zrobić? ──────────────────────────────────────────────────────────────────────


class Evidence(Contract):
    """Dane wejściowe, które uruchomiły regułę."""

    name: str
    value: float | str | None
    unit: str | None = None
    source: str
    date: dt.date | None = None


class Recommendation(Contract):
    id: str
    category: RecommendationCategory
    title: str
    description: str = Field(description="Jedno zdanie")
    why: str = Field(description="Przesłanki z liczbami (rozwijane „Dlaczego?”)")
    inputs: list[Evidence]
    confidence: Confidence
    location: dict[str, Any] | None = Field(None, description="GeoJSON geometria miejsca (EPSG:4326) – „Pokaż na mapie”")
    rule_id: str | None = Field(None, description="Id reguły z analysis/rules/*.yaml")
    priority: int = Field(0, description="Ważność w obrębie kategorii (większa = ważniejsza)")
    in_panel: bool = Field(False, description="Pokazać w panelu działki (maks. 3: po jednej z kategorii); reszta – paszport")
    when: RecommendationWhen = Field(description="Kiedy działać")
    when_label: str = Field(description="Np. 'teraz', 'po zbiorze', 'przed następnym sezonem'")
    permit: PermitLevel = Field(description="Formalności")
    permit_note: str = Field(description="Np. 'Bez formalności – możesz to zrobić sam.'")
    permit_url: str | None = Field(None, description="Link do Wód Polskich (dla maybe / required)")
    warning: str | None = Field(None, description="Przy niskiej pewności: 'obarczone dużym ryzykiem błędu'")
    eco_scheme: "EcoScheme | None" = Field(None, description="Powiązany ekoschemat ARiMR (bez kwot dopłat)")


class EcoScheme(Contract):
    """Ekoschemat (PS WPR, ARiMR) powiązany z rekomendacją – tylko informacja, bez kwot dopłat."""

    name: str = Field(description="Np. 'Rolnictwo węglowe i zarządzanie składnikami odżywczymi'")
    practice: str = Field(description="Np. 'Międzyplony ozime lub wsiewki śródplonowe'")
    code: str | None = Field(None, description="Kod praktyki, np. 'E_MPW'")
    note: str = Field(description="Np. 'Sprawdź aktualne warunki w ARiMR.'")


# ── E. Wiarygodność ─────────────────────────────────────────────────────────────────────────


class SourceStatus(Contract):
    name: str
    used_for: str
    data_date: dt.date | None
    resolution: str | None = None
    status: SourceAvailability
    note: str | None = None


class Completeness(Contract):
    available: int
    total: int


class Reliability(Contract):
    confidence: Confidence
    reason: str = Field(description="Np. 'Model i zdjęcie satelitarne zgadzają się'")
    sources: list[SourceStatus]
    completeness: Completeness
    limitations: list[str] = Field(description="Generowane z danych, np. 'Pogoda uśredniona dla obszaru ok. 50 km'")


# ── Ładowanie ───────────────────────────────────────────────────────────────────────────────


class LoadingStep(Contract):
    id: str
    label: str
    state: StepState
    note: str | None = None
    duration_ms: int | None = None


# ── Odpowiedź ───────────────────────────────────────────────────────────────────────────────


class AnalysisResponse(Contract):
    parcel: Parcel
    crop: CropId
    previous_crop: PreviousCropId | None = Field(None, description="Uprawa w poprzednim roku (jeśli podana)")
    analysis_date: dt.date
    historical: bool = Field(description="True, gdy analysis_date < dziś (analiza historyczna)")
    generated_at: dt.datetime
    status: OverallStatus
    indicators: Indicators
    crop_season: CropSeason
    soil_water: SoilWaterState
    irrigation: IrrigationPlan
    soil: Soil
    history: History
    causes: list[Cause] = Field(description="Od największego udziału")
    recommendations: list[Recommendation] = Field(description="retencja → agrotechnika → nawadnianie")
    reliability: Reliability
    steps: list[LoadingStep]


Soil.model_rebuild()
Recommendation.model_rebuild()
