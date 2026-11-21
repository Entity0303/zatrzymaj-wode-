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


class History(Contract):
    period_start: dt.date
    period_end: dt.date
    season_start: dt.date
    balance_cumulative: list[SeriesPoint] = Field(description="Bilans wody narastająco – bieżący sezon, mm")
    balance_band: list[BandPoint] = Field(description="Pasmo min/max/średnia z 10 lat, mm")
    stress_days_by_year: list[YearStress]
    monthly_precip: list[MonthlyPrecip]
    summary: str | None = Field(None, description="Np. 'W 6 z 10 ostatnich lat w maju–lipcu brakowało wody.'")
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
    analysis_date: dt.date
    historical: bool = Field(description="True, gdy analysis_date < dziś (analiza historyczna)")
    generated_at: dt.datetime
    status: OverallStatus
    indicators: Indicators
    history: History
    causes: list[Cause] = Field(description="Od największego udziału")
    recommendations: list[Recommendation] = Field(description="retencja → agrotechnika → nawadnianie")
    reliability: Reliability
    steps: list[LoadingStep]
