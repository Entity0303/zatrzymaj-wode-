/**
 * KONTRAKT API – typy identyczne z backend/app/schemas/*.py (Pydantic).
 * Zmiany tylko po uzgodnieniu i w obu miejscach naraz (CLAUDE.md – Praca zespołowa).
 *
 * Zasady: każda liczba ma `source_tag`; brak danych = `value: null` + `kind: 'brak_danych'`
 * (nigdy 0 ani wymyślona wartość). Daty: 'YYYY-MM-DD', znaczniki czasu: ISO 8601.
 */

type ISODate = string
type ISODateTime = string

// ── schemas/parcel.py ───────────────────────────────────────────────────────────────────────

export type DataSource = {
  nazwa: string
  url: string
  pobrano?: string | null
  uwagi?: string | null
}

export type Parcel = {
  id: string
  wojewodztwo: string
  powiat: string
  gmina: string
  obreb: string
  numer: string
  teryt_gminy: string
  powierzchnia_ha: number
  geometria: GeoJSON.Polygon | GeoJSON.MultiPolygon
  zrodlo: DataSource
}

/** `detail` przy HTTP 409 */
export type ParcelCandidates = { message: string; total: number; candidates: Parcel[] }

/** `detail` przy HTTP 404 / 502 */
export type ErrorDetail = { source?: string | null; message: string }

// ── schemas/weather.py ──────────────────────────────────────────────────────────────────────

export type WeatherIcon = 'sun' | 'cloud-sun' | 'cloud' | 'fog' | 'drizzle' | 'rain' | 'snow' | 'storm' | 'unknown'

export type CurrentWeather = {
  czas: string | null
  temperatura: number | null
  opis: string
  ikona: WeatherIcon
  dzien: boolean
}

export type ForecastDay = {
  data: string
  opis: string
  ikona: WeatherIcon
  temp_max: number | null
  temp_min: number | null
  opad_mm: number | null
  parowanie_mm: number | null
  bilans_mm: number | null
}

export type Forecast = {
  lon: number
  lat: number
  teraz: CurrentWeather
  dni: ForecastDay[]
  bilans_okresu_mm: number | null
  zrodlo: DataSource
}

// ── schemas/analysis.py – GET /api/analysis?parcel_id=&crop=&date= ─────────────────────────

/** Dobrze / Uwaga / Ryzyko / Susza / Brak danych (SPEC 2.2) */
export type StatusLevel = 'ok' | 'warn' | 'risk' | 'danger' | 'no_data'

/** Etykiety pochodzenia liczb (SPEC 15.2) */
export type SourceKind = 'pomiar' | 'satelita' | 'obliczenia' | 'szacunek_modelu' | 'prognoza' | 'brak_danych'

export type Confidence = 'wysoka' | 'srednia' | 'ograniczona'

/** Kolejność w odpowiedzi zawsze: retencja → agrotechnika → nawadnianie */
export type RecommendationCategory = 'retencja' | 'agrotechnika' | 'nawadnianie'

/** 15 upraw IUNG SMSR (etykiety: lib/crops.ts) */
export type CropId =
  | 'zboza_ozime'
  | 'zboza_jare'
  | 'kukurydza_ziarno'
  | 'kukurydza_kiszonka'
  | 'rzepak'
  | 'rzepak_jesien'
  | 'ziemniak'
  | 'burak_cukrowy'
  | 'straczkowe'
  | 'warzywa'
  | 'drzewa_owocowe'
  | 'krzewy_owocowe'
  | 'truskawki'
  | 'chmiel'
  | 'tyton'

export type StepState = 'done' | 'active' | 'error' | 'pending'
export type SourceAvailability = 'ok' | 'czesciowo' | 'brak'
export type CauseFactor = 'opady' | 'parowanie' | 'gleba' | 'teren' | 'uprawa' | 'inne'

export type SourceTag = {
  kind: SourceKind
  /** data danych, np. zdjęcia satelitarnego (wymagana dla 'satelita') */
  date?: ISODate | null
  /** nazwa źródła, np. 'Sentinel-2 L2A' */
  source?: string | null
}

export type Indicator = {
  /** null = brak danych (nigdy 0 zamiast braku) */
  value: number | null
  unit?: string | null
  label?: string | null
  status?: StatusLevel
  note?: string | null
  source_tag: SourceTag
}

export type RiskIndicator = Indicator & { days_to_stress?: number | null }

export type SatelliteIndicator = Indicator & { index_value?: number | null }

export type Indicators = {
  soil_water_pct: Indicator
  soil_water_mm: Indicator
  risk_7d: RiskIndicator
  crop_health: SatelliteIndicator
  plant_moisture: SatelliteIndicator
  water_balance_season: Indicator
  soil_capacity: Indicator
}

export type OverallStatus = {
  level: StatusLevel
  score?: number | null
  headline: string
  summary: string
}

/** Faza uprawy w dacie analizy. Wrażliwe na niedobór (stres, nawadnianie): poczatkowa, rozwoj, pelnia */
export type CropPhase =
  | 'przed_siewem'
  | 'wschody_jesienne'
  | 'spoczynek_zimowy'
  | 'poczatkowa'
  | 'rozwoj'
  | 'pelnia'
  | 'dojrzewanie'
  | 'po_zbiorze'

export type IrrigationStatus = 'zalecane' | 'niepotrzebne' | 'nieuzasadnione_w_fazie' | 'brak_danych'

export type CropSeason = {
  phase: CropPhase
  /** np. 'pełnia rozwoju', 'po zbiorze' */
  phase_label: string
  season_year: number
  /** siew / wznowienie wegetacji */
  season_start: ISODate
  /** typowy termin zbioru w Polsce */
  harvest: ISODate
  /** dzień sezonu w dacie analizy (1 = siew / wznowienie) */
  day_of_season?: number | null
  /** faza wrażliwa na niedobór – liczymy stres, możliwe zalecenie nawadniania */
  sensitive: boolean
  root_depth_m?: number | null
}

/** Podsumowanie zakończonego sezonu uprawy */
export type SeasonSummary = {
  year: number
  stress_days: number | null
  /** średnia z 10 poprzednich sezonów */
  mean_prev_stress_days?: number | null
}

/** Stan wody w glebie w dacie analizy – także poza sezonem */
export type SoilWaterState = {
  /** strefa_korzeni – w fazach uprawy; profil (~1 m) – poza sezonem */
  scope: 'strefa_korzeni' | 'profil'
  depth_m: number
  /** np. 'poza sezonem – gleba odbudowuje zapas wody' */
  description: string
  /** ten sam dzień w 10 poprzednich latach: w ilu latach było MNIEJ wody niż teraz, z ilu */
  rank?: BalanceRank | null
  /** zakończony sezon (po zbiorze / przed siewem) */
  last_season?: SeasonSummary | null
}

export type IrrigationPlan = {
  status: IrrigationStatus
  /** np. '25 mm teraz, powtórz za ok. 5 dni' */
  message: string
  /** dawka jednorazowa zależna od gleby, nigdy > 35 mm */
  dose_mm?: number | null
  first_date?: ISODate | null
  /** co ile dni powtarzać */
  interval_days?: number | null
  /** łączny niedobór do uzupełnienia w 7 dniach */
  total_7d_mm?: number | null
  doses_7d?: number | null
  source_tag: SourceTag
}

/** Dlaczego ocena suszy rolniczej nie ma zastosowania (kody IUNG 11, 12, 13, 14, 5 łącznie > 50%) */
export type NonAgriculturalReason = 'las' | 'woda' | 'zabudowa' | 'drogi' | 'gleby_organiczne'

export type SoilShareItem = {
  /** kod IUNG: 1–4 kategorie podatności, 5 organiczne, 11 las, 12 woda, 13 zabudowa, 14 drogi/nieużytki */
  code: number
  label: string
  /** 0–1 */
  share: number
}

/** Gleba działki (SPEC 7.A, 15.1 „to nie jest grunt rolny”, 15.3) */
export type Soil = {
  dominant_code: number | null
  dominant_label: string | null
  shares: SoilShareItem[]
  /** udział gleb mineralnych użytków rolnych (kody 1–4), 0–1 */
  agricultural_share?: number | null
  /** woda dostępna dla roślin (WOD), mm */
  wod_mm?: number | null
  /** klasy bonitacyjne EGiB – tylko informacyjnie */
  classes?: string[] | null
  /** powód braku klas */
  classes_note?: string | null
  non_agricultural?: boolean
  non_agricultural_reason?: NonAgriculturalReason | null
  /** gotowy komunikat dla rolnika */
  non_agricultural_note?: string | null
  source_tag: SourceTag
}

export type SeriesPoint = { date: ISODate; value: number | null }

export type BandPoint = { date: ISODate; min: number | null; max: number | null; mean: number | null }

export type YearStress = { year: number; stress_days: number | null; is_current?: boolean }

export type MonthlyPrecip = { month: number; current_mm: number | null; mean_mm: number | null }

/** Pozycja bieżącego bilansu na tle lat porównawczych */
export type BalanceRank = {
  /** w ilu latach bilans był NIŻSZY niż teraz (0 = najgorszy) */
  lower_years: number
  /** z ilu lat porównawczych */
  of_years: number
}

/** Najdłuższy okres bez opadu (opad < 1 mm) w bieżącym sezonie */
export type DrySpell = { days: number; end_date?: ISODate | null }

export type History = {
  period_start: ISODate
  period_end: ISODate
  season_start: ISODate
  balance_cumulative: SeriesPoint[]
  balance_band: BandPoint[]
  stress_days_by_year: YearStress[]
  monthly_precip: MonthlyPrecip[]
  summary?: string | null
  /** bieżący bilans − średnia z lat porównawczych, mm */
  balance_deviation_mm?: number | null
  balance_rank?: BalanceRank | null
  longest_dry_spell?: DrySpell | null
  /** lata użyte w paśmie porównawczym */
  band_years?: number[]
  source_tag: SourceTag
}

export type Cause = {
  factor: CauseFactor
  title: string
  /** 0–1 */
  share: number
  description: string
  source_tag: SourceTag
}

export type Evidence = {
  name: string
  value: number | string | null
  unit?: string | null
  source: string
  date?: ISODate | null
}

export type Recommendation = {
  id: string
  category: RecommendationCategory
  title: string
  description: string
  why: string
  inputs: Evidence[]
  confidence: Confidence
  /** GeoJSON geometria miejsca (EPSG:4326) – „Pokaż na mapie” */
  location?: GeoJSON.Geometry | null
  rule_id?: string | null
  /** ważność w obrębie kategorii (większa = ważniejsza) */
  priority?: number
  /** pokazać w panelu działki (maks. 3: po jednej z kategorii); reszta – paszport */
  in_panel?: boolean
}

export type SourceStatus = {
  name: string
  used_for: string
  data_date: ISODate | null
  resolution?: string | null
  status: SourceAvailability
  note?: string | null
}

export type Completeness = { available: number; total: number }

export type Reliability = {
  confidence: Confidence
  reason: string
  sources: SourceStatus[]
  completeness: Completeness
  limitations: string[]
}

export type LoadingStep = {
  id: string
  label: string
  state: StepState
  note?: string | null
  duration_ms?: number | null
}

export type AnalysisResponse = {
  parcel: Parcel
  crop: CropId
  analysis_date: ISODate
  historical: boolean
  generated_at: ISODateTime
  status: OverallStatus
  indicators: Indicators
  crop_season: CropSeason
  soil_water: SoilWaterState
  irrigation: IrrigationPlan
  soil: Soil
  history: History
  causes: Cause[]
  recommendations: Recommendation[]
  reliability: Reliability
  steps: LoadingStep[]
}

// ── schemas/layers.py – GET /api/layers/{layer} (szkielet) ─────────────────────────────────

export type LayerKey = 'kondycja' | 'wilgotnosc' | 'teren' | 'splyw' | 'gleba'

export type RasterOverlay = {
  image_url: string
  /** lon_min, lat_min, lon_max, lat_max (EPSG:4326) */
  bbox: [number, number, number, number]
}

export type LayerResponse = {
  parcel_id: string
  layer: LayerKey
  analysis_date: ISODate
  raster?: RasterOverlay | null
  features?: GeoJSON.FeatureCollection | null
  value_range?: [number, number] | null
  source_tag: SourceTag
}

export type PointValue = { layer: LayerKey; text: string; value: number | null; source_tag: SourceTag }

// ── schemas/reports.py – raport PDF i zgłoszenia (szkielet) ────────────────────────────────

export type ReportRequest = { parcel_id: string; crop: CropId; date: ISODate }

export type ReportMeta = {
  report_id: string
  parcel_id: string
  crop: CropId
  analysis_date: ISODate
  generated_at: ISODateTime
  pdf_url: string
}

export type WaterObjectType = 'row' | 'ciek' | 'zbiornik'
export type InfraProblem =
  | 'drozny'
  | 'zarosniety'
  | 'zamulony'
  | 'zatkany_przepust'
  | 'uszkodzona_zastawka'
  | 'uszkodzona_skarpa'
  | 'zanieczyszczony'
export type WaterLevel = 'brak' | 'niski' | 'normalny' | 'wysoki'

export type InfraReportIn = {
  object_type: WaterObjectType
  object_id?: string | null
  lon: number
  lat: number
  problem: InfraProblem
  water_level?: WaterLevel | null
  description?: string | null
}

export type InfraReport = InfraReportIn & {
  id: string
  created_at: ISODateTime
  confirmations: number
  addressee: string
}
