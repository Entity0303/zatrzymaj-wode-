"""KONTRAKT API: wynik analizy wodnej działki – GET /api/analysis?parcel_id=&crop=&date=

`crop` jest opcjonalne (A5b-1): bez uprawy odpowiedź opisuje „Stan działki” (gleba, zapas wody pod
pokryciem referencyjnym FAO-56, bilans opad − ET0) – `crop`, `crop_season`, `irrigation` = null.

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


StatusScope = Literal["sezon", "zimowanie", "poza_sezonem", "bez_uprawy"]
"""Czego dotyczy ocena: sezon uprawy (stres roślin) / zimowanie – uprawa jest w polu (oziminy od siewu jesiennego
do wiosny, uprawy wieloletnie zimą) / poza sezonem uprawy (zapas wody w glebie i bilans z ostatnich
tygodni) / bez uprawy (stan wody na działce, pokrycie referencyjne FAO-56)."""


class OverallStatus(Contract):
    """Karta stanu (SPEC 6.3) i wskaźnik w okręgu paszportu (SPEC 7.A)."""

    level: StatusLevel
    score: int | None = Field(None, ge=0, le=100, description="Ogólny stan wodny 0–100")
    headline: str = Field(description="Np. 'Uwaga – rośnie ryzyko suszy'")
    summary: str = Field(description="Jedno zdanie z liczbami")
    scope: StatusScope | None = Field(None, description="Czego dotyczy ocena (sezon / poza sezonem / bez uprawy)")
    scope_label: str | None = Field(None, description="Etykieta, np. 'poza sezonem', 'stan wody na działce'")


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
    organic_matter: "OrganicMatter | None" = Field(None, description="A24: próchnica – szacunek SoilGrids (informacyjnie)")
    soil_map: "SoilMapInfo | None" = Field(None, description="Mapa glebowo-rolnicza (GUGiK): kompleks i gatunek gleby")
    texture_note: str | None = Field(None, description="Powód braku frakcji / mapy glebowo-rolniczej, np. 'SoilGrids nie odpowiada'")
    consistency: "SoilConsistency | None" = Field(None, description="Czy źródła gleby się zgadzają (mapa glebowo-rolnicza, IUNG, SoilGrids)")
    source_tag: SourceTag


SoilSourceKey = Literal["mapa_glebowo_rolnicza", "iung", "soilgrids"]


class SoilCategoryVote(Contract):
    """Kategoria agronomiczna gleby (I bardzo lekka … IV ciężka) według jednego źródła."""

    source: SoilSourceKey
    source_label: str = Field(description="Np. 'Mapa glebowo-rolnicza 1:5000 (GUGiK)'")
    category: int | None = Field(None, ge=1, le=4, description="Kategoria I–IV (jak kategorie podatności IUNG)")
    description: str = Field(description="Np. 'piasek gliniasty lekki – gleba lekka'")


class SoilConsistency(Contract):
    """Zgodność źródeł gleby. Kolejność ważności: mapa glebowo-rolnicza > IUNG > SoilGrids (D49)."""

    status: Literal["ok", "conflict"]
    note: str = Field(description="Krótkie wyjaśnienie dla rolnika")
    basis: SoilSourceKey | None = Field(None, description="Źródło kategorii gleby i WOD użytych w obliczeniach")
    category_used: int | None = Field(None, ge=1, le=4, description="Kategoria gleby użyta w modelu wody")
    by_source: list[SoilCategoryVote] = Field(default_factory=list)


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


class OrganicMatter(Contract):
    """A24: próchnica wierzchniej warstwy gleby – szacunek z węgla organicznego SoilGrids (0–30 cm) × 1,72.
    Informacyjnie – nie zmienia pojemności wodnej (WOD) ani bilansu."""

    value_pct: float = Field(description="Próchnica, % (węgiel organiczny × 1,72)")
    class_key: Literal["bardzo_niska", "niska", "srednia", "wysoka"]
    class_label: str = Field(description="bardzo niska / niska / średnia / wysoka")
    sentence: str = Field(description="Np. 'Próchnica: ok. 1,6% (niska) – szacunek SoilGrids, siatka ok. 250 m.'")
    source_tag: SourceTag


class DrySpellStats(Contract):
    """A24: najdłuższy okres bez opadu (dni z opadem < 1 mm) w oknie i na tle tego samego okna w 10 latach."""

    window_from: dt.date
    window_to: dt.date
    longest_days: int
    longest_from: dt.date | None = None
    longest_to: dt.date | None = None
    spells_10d: int = Field(description="Ile było okresów bez opadu trwających co najmniej 10 dni")
    usual_days: int | None = Field(None, description="Mediana najdłuższego okresu w poprzednich latach")
    longer_in_years: int | None = Field(None, description="W ilu z poprzednich lat najdłuższy okres był dłuższy")
    of_years: int = 0
    sentence: str
    source_tag: SourceTag


class Heat(Contract):
    """A24: dni upalne (temperatura maksymalna ≥ 30°C) i gorące (≥ 25°C) w sezonie na tle 10 lat – informacyjnie."""

    window_from: dt.date
    window_to: dt.date
    days_30: int
    days_25: int
    usual_days_30: int | None = None
    usual_days_25: int | None = None
    of_years: int = 0
    sensitive_days_30: int | None = Field(None, description="Dni ≥ 30°C w fazie wrażliwej wybranej uprawy")
    sensitive_phase_label: str | None = None
    sentence: str
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
    summary: str | None = Field(None, description="Proste zdanie, np. 'Ten rok jest suchszy niż zwykle – suszej było tylko w 2 z ostatnich 10 lat.'")
    details: str | None = Field(None, description="Szczegóły liczbowe: 'Od 1 marca do …: spadło minus wyparowało = −228 mm; średnio …'")
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

IrrigationStatus = Literal["zalecane", "niepotrzebne", "nieuzasadnione_w_fazie", "nie_praktykowane", "informacyjne",
                           "brak_danych"]
"""nie_praktykowane – uprawy, których w Polsce się nie nawadnia (zboża, rzepak, strączkowe): bez dawek (D48);
informacyjne – uprawy nawadniane rzadko (kukurydza, tytoń) przy niedoborze wody: bez dawek, tylko informacja (D64, D67)."""

IrrigationPractice = Literal["not_practiced", "optional", "common"]
"""Nawadnianie w praktyce w Polsce: nie stosuje się / rzadko (gdy jest woda i sprzęt) / typowe."""


class CropSeason(Contract):
    phase: CropPhase
    phase_label: str = Field(description="Np. 'pełnia rozwoju', 'po zbiorze'")
    season_year: int = Field(description="Rok sezonu, którego dotyczą dni stresu")
    season_start: dt.date = Field(description="Siew / wznowienie wegetacji")
    harvest: dt.date = Field(description="Typowy termin zbioru w Polsce (koniec sezonu modelu)")
    day_of_season: int | None = Field(None, description="Dzień sezonu w dacie analizy (1 = siew / wznowienie)")
    sensitive: bool = Field(description="Faza wrażliwa na niedobór wody – liczymy stres, możliwe zalecenie nawadniania")
    root_depth_m: float | None = Field(None, description="Głębokość korzeni w modelu w dacie analizy")
    sowing_date: dt.date | None = Field(None, description="A21: data siewu podana przez rolnika i użyta w modelu")
    sowing_note: str | None = Field(None, description="A21: np. 'data siewu poza typowym zakresem – użyto typowej'")


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
    practice: IrrigationPractice | None = Field(None, description="Czy tę uprawę w Polsce się nawadnia")
    source_tag: SourceTag


# ── Stan działki bez uprawy (A5b-1, punkt 1 przepływu panelu) ───────────────────────────────


class FieldState(Contract):
    """Stan wody na działce niezależnie od uprawy: zapas wody w profilu ~1 m pod pokryciem referencyjnym FAO-56
    (trawa, Kc = 1 – ta sama powierzchnia, dla której liczy się ET0 i KBW), bilans opad − ET0 z ostatnich 30 dni
    na tle 10 lat i status „stan wody na działce”. Liczony zawsze (z uprawą i bez), null dla gruntu nierolnego."""

    status: OverallStatus
    cover: str = Field(description="Założone pokrycie, np. 'pokrycie referencyjne FAO-56 (trawa, Kc = 1)'")
    soil_water_pct: Indicator = Field(description="Woda dostępna w profilu ~1 m, %")
    soil_water_mm: Indicator = Field(description="Woda dostępna w profilu ~1 m, mm")
    soil_water: SoilWaterState = Field(description="Opis i porównanie z tym samym dniem w 10 latach")
    series_start: dt.date = Field(description="Początek przebiegu (1 listopada – początek roku hydrologicznego)")
    series: list[SeriesPoint] = Field(description="Woda dostępna w profilu, % – dzień po dniu od series_start")
    series_band: list[BandPoint] = Field(description="Ten sam okres w 10 poprzednich latach: min / max / średnia, %")
    balance_30d: Indicator = Field(description="Bilans opad − ET0 z ostatnich 30 dni z danymi, mm")
    balance_30d_rank: BalanceRank | None = Field(None, description="W ilu z 10 lat bilans 30 dni był niższy")
    source_tag: SourceTag


# ── Ranking „Co tu posiać?” (A5b-2a) ────────────────────────────────────────────────────────

RankingCropId = Literal[
    "kukurydza_ziarno", "kukurydza_kiszonka", "rzepak", "ziemniak", "burak_cukrowy", "straczkowe", "warzywa",
    "drzewa_owocowe", "krzewy_owocowe", "truskawki", "pszenica_ozima", "zyto", "pszenzyto_ozime", "jeczmien_ozimy",
    "jeczmien_jary", "owies", "lubin",
]
"""Uprawy w rankingu (crops.csv, in_ranking = tak): 10 upraw IUNG + 7 gatunków (zboża, łubin)."""

SuggestionCategory = Literal["polecane", "mozliwe", "odradzane"]
"""✅ polecane / 🟡 możliwe / ❌ odradzane."""

SoilSuitability = Literal["odpowiednia", "neutralna", "nieodpowiednia"]
RotationStatus = Literal["ok", "plus", "ostrzezenie", "naruszenie", "brak_historii"]


class RotationCheck(Contract):
    """Płodozmian dla uprawy wg historii pola: naruszenie = za krótka przerwa (uprawa odradzana)."""

    status: RotationStatus
    notes: list[str] = Field(default_factory=list, description="Zdania dla rolnika, np. 'Zboże po zbożu – więcej chorób…'")


class YearYield(Contract):
    year: int
    relative: float = Field(ge=0, le=1, description="Plon względny Ya/Ym w tym sezonie (1 = bez strat z braku wody)")
    yield_t_ha: float | None = None
    water_deficit_mm: float | None = Field(None, description="Niedobór wody w sezonie: ETc − ETa, mm")


class PeriodDay(Contract):
    date: dt.date
    precip_mm: float
    et0_mm: float
    balance_cum_mm: float = Field(description="Bilans (opad − ET0) narastająco od początku okresu, mm")


class PeriodSummary(Contract):
    """A9b: podsumowanie okresu (period=30d|since_sowing|season albo date_from + date_to)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: dt.date = Field(alias="from", description="Początek okresu")
    to: dt.date = Field(description="Koniec okresu (≤ ostatni dzień z danymi przed datą analizy)")
    label: str = Field(description="Np. 'Ostatnie 30 dni (23.10–21.11.2026)'")
    precip_mm: float
    et0_mm: float
    balance_mm: float
    normal_balance_mm: float = Field(description="Średni bilans tego samego okresu w 10 poprzednich latach, mm")
    percentile: float = Field(description="W ilu % z 10 poprzednich lat było suszej (niższy bilans) niż teraz")
    sentence: str
    stress_days: int | None = Field(None, description="Dni stresu wodnego uprawy w okresie (tylko z uprawą)")
    daily: list[PeriodDay] = Field(default_factory=list)
    requested_to: dt.date | None = Field(None, description="A17: koniec okresu wybrany przez rolnika")
    data_until: dt.date | None = Field(None, description="A17: ostatni dzień okresu z pomiarami (NASA / IMGW)")
    filled_days: int = Field(0, description="A17: ile ostatnich dni okresu uzupełniono danymi modelu Open-Meteo")
    note: str | None = Field(None, description="A17: nota dla rolnika, gdy pomiary kończą się przed końcem okresu")
    dry_spell: "DrySpellStats | None" = Field(None, description="A24: najdłuższy okres bez opadu w tym okresie")


class CropRevenue(Contract):
    """A12: przychód z pola wg cen skupu GUS (bez kosztów, bez dopłat)."""

    price_zl_t: float = Field(description="Średnia cena skupu, zł/t (3 ostatnie lata, województwo działki)")
    price_source: str = Field(description="Np. 'GUS – ceny skupu, woj. podlaskie, 2023–2025'")
    typical_zl: float = Field(description="Przychód w typowym roku, zł (do 100 zł)")
    revenue_range: list[float] | None = Field(None, description="A21: przychód w typowym roku [min, max] z wariantów "
                                                                "opadu i pojemności gleby, zł (do 100 zł)")
    weak_year_zl: float = Field(description="Przychód w słabym roku, zł (do 100 zł)")
    for_area_ha: float = Field(description="Powierzchnia, dla której liczono, ha")


class PriceNow(Contract):
    """A12: bieżąca cena (ZSRIR MRiRW, tydzień) – tylko z ręcznie przepisanego biuletynu."""

    crop_id: str
    zl_t: float
    week: str = Field(description="Np. '10–16.11.2026'")
    source: str
    url: str | None = None


class CultivatedArea(Contract):
    value_ha: float
    estimated: bool = Field(description="True = powierzchnia działki × udział gruntów rolnych wg IUNG (oszacowanie)")
    note: str


class CropSuggestion(Contract):
    crop_id: RankingCropId
    label: str
    revenue: CropRevenue | None = Field(None, description="A12: przychód z pola wg cen skupu GUS (null = brak ceny)")
    revenue_note: str | None = Field(None, description="A12b: powód braku ceny (gdy revenue = null), np. 'cena z umowy z cukrownią'")
    yield_typical_range: list[float] | None = Field(None, description="A21: plon typowy [min, max] t/ha z wariantów opadu i gleby")
    yield_weak_range: list[float] | None = Field(None, description="A21: plon w słabym roku [min, max] t/ha")
    drought_risk_range: list[int] | None = Field(None, description="A21: lata ze stratą > 20% plonu [min, max] z wariantów")
    group_id: str = Field(description="Uprawa IUNG, której modelem wody liczony jest gatunek, np. 'zboza_ozime'")
    category: SuggestionCategory
    category_label: str
    rank: int = Field(description="Miejsce w grupie (1 = najlepsza)")
    score: float = Field(description="Ocena do kolejności (plon względny, stabilność, gleba, płodozmian)")
    reason: str = Field(description="JEDNO zdanie uzasadnienia prostym językiem")
    yield_typical_t_ha: float | None = Field(None, description="Typowy plon – mediana z 10 lat, t/ha (bez nawadniania)")
    yield_weak_t_ha: float | None = Field(None, description="Plon w słabym roku – najgorszy z 10 lat, t/ha")
    weak_year: int = Field(description="Który to był rok")
    yield_potential_t_ha: float | None = Field(None, description="Plon potencjalny Ym (GUS × gleba), t/ha")
    gus_mean_t_ha: float | None = Field(None, description="Średni plon GUS w województwie z 10 lat, t/ha")
    relative_yield_median: float = Field(ge=0, le=1)
    relative_yield_weak: float = Field(ge=0, le=1)
    drought_risk_years: int = Field(ge=0, description="W ilu latach strata plonu > 20%")
    years_simulated: int = Field(description="Z ilu pełnych sezonów (zwykle 10)")
    total_typical_t: float | None = Field(None, description="Typowy plon z całej powierzchni uprawy, t")
    total_weak_t: float | None = Field(None, description="Plon w słabym roku z całej powierzchni, t")
    price: None = Field(None, description="Miejsce na cenę skupu (później) – na razie null")
    soil_suitability: SoilSuitability
    soil_suitability_label: str
    rotation: RotationCheck
    irrigation_practice: IrrigationPractice
    drought_sensitivity: Literal["niska", "srednia", "wysoka"]
    confidence: Confidence
    confidence_note: str | None = Field(None, description="Dlaczego pewność niższa, np. 'Ky to szacunek'")
    notes: list[str] = Field(default_factory=list)
    yields_by_year: list[YearYield]
    source_tags: list[SourceTag]


class SuggestionGroup(Contract):
    key: Literal["polowe", "wieloletnie"]
    label: str
    items: list[CropSuggestion] = Field(description="Od najlepszej: polecane → możliwe → odradzane")


class PerennialSuggestion(Contract):
    """Uprawa wieloletnia – bez kategorii ✅/🟡/❌ (inwestycja na lata, osobna analiza opłacalności), niska pewność."""

    crop_id: RankingCropId
    label: str
    yield_typical_t_ha: float | None = None
    yield_weak_t_ha: float | None = None
    weak_year: int
    drought_risk_years: int = Field(ge=0)
    years_simulated: int
    total_typical_t: float | None = None
    total_weak_t: float | None = None
    soil_suitability: SoilSuitability
    soil_suitability_label: str
    irrigation_practice: IrrigationPractice
    confidence: Confidence = "ograniczona"
    note: str = Field(description="Np. 'Wymaga osobnej analizy opłacalności…'")
    source_tags: list[SourceTag] = Field(default_factory=list)


class PerennialSection(Contract):
    label: str = Field(description="'Uprawy wieloletnie – inwestycja na lata'")
    note: str = Field(description="Wymaga osobnej analizy opłacalności – nie oceniamy jak upraw polowych")
    items: list[PerennialSuggestion]


AlternativeRelation = Literal["lepsza", "podobna"]


class ChoiceItem(Contract):
    """Uprawa wybrana przez rolnika (planned_crops) – ocena na tej działce (A5e, D77)."""

    crop_id: RankingCropId
    label: str
    revenue: CropRevenue | None = Field(None, description="A12: przychód z pola (null = brak ceny)")
    category: SuggestionCategory | None = Field(None, description="null = uprawa wieloletnia (bez oceny ✅/🟡/❌)")
    category_label: str | None = None
    perennial: bool = False
    requested_id: str | None = Field(None, description="Co rolnik podał – uprawa albo grupa (np. 'zboza_ozime')")
    group_note: str | None = Field(None, description="Dla grupy: 'Z grupy zboża ozime najlepiej wypada: żyto.'")
    yield_typical_t_ha: float | None = None
    total_typical_t: float | None = Field(None, description="Typowy plon z całej powierzchni uprawy, t")
    yield_weak_t_ha: float | None = None
    total_weak_t: float | None = None
    weak_year: int | None = None
    drought_risk_years: int = Field(ge=0, description="W ilu latach strata plonu > 20%")
    years_simulated: int
    rotation: RotationCheck = Field(description="Uwagi płodozmianu z historii pola (crop_history)")
    why: str = Field(description="JEDNO zdanie: gleba / susza / przedplon – bez powtarzania liczb z tabeli")
    confidence: Confidence


class AlternativeItem(Contract):
    """Uprawa lepsza lub podobna od wyboru rolnika na tej działce (z uwzględnieniem historii pola)."""

    crop_id: RankingCropId
    label: str
    revenue: CropRevenue | None = Field(None, description="A12: przychód z pola (null = brak ceny)")
    category: SuggestionCategory
    category_label: str
    relation: AlternativeRelation = Field(
        description="lepsza = mniej lat ze stratą > 20% przy podobnym plonie względnym; podobna = tylko gdy wybór jest ❌ "
                    "wyłącznie przez płodozmian (podobne ryzyko suszy, bez problemu z przerwą)")
    yield_typical_t_ha: float | None = None
    total_typical_t: float | None = None
    drought_risk_years: int = Field(ge=0)
    years_simulated: int
    why: str = Field(description="Np. 'Po pszenicy ozimej rzepak – dobry przedplon.'")


class NotRecommendedItem(Contract):
    crop_id: RankingCropId
    label: str
    reason: str = Field(description="JEDEN powód, np. 'ta uprawa rosła 2 lata temu, potrzeba 3 lat przerwy'")


class CropSuggestions(Contract):
    """Ranking upraw dla tej działki i gleby na pogodzie z 10 sezonów. Plony zawsze BEZ nawadniania."""

    seasons: list[int] = Field(description="Sezony użyte w symulacji")
    groups: list[SuggestionGroup] = Field(description="Od A5b-2b tylko „uprawy polowe” (wieloletnie – w `perennials`)")
    perennials: PerennialSection | None = Field(None, description="Uprawy wieloletnie – osobno, bez kategorii, niska pewność")
    area: CultivatedArea
    choice: list[ChoiceItem] = Field(default_factory=list, description="Wybór rolnika (planned_crops) – pusta lista, gdy nie podano")
    choice_summary: str | None = Field(None, description="Jedno zdanie oceny wyboru, np. 'Twój wybór pasuje do tej działki.'")
    choice_notes: list[str] = Field(default_factory=list, description="Uprawy z planu, których nie ma w rankingu (chmiel, tytoń)")
    alternatives: list[AlternativeItem] = Field(
        default_factory=list, description="2–3 uprawy lepsze lub podobne od wyboru (puste bez wyboru albo gdy wybór jest najlepszy)")
    not_recommended: list[NotRecommendedItem] = Field(
        default_factory=list, description="Uprawy odradzane (bez wybranych) – każda z jednym powodem")
    top_ids: list[RankingCropId] = Field(default_factory=list, description="Top 5 upraw nieodradzanych (bez wyboru rolnika)")
    crop_history: list[str] = Field(default_factory=list, description="Historia upraw z zapytania (0 = rok temu)")
    rotation_hint: str | None = Field(None, description="Bez historii: 'Podaj, co rosło w ostatnich latach…'")
    note: str
    limitations: list[str] = Field(default_factory=list)
    ranges_pending: bool = Field(False, description="A21: widełki (pola *_range) jeszcze się liczą w tle – ponów "
                                                    "zapytanie za chwilę (wynik z pamięci)")
    compute_ms: int | None = None
    source_tag: SourceTag


# ── Werdykt działki (A5b-2b) ────────────────────────────────────────────────────────────────

VerdictKind = Literal["gleba", "opady", "teren", "rosliny", "uprawy", "woda", "uprawa_wybrana"]
VerdictLevel = Literal["ok", "warn", "bad"]
VerdictStatementLevel = Literal["ok", "warn", "bad", "info"]


class VerdictStatement(Contract):
    kind: VerdictKind
    level: VerdictStatementLevel = Field(
        description="ok #5BB37F / warn #E8B931 / bad #C8453B; info #2F80C9 – pozycja „woda” (lista działań, bez oceny)")
    text: str = Field(description="1–2 proste zdania z liczbami (szablony rules/verdict.yaml)")
    numbers: dict[str, float | int | str | None] = Field(default_factory=dict, description="Liczby użyte w zdaniu")


class VerdictCrop(Contract):
    crop_id: RankingCropId
    label: str
    reason: str | None = Field(None, description="Dla ❌ – jeden powód, np. 'za mało wody na tej glebie'")


class Verdict(Contract):
    """Werdykt działki w 10 sekund: gdzie dobrze, gdzie źle, co siać, czego nie siać, co zrobić z wodą.
    Deterministyczny – te same dane dają te same zdania (bez AI)."""

    headline: str = Field(description="Jedno zdanie ogólne, np. 'Dobra działka z wilgotnym obniżeniem'")
    level: VerdictLevel
    statements: list[VerdictStatement] = Field(description="4–6 pozycji: gleba, opady, teren, uprawy, woda, uprawa_wybrana")
    crops_good: list[VerdictCrop] = Field(default_factory=list, description="✅ 2–4 najlepsze uprawy polowe")
    crops_bad: list[VerdictCrop] = Field(default_factory=list, description="❌ odradzane (z jednym powodem)")
    note: str = Field(description="Skąd zdania: obliczenia z danych działki, bez modelu językowego")


class ApproximateArea(Contract):
    """Analiza po punkcie bez granic działki (ULDK nie odpowiada / punkt poza znanymi działkami)."""

    center: list[float] = Field(description="[lon, lat] klikniętego punktu")
    side_m: float = Field(description="Bok kwadratu, m (100 m = 1 ha)")
    area_ha: float
    reason: str = Field(description="Dlaczego obszar przybliżony, np. 'ULDK GUGiK: usługa chwilowo ogranicza ruch'")
    note: str = Field(description="'Obszar przybliżony – brak dokładnych granic działki…'")
    voivodeship_note: str | None = Field(None, description="Jak ustalono województwo (do plonów GUS)")


# ── Teren i spływ wody z NMT (A6) ───────────────────────────────────────────────────────────

TerrainZoneKey = Literal["sucha_gorka", "stok", "plasko", "mokry_dolek"]
TerrainRating = Literal["dobrze", "uwaga", "zle"]


class TerrainZone(Contract):
    """Strefa terenu z udziałem w działce i oceną z glebą (reguły: analysis/rules/teren_gleba.yaml)."""

    key: TerrainZoneKey
    label: str = Field(description="Dla rolnika: 'górka – sucho', 'stok – woda ucieka', 'płasko – dobre warunki', 'dołek – woda stoi'")
    share_pct: float = Field(ge=0, le=100)
    color: str = Field(description="Kolor strefy na pasku i mapie, np. '#8B6B4A'")
    rating: TerrainRating | None = Field(None, description="Ocena strefy z glebą; null, gdy strefy praktycznie nie ma (< 1%)")
    sentence: str | None = Field(None, description="Jedno zdanie dla rolnika, np. '20% działki to dołek – wiosną stoi woda.'")


class TerrainOutlet(Contract):
    """Miejsce, którędy woda opuszcza działkę („tu woda ucieka”)."""

    direction: str = Field(description="Np. 'południowy zachód'")
    direction_short: str = Field(description="Np. 'SW'")
    azimuth_deg: float | None = None
    share_of_parcel_pct: float = Field(description="Jaka część działki odprowadza wodę tym miejscem, %")
    location: list[float] = Field(description="[lon, lat] (EPSG:4326)")


class TerrainDepression(Contract):
    """Największe zagłębienie bez odpływu (tu zbiera się woda)."""

    area_m2: float | None = None
    max_depth_m: float | None = None
    volume_m3: float | None = None
    catchment_m2: float | None = None
    location: list[float] | None = Field(None, description="[lon, lat] najgłębszego miejsca")


class TerrainDetails(Contract):
    """Szczegóły „dla dociekliwych” – metoda i liczby techniczne."""

    grid_step_m: float
    smoothing_sigma_m: float
    nmt_points: int | None = None
    nmt_missing_pct: float | None = None
    twi_mean: float | None = Field(None, description="Wskaźnik wilgotności topograficznej TWI = ln(a / tan β), średnia w działce")
    twi_p90: float | None = None
    steep_share_pct: float | None = Field(None, description="Udział działki o spadku > 5%")
    flow_consistency: float | None = Field(None, description="1 = cała działka spada w jedną stronę")
    method: str = Field(description="Np. 'priority-flood (Barnes 2014), D8 + D-infinity (TWI), spadek: Horn 3×3'")


HydroStatus = Literal["pending", "ok", "none"]
HydroKind = Literal["rzeka", "ciek", "row", "kanal", "zbiornik"]
GaugeState = Literal["niski", "sredni", "wysoki"]


class HydroFeature(Contract):
    """A9: obiekt wodny ≤ 500 m od działki (OSM)."""

    kind: HydroKind
    name: str | None = None
    distance_m: float = Field(description="Odległość od granicy działki, m")
    toward_outflow: bool = Field(description="Czy obiekt leży tam, dokąd woda odpływa z działki (teren, NMT)")


class HydroGauge(Contract):
    """A9: najbliższy wodowskaz IMGW z bieżącym stanem (tylko analiza na dziś)."""

    name: str
    river: str
    distance_km: float
    level_cm: float
    state: GaugeState = Field(description="Względem P33 / P66 stanu z tego samego miesiąca w latach 2016–2025")
    date: str


class HydroSource(Contract):
    name: str
    url: str


class Hydro(Contract):
    """A9: woda w okolicy – cieki, rowy, kanały, zbiorniki w promieniu 500 m + wodowskaz; pending → GET /api/hydro."""

    status: HydroStatus
    sentence: str | None = None
    features: list[HydroFeature] = Field(default_factory=list)
    gauge: HydroGauge | None = None
    sources: list[HydroSource] = Field(default_factory=list)


class TerrainPending(Contract):
    """A9: teren liczony w tle – dociągnij GET /api/terrain (albo POST z geometry)."""

    status: Literal["pending"] = "pending"


class Terrain(Contract):
    """Teren i spływ wody z NMT GUGiK (A6) – strefy, spadki, odpływ, zagłębienia, ocena z glebą, zdania dla rolnika."""

    zones: list[TerrainZone] = Field(description="Zawsze 4 strefy: górka, stok, płasko, dołek (kolejność stała)")
    zone_share_pct: dict[str, float] = Field(description="Udziały stref, %: sucha_gorka, stok, plasko, mokry_dolek")
    soil_group: Literal["lekka", "srednia", "ciezka", "organiczna", "zwiezla", "nieznana"] = Field(
        description="Gleba użyta w ocenie stref – etykieta ważona udziałem (A5b-2b); 'zwiezla' – już nieużywane")
    soil_group_label: str = Field(description="Np. 'gleba średnia: glina lekka pylasta 78%, piasek gliniasty lekki 22%'")
    summary: str = Field(description="2–3 zdania o terenie prostym językiem")
    relief_m: float | None = Field(None, description="Różnica wysokości w działce, m")
    elev_min_m: float | None = None
    elev_max_m: float | None = None
    slope_mean_pct: float | None = None
    slope_max_pct: float | None = None
    main_flow_direction: str | None = Field(None, description="Główny kierunek spływu, np. 'południowy zachód'")
    main_flow_direction_short: str | None = None
    main_flow_azimuth_deg: float | None = None
    outlets: list[TerrainOutlet] = Field(default_factory=list)
    inflow_from_outside_m2: float | None = Field(None, description="Powierzchnia spoza działki, z której woda spływa na działkę")
    inflow_from_outside_ratio: float | None = Field(None, description="Dopływ z zewnątrz / powierzchnia działki")
    depressions_count: int = 0
    depressions_volume_m3: float | None = None
    largest_depression: TerrainDepression | None = None
    details: TerrainDetails
    confidence: Confidence
    limitations: list[str] = Field(default_factory=list)
    source_tag: SourceTag


# ── C. Dlaczego? ────────────────────────────────────────────────────────────────────────────


class Cause(Contract):
    factor: CauseFactor
    title: str = Field(description="Np. 'Mało opadów'")
    share: float = Field(ge=0, le=1, description="Udział w problemie (paski od największego)")
    informational: bool = Field(False, description="A24: pozycja informacyjna (bez udziału %) – teren, okres bez "
                                                   "deszczu, upał, próchnica; nie zmienia policzonego bilansu")
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
    data_date: dt.date | None = Field(description="Data danych – nigdy późniejsza niż data analizy (A20)")
    fetched_at: dt.date | None = Field(None, description="A20: kiedy pobrano, gdy później niż data analizy "
                                                         "(np. granice działki pobrane dziś dla analizy z 2018 r.)")
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


SatelliteStatus = Literal["ok", "pending", "brak_danych"]
NdviClass = Literal["gleba", "slaba", "umiarkowana", "gesta"]
NdmiClass = Literal["sucho", "srednio", "dobrze"]
SatelliteTrend = Literal["lepiej", "podobnie", "gorzej"]


class SatelliteScene(Contract):
    date: dt.date
    scene_id: str
    ndvi: float | None = None
    ndmi: float | None = None
    valid_pct: float = Field(description="Udział ważnych pikseli (roślinność / gleba wg maski SCL) w obrysie, %")
    cloud_pct: float = Field(description="Chmury i cienie chmur w obrysie, %")


class SatelliteSeriesPoint(Contract):
    date: dt.date
    ndvi: float | None = None
    ndmi: float | None = None
    valid_pct: float


class Satellite(Contract):
    """Sentinel-2 L2A dla działki (A11): kondycja (NDVI) i wilgotność roślin (NDMI) z ostatniej czystej sceny,
    porównanie z tą samą porą rok temu, zdanie dla rolnika. W /api/analysis tylko z cache – inaczej status „pending”
    i frontend dociąga GET /api/satellite."""

    status: SatelliteStatus
    date: dt.date | None = Field(None, description="Data sceny („zdjęcie satelitarne z 16.11.2026”)")
    scene_id: str | None = None
    ndvi: float | None = Field(None, description="NDVI – mediana w obrysie (kondycja roślin, −1…1)")
    ndmi: float | None = Field(None, description="NDMI – mediana w obrysie (wilgotność roślin, −1…1)")
    ndvi_class: NdviClass | None = None
    ndvi_label: str | None = Field(None, description="Np. 'gęsta zieleń'")
    ndmi_class: NdmiClass | None = Field(None, description="Tylko w sezonie (IV–IX) i przy NDVI ≥ 0,5")
    ndmi_label: str | None = None
    valid_pct: float | None = None
    cloud_pct: float | None = None
    last_year: SatelliteScene | None = Field(None, description="Najbliższa czysta scena z tej samej pory rok wcześniej (±20 dni)")
    ndvi_change: float | None = Field(None, description="NDVI teraz − rok temu")
    trend: SatelliteTrend | None = None
    level: VerdictStatementLevel | None = Field(None, description="ok / warn / bad; info – poza sezonem bez anomalii")
    in_season: bool | None = None
    sentence: str | None = Field(None, description="Zdanie dla rolnika z datą sceny")
    warning: str | None = Field(None, description="Np. scena częściowo zachmurzona albo brak czystej sceny")
    series: list[SatelliteSeriesPoint] = Field(default_factory=list, description="Szereg 12 mies. (1 punkt / 15 dni) – tylko z cache")
    series_note: str | None = None
    layers: list[Literal["kondycja", "wilgotnosc"]] = Field(default_factory=list, description="Dostępne warstwy mapy")
    downloaded_mb: float | None = Field(None, description="Ile pobrano przy liczeniu (tryb na żywo: ok. 10 MB)")
    compute_s: float | None = None
    cached: bool = False
    note: str | None = None
    source_tag: SourceTag


PrecipMain = Literal["imgw", "imgw_daleko", "nasa"]
PrecipAgreement = Literal["zgodne", "roznia_sie", "mocno_sie_roznia", "brak_danych"]


class PrecipStation(Contract):
    code: str = Field(description="Kod stacji IMGW (9 cyfr)")
    name: str = Field(description="Np. 'Burzyn'")
    kind: Literal["synop", "klimat", "opad"]
    kind_label: str = Field(description="stacja synoptyczna / klimatologiczna / posterunek opadowy")
    distance_km: float
    weight: float = Field(description="Waga IDW (1/d², suma = 1)")
    coverage_pct: float = Field(description="Udział dni z pomiarem w okresie analizy, %")
    lon: float
    lat: float


class PrecipWindow(Contract):
    """Porównanie sum opadu w oknie (doba IMGW 6:00–6:00 – porównujemy sumy, nie dni)."""

    key: Literal["sezon", "ostatnie_30_dni", "wielolecie"]
    label: str
    start: dt.date
    end: dt.date
    imgw_mm: float | None = None
    nasa_mm: float | None = None
    difference_pct: float | None = Field(None, description="NASA względem stacji IMGW, % (dodatnie = NASA pokazuje więcej)")
    rating: PrecipAgreement


class PrecipSources(Contract):
    """Skąd opad dla tej działki (A7): stacje IMGW (źródło główne) i porównanie z NASA POWER."""

    main: PrecipMain = Field(description="imgw – stacje ≤ 30 km; imgw_daleko – stacje 30–50 km (pewność niżej); nasa – brak stacji")
    main_label: str
    stations: list[PrecipStation] = Field(default_factory=list, description="Do 3 najbliższych stacji z danymi (IDW)")
    nasa_factor: float | None = Field(None, description="Suma IMGW / suma NASA ze wspólnego okresu – korekta dni bez pomiaru")
    nasa_vs_imgw_pct: float | None = Field(None, description="O ile % NASA pokazuje więcej (+) / mniej (−) niż stacje, wspólne lata")
    common_days: int = 0
    filled_days: int = Field(0, description="Ostatnie dni bez pomiaru ze stacji – NASA przeliczona współczynnikiem")
    filled_from: dt.date | None = None
    filled_earlier_days: int = Field(0, description="Wcześniejsze dni bez pomiaru (lata sprzed magazynu, luki) – też przeliczona NASA")
    agreement: PrecipAgreement = Field(description="Zgodność źródeł: sezon od 1 marca i ostatnie 30 dni (gorsza z dwóch)")
    agreement_label: str
    windows: list[PrecipWindow] = Field(default_factory=list)
    sentence: str = Field(description="Najwyżej 2 zdania dla rolnika, np. 'Opady liczymy ze stacji IMGW Burzyn (27 km). …'")
    details: list[str] = Field(default_factory=list, description="A20: szczegóły źródeł (tryb Doradca) – porównanie "
                                                                 "z NASA w %, lata rozjazdu, uzupełnione dni")
    confidence_lowered: bool = Field(False, description="True: stacje daleko albo źródła mocno się różnią – pewność o poziom niżej")
    precip_disagreement: list[int] = Field(
        default_factory=list, description="A16: lata, w których suma IV–VII ze stacji IMGW różni się od NASA o > 30%")
    precip_disagreement_source: Literal["nasa", "station"] | None = Field(
        None, description="A16b: kto odstaje – 'nasa' (stacje zgodne z sąsiednimi ±25%, pewność bez zmian), "
                          "'station' (stacja odstaje od sąsiadów – wynik dla tych lat mniej pewny); null = brak lat")
    source_tag: SourceTag


class SeasonalBalanceYear(Contract):
    """Bilans wody (spadło minus wyparowało) od początku sezonu do tego samego dnia – jeden słupek wykresu „Na tle 10 lat”."""

    year: int
    balance_mm: float = Field(description="mm, zaokrąglone do całości – ta sama liczba w tekstach, raporcie i na wykresie")
    current: bool = Field(False, description="true = bieżący rok (słupek wyróżniony)")


class AnalysisRequest(Contract):
    """Treść POST /api/analysis i POST /api/report.pdf (A5c, D75): to samo co zapytanie GET, plus własny obrys pola.
    Dokładnie jedno z: `parcel_id`, para `lon` + `lat`, `geometry`."""

    parcel_id: str | None = Field(None, description="Pełny identyfikator działki ULDK (albo „obręb numer”)")
    lon: float | None = Field(None, description="Punkt na mapie (WGS84) – zamiast parcel_id")
    lat: float | None = None
    geometry: dict[str, Any] | None = Field(
        None, description="Własny obrys pola: GeoJSON Polygon w WGS84 ([lon, lat]), 0,05–200 ha, w Polsce, bez samoprzecięć")
    crop: str | None = None
    date: dt.date | None = None
    previous_crop: str | None = None
    crop_history: str | None = None
    cultivated_area_ha: float | None = None
    planned_crops: list[str] | None = Field(None, description="Co rolnik planuje posiać: 1–3 uprawy z rankingu (A5e)")
    period: Literal["30d", "since_sowing", "season"] | None = Field(None, description="A9b: okres podsumowania")
    date_from: dt.date | None = Field(None, description="A9b: własny zakres – początek")
    date_to: dt.date | None = Field(None, description="A9b: własny zakres – koniec (≤ data analizy)")
    sowing_date: dt.date | None = Field(None, description="A21: data siewu wybranej uprawy (RRRR-MM-DD) – model wody "
                                                          "startuje od niej zamiast od typowej (± 30 dni)")
    report_type: Literal["short", "full"] | None = Field(None, description="Tylko POST /api/report.pdf: short (domyślnie) | full")


class AnalysisResponse(Contract):
    parcel: Parcel
    crop: CropId | None = Field(description="null = analiza bez uprawy („Stan działki”)")
    previous_crop: PreviousCropId | None = Field(None, description="Uprawa w poprzednim roku (jeśli podana)")
    analysis_date: dt.date
    historical: bool = Field(description="True, gdy analysis_date < dziś (analiza historyczna)")
    generated_at: dt.datetime
    status: OverallStatus
    indicators: Indicators
    crop_season: CropSeason | None = Field(description="null bez uprawy")
    soil_water: SoilWaterState
    irrigation: IrrigationPlan | None = Field(description="null bez uprawy")
    soil: Soil
    field_state: FieldState | None = Field(None, description="Stan działki bez względu na uprawę (null: grunt nierolny / brak danych)")
    terrain: Terrain | TerrainPending | None = Field(
        None, description="Teren i spływ wody z NMT (null = brak danych, powód w terrain_note); A9: {status: pending} – "
                          "liczony w tle, GET /api/terrain")
    verdict: Verdict | None = Field(None, description="Werdykt działki (null: grunt nierolny / brak danych)")
    approximate_area: ApproximateArea | None = Field(None, description="Obszar przybliżony zamiast działki (analiza po punkcie)")
    terrain_note: str | None = Field(None, description="Dlaczego brak analizy terenu, np. 'NMT GUGiK nie odpowiada'")
    hydro: Hydro | None = Field(None, description="A9: woda w okolicy (z cache); {status: pending} → GET /api/hydro")
    price_now: list[PriceNow] | None = Field(None, description="A12: bieżące ceny ZSRIR (null = brak pliku z biuletynu)")
    period: PeriodSummary | None = Field(None, description="A9b: okres z zapytania (period / date_from + date_to); bez – null")
    suggestions: CropSuggestions | None = Field(None, description="Ranking „Co tu posiać?” (null: grunt nierolny / brak danych)")
    crop_history: list[str] = Field(default_factory=list, description="Historia upraw z zapytania: 1–3 lata, indeks 0 = rok temu (crop_id albo 'nie_wiem')")
    cultivated_area_ha: float | None = Field(None, description="Powierzchnia uprawy użyta w rankingu, ha (podana albo oszacowana)")
    planned_crops: list[str] = Field(default_factory=list, description="Co rolnik planuje posiać (z zapytania): uprawy z rankingu albo grupy (A5e)")
    seasonal_balance_by_year: list[SeasonalBalanceYear] = Field(
        default_factory=list, description="Bilans wody od początku sezonu do tego samego dnia: 10 lat + bieżący (słupki „Na tle 10 lat”)")
    seasonal_balance_mean_mm: float | None = Field(None, description="Średnia z lat porównawczych, mm (linia na wykresie)")
    seasonal_balance_label: str | None = Field(None, description="Okres bilansu, np. 'od 1 marca do 18 listopada'")
    weather_data_until: dt.date | None = Field(None, description="Ostatni dzień z danymi pogodowymi („dane pogodowe do 18.11”)")
    dry_spell: DrySpellStats | None = Field(None, description="A24: najdłuższy okres bez opadu w sezonie (od 1 marca)")
    heat: Heat | None = Field(None, description="A24: dni upalne w sezonie (informacyjnie)")
    precip_sources: PrecipSources | None = Field(None, description="Skąd opad: stacje IMGW, zgodność z NASA, zdanie dla rolnika (A7)")
    satellite: Satellite | None = Field(None, description="Sentinel-2 (A11): z cache albo {status: pending} – dociągnij GET /api/satellite")
    history: History
    causes: list[Cause] = Field(description="Od największego udziału")
    recommendations: list[Recommendation] = Field(description="retencja → agrotechnika → nawadnianie")
    reliability: Reliability
    steps: list[LoadingStep]


Soil.model_rebuild()
Recommendation.model_rebuild()
