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
  /** A5c: uldk – działka z ewidencji; drawn – pole narysowane przez rolnika; approximate – 1 ha wokół punktu (brak granic) */
  source?: 'uldk' | 'drawn' | 'approximate'
  /** np. „Pole narysowane przez rolnika” (null dla działki z ULDK) */
  name?: string | null
}

// ── Wyszukiwanie: GET /api/search?q= (A5c) ──────────────────────────────────────────────────

export type SearchKind = 'parcel' | 'place'
export type PlaceType = 'miejscowosc' | 'gmina' | 'obreb'
/** jak backend rozpoznał zapytanie */
export type QueryInterpretation = 'parcel_id' | 'obreb_numer' | 'name' | 'empty' | 'unrecognized'

export type SearchResult = {
  kind: SearchKind
  /** parcel: identyfikator ULDK; place: id źródła, np. „prng:139268” */
  id: string
  /** gotowy tekst do listy, np. „Tczów, gm. Tczów, pow. zwoleński, mazowieckie” */
  label: string
  /** parcel: „obręb numer”; place: nazwa miejscowości */
  name: string
  /** środek (WGS84) – do przybliżenia mapy; parcel: punkt wewnątrz działki */
  lon: number
  lat: number
  /** tylko parcel – do GET /api/analysis?parcel_id= */
  parcel_id?: string | null
  /** tylko place */
  type?: PlaceType | null
  /** np. „wieś”, „miasto”, „osada”, „gmina” */
  type_label?: string | null
  gmina?: string | null
  powiat?: string | null
  wojewodztwo?: string | null
  /** lon_min, lat_min, lon_max, lat_max (EPSG:4326) – do fitBounds; parcel: obrys działki */
  bbox?: [number, number, number, number] | null
  /** true = bbox wyznaczony wokół punktu (źródło podało tylko punkt) */
  bbox_approx?: boolean
  /** tylko parcel – z geometrii */
  area_ha?: number | null
  /** „ULDK GUGiK” | „PRNG GUGiK” | „OpenStreetMap Nominatim” | „słownik demo” */
  source: string
}

export type SearchResponse = {
  query: string
  interpreted_as: QueryInterpretation
  /** maks. 10 */
  results: SearchResult[]
  /** ile wyników pasuje (lista jest przycięta do 10) */
  total: number
  truncated: boolean
  /** podpowiedź dla rolnika (brak wyników, za dużo wyników) */
  hint?: string | null
  /** czego nie udało się sprawdzić (źródło niedostępne) */
  notices?: string[]
  /** atrybucja źródła, gdy wymagana (OSM) */
  attribution?: string | null
}

/** Treść POST /api/analysis i POST /api/report.pdf – dokładnie jedno z: parcel_id, lon+lat, geometry (A5c) */
export type AnalysisRequest = {
  parcel_id?: string | null
  lon?: number | null
  lat?: number | null
  /** własny obrys pola: GeoJSON Polygon w WGS84 ([lon, lat]); 0,05–200 ha, w Polsce, bez samoprzecięć */
  geometry?: GeoJSON.Polygon | null
  crop?: string | null
  date?: string | null
  previous_crop?: string | null
  crop_history?: string | null
  cultivated_area_ha?: number | null
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

/** uprawa w poprzednim roku (przedplon): 15 upraw + „nie wiem” */
export type PreviousCropId = CropId | 'nie_wiem'

/** formalności: none – bez formalności; maybe – może wymagać zgłoszenia wodnoprawnego; required – pozwolenie wodnoprawne */
export type PermitLevel = 'none' | 'maybe' | 'required'
/** kiedy działać: teraz / po zbiorze / przed następnym sezonem */
export type RecommendationWhen = 'teraz' | 'po_zbiorze' | 'przed_sezonem'
/** woda z ulewy: szybko wsiąka i ucieka / dobrze ją zatrzymuje / ryzyko spływu i zastoisk */
export type RainRetention = 'ucieka' | 'zatrzymuje' | 'splywa'

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

/** Czego dotyczy ocena: sezon uprawy / poza sezonem (zapas wody + bilans 30 dni) / bez uprawy (stan działki) */
export type StatusScope = 'sezon' | 'zimowanie' | 'poza_sezonem' | 'bez_uprawy'

export type OverallStatus = {
  level: StatusLevel
  score?: number | null
  headline: string
  summary: string
  /** A5b-1: czego dotyczy ocena */
  scope?: StatusScope | null
  /** np. 'poza sezonem', 'stan wody na działce' */
  scope_label?: string | null
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

/** nie_praktykowane – uprawy, których w Polsce się nie nawadnia (zboża, rzepak, strączkowe): bez dawek */
export type IrrigationStatus =
  | 'zalecane'
  | 'niepotrzebne'
  | 'nieuzasadnione_w_fazie'
  | 'nie_praktykowane'
  /** A5b-2b: kukurydza / tytoń przy niedoborze – bez dawek, tylko informacja w `message` */
  | 'informacyjne'
  | 'brak_danych'

/** nawadnianie w praktyce w Polsce: nie stosuje się / rzadko / typowe */
export type IrrigationPractice = 'not_practiced' | 'optional' | 'common'

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
  /** A5b-1: czy tę uprawę w Polsce się nawadnia */
  practice?: IrrigationPractice | null
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
  /** frakcje i klasa uziarnienia 0–30 cm (SoilGrids) */
  texture?: SoilTexture | null
  /** przepuszczalność i zachowanie wody przy ulewie */
  permeability?: SoilPermeability | null
  /** mapa glebowo-rolnicza (GUGiK): kompleks i gatunek gleby */
  soil_map?: SoilMapInfo | null
  /** powód braku frakcji / mapy glebowo-rolniczej */
  texture_note?: string | null
  /** A5b-1: zgodność źródeł gleby (mapa glebowo-rolnicza > IUNG > SoilGrids) */
  consistency?: SoilConsistency | null
  source_tag: SourceTag
}

export type SoilSourceKey = 'mapa_glebowo_rolnicza' | 'iung' | 'soilgrids'

/** kategoria agronomiczna gleby (I bardzo lekka … IV ciężka) według jednego źródła */
export type SoilCategoryVote = {
  source: SoilSourceKey
  source_label: string
  /** 1–4 */
  category?: number | null
  /** np. 'piasek gliniasty lekki – gleba lekka' */
  description: string
}

export type SoilConsistency = {
  status: 'ok' | 'conflict'
  /** krótkie wyjaśnienie dla rolnika */
  note: string
  /** źródło kategorii gleby i WOD użytych w obliczeniach */
  basis?: SoilSourceKey | null
  /** kategoria gleby (1–4) użyta w modelu wody */
  category_used?: number | null
  by_source?: SoilCategoryVote[]
}

/** uziarnienie 0–30 cm – SoilGrids 250 m (ISRIC) */
export type SoilTexture = {
  sand_pct: number
  silt_pct: number
  clay_pct: number
  /** węgiel organiczny, % */
  organic_carbon_pct?: number | null
  /** klasa uziarnienia po polsku (trójkąt USDA), np. 'glina piaszczysta' */
  texture_class: string
  /** kod klasy USDA, np. 'sandy_loam' */
  texture_code: string
  depth: string
  source_tag: SourceTag
}

/** przepuszczalność (Ksat) – Saxton i Rawls (2006) */
export type SoilPermeability = {
  ksat_mm_h: number
  /** bardzo duża / duża / średnia / mała / bardzo mała */
  label: string
  rain_retention: RainRetention
  /** zdanie dla rolnika: co dzieje się z wodą z ulewy */
  description: string
  method: string
  source_tag: SourceTag
}

/** mapa glebowo-rolnicza 1:5000 (PZGiK) – kontur w środku działki */
export type SoilMapInfo = {
  /** kompleks przydatności rolniczej, np. '2', '2z' */
  complex_code?: string | null
  /** np. 'pszenny dobry' */
  complex_label?: string | null
  /** gatunek wierzchniej warstwy, np. 'pgl' */
  species_code?: string | null
  /** np. 'piasek gliniasty lekki' */
  species_label?: string | null
  /** utwory głębszych warstw, od góry */
  deeper?: string[]
  /** typ/podtyp gleby, np. 'Bw' */
  soil_type_code?: string | null
  /** rok opracowania mapy */
  mapped_year?: number | null
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
  /** kiedy działać */
  when: RecommendationWhen
  /** np. 'teraz', 'po zbiorze', 'przed następnym sezonem' */
  when_label: string
  /** formalności */
  permit: PermitLevel
  /** np. 'Bez formalności – możesz to zrobić sam.' */
  permit_note: string
  /** link do Wód Polskich (maybe / required) */
  permit_url?: string | null
  /** przy niskiej pewności: 'obarczone dużym ryzykiem błędu' */
  warning?: string | null
  /** powiązany ekoschemat ARiMR (bez kwot dopłat) */
  eco_scheme?: EcoScheme | null
}

/** ekoschemat (PS WPR, ARiMR) – tylko informacja, bez kwot */
export type EcoScheme = {
  name: string
  practice: string
  /** kod praktyki, np. 'E_MPW' */
  code?: string | null
  note: string
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

/**
 * A5b-1: stan wody na działce bez względu na uprawę – profil ~1 m pod pokryciem referencyjnym FAO-56
 * (trawa, Kc = 1), bilans opad − ET0 z 30 dni na tle 10 lat. Liczony zawsze; null dla gruntu nierolnego.
 */
export type FieldState = {
  status: OverallStatus
  /** np. 'pokrycie referencyjne FAO-56 (trawa, Kc = 1), profil ok. 1 m' */
  cover: string
  soil_water_pct: Indicator
  soil_water_mm: Indicator
  soil_water: SoilWaterState
  /** początek przebiegu – 1 listopada (rok hydrologiczny) */
  series_start: ISODate
  /** woda dostępna w profilu, %, dzień po dniu */
  series: SeriesPoint[]
  /** ten sam okres w 10 poprzednich latach (min / max / średnia), % */
  series_band: BandPoint[]
  /** bilans opad − ET0 z ostatnich 30 dni, mm */
  balance_30d: Indicator
  balance_30d_rank?: BalanceRank | null
  source_tag: SourceTag
}

// ── Ranking „Co tu posiać?” (A5b-2a) ───────────────────────────────────────────────────────

/** uprawy w rankingu: 10 upraw IUNG + 7 gatunków (zboża, łubin) */
export type RankingCropId =
  | 'kukurydza_ziarno'
  | 'kukurydza_kiszonka'
  | 'rzepak'
  | 'ziemniak'
  | 'burak_cukrowy'
  | 'straczkowe'
  | 'warzywa'
  | 'drzewa_owocowe'
  | 'krzewy_owocowe'
  | 'truskawki'
  | 'pszenica_ozima'
  | 'zyto'
  | 'pszenzyto_ozime'
  | 'jeczmien_ozimy'
  | 'jeczmien_jary'
  | 'owies'
  | 'lubin'

/** ✅ polecane / 🟡 możliwe / ❌ odradzane */
export type SuggestionCategory = 'polecane' | 'mozliwe' | 'odradzane'
export type SoilSuitability = 'odpowiednia' | 'neutralna' | 'nieodpowiednia'
export type RotationStatus = 'ok' | 'plus' | 'ostrzezenie' | 'naruszenie' | 'brak_historii'

/** płodozmian wg historii pola; naruszenie = za krótka przerwa (uprawa odradzana) */
export type RotationCheck = { status: RotationStatus; notes?: string[] }

export type YearYield = {
  year: number
  /** plon względny 0–1 (1 = bez strat z braku wody) */
  relative: number
  yield_t_ha?: number | null
  water_deficit_mm?: number | null
}

export type CultivatedArea = {
  value_ha: number
  /** true = działka × udział gruntów rolnych wg IUNG (oszacowanie) */
  estimated: boolean
  note: string
}

export type CropSuggestion = {
  crop_id: RankingCropId
  label: string
  group_id: string
  category: SuggestionCategory
  category_label: string
  /** miejsce w grupie (1 = najlepsza) */
  rank: number
  score: number
  /** JEDNO zdanie uzasadnienia */
  reason: string
  /** typowy plon – mediana z 10 lat, t/ha, bez nawadniania */
  yield_typical_t_ha?: number | null
  /** plon w słabym roku – najgorszy z 10 lat, t/ha */
  yield_weak_t_ha?: number | null
  weak_year: number
  yield_potential_t_ha?: number | null
  gus_mean_t_ha?: number | null
  relative_yield_median: number
  relative_yield_weak: number
  /** w ilu latach strata plonu > 20% („X na 10 lat”) */
  drought_risk_years: number
  years_simulated: number
  /** plon z całej powierzchni uprawy, t */
  total_typical_t?: number | null
  total_weak_t?: number | null
  /** miejsce na cenę skupu – na razie null */
  price?: null
  soil_suitability: SoilSuitability
  soil_suitability_label: string
  rotation: RotationCheck
  irrigation_practice: IrrigationPractice
  drought_sensitivity: 'niska' | 'srednia' | 'wysoka'
  confidence: Confidence
  confidence_note?: string | null
  notes?: string[]
  yields_by_year: YearYield[]
  source_tags: SourceTag[]
}

export type SuggestionGroup = {
  key: 'polowe' | 'wieloletnie'
  label: string
  /** od najlepszej: polecane → możliwe → odradzane */
  items: CropSuggestion[]
}

/** ranking upraw dla tej działki i gleby na pogodzie z 10 sezonów; plony zawsze BEZ nawadniania */
/** A5b-2b: uprawa wieloletnia – bez kategorii, niska pewność, osobna analiza opłacalności */
export type PerennialSuggestion = {
  crop_id: RankingCropId
  label: string
  yield_typical_t_ha?: number | null
  yield_weak_t_ha?: number | null
  weak_year: number
  drought_risk_years: number
  years_simulated: number
  total_typical_t?: number | null
  total_weak_t?: number | null
  soil_suitability: SoilSuitability
  soil_suitability_label: string
  irrigation_practice: IrrigationPractice
  confidence?: Confidence
  note: string
  source_tags?: SourceTag[]
}

export type PerennialSection = {
  /** 'Uprawy wieloletnie – inwestycja na lata' */
  label: string
  note: string
  items: PerennialSuggestion[]
}

export type CropSuggestions = {
  seasons: number[]
  /** od A5b-2b tylko „uprawy polowe” */
  groups: SuggestionGroup[]
  /** A5b-2b: uprawy wieloletnie osobno, bez ✅/🟡/❌ */
  perennials?: PerennialSection | null
  area: CultivatedArea
  crop_history?: string[]
  /** bez historii: 'Podaj, co rosło w ostatnich latach – uwzględnimy płodozmian.' */
  rotation_hint?: string | null
  note: string
  limitations?: string[]
  compute_ms?: number | null
  source_tag: SourceTag
}

// ── Werdykt działki (A5b-2b) ──────────────────────────────────────────────────────────────

export type VerdictKind = 'gleba' | 'opady' | 'teren' | 'uprawy' | 'woda' | 'uprawa_wybrana'
/** ok #5BB37F / warn #E8B931 / bad #C8453B */
export type VerdictLevel = 'ok' | 'warn' | 'bad'
/** pozycja „woda” ma level 'info' (lista działań, bez oceny; kolor #2F80C9, ikona kropli) */
export type VerdictStatementLevel = VerdictLevel | 'info'

export type VerdictStatement = {
  kind: VerdictKind
  level: VerdictStatementLevel
  /** 1–2 proste zdania z liczbami */
  text: string
  numbers?: Record<string, number | string | null>
}

export type VerdictCrop = {
  crop_id: RankingCropId
  label: string
  /** dla ❌ – jeden powód */
  reason?: string | null
}

/** werdykt działki w 10 sekund – deterministyczny, bez AI */
export type Verdict = {
  /** np. 'Dobra działka z wilgotnym obniżeniem' */
  headline: string
  level: VerdictLevel
  /** 4–6 pozycji */
  statements: VerdictStatement[]
  /** ✅ 2–4 najlepsze uprawy polowe */
  crops_good?: VerdictCrop[]
  /** ❌ odradzane z jednym powodem */
  crops_bad?: VerdictCrop[]
  note: string
}

/** analiza po punkcie bez granic działki (ULDK nie odpowiada) */
export type ApproximateArea = {
  /** [lon, lat] */
  center: number[]
  side_m: number
  area_ha: number
  reason: string
  /** 'Obszar przybliżony – brak granic działki z ULDK…' */
  note: string
  voivodeship_note?: string | null
}

// ── Teren i spływ wody z NMT (A6) ──────────────────────────────────────────────────────────

export type TerrainZoneKey = 'sucha_gorka' | 'stok' | 'plasko' | 'mokry_dolek'
export type TerrainRating = 'dobrze' | 'uwaga' | 'zle'

/** strefa terenu z udziałem i oceną z glebą */
export type TerrainZone = {
  key: TerrainZoneKey
  /** 'górka – sucho' | 'stok – woda ucieka' | 'płasko – dobre warunki' | 'dołek – woda stoi' */
  label: string
  /** 0–100 */
  share_pct: number
  /** kolor na pasku i mapie: górka #8B6B4A, stok #E8B931, płasko #5BB37F, dołek #2F80C9 */
  color: string
  /** null, gdy strefy praktycznie nie ma (< 1%) */
  rating?: TerrainRating | null
  /** jedno zdanie dla rolnika, np. '20% działki to dołek – wiosną stoi woda.' */
  sentence?: string | null
}

/** miejsce, którędy woda opuszcza działkę („tu woda ucieka”) */
export type TerrainOutlet = {
  direction: string
  direction_short: string
  azimuth_deg?: number | null
  share_of_parcel_pct: number
  /** [lon, lat] */
  location: number[]
}

export type TerrainDepression = {
  area_m2?: number | null
  max_depth_m?: number | null
  volume_m3?: number | null
  catchment_m2?: number | null
  /** [lon, lat] najgłębszego miejsca */
  location?: number[] | null
}

/** szczegóły „dla dociekliwych” */
export type TerrainDetails = {
  grid_step_m: number
  smoothing_sigma_m: number
  nmt_points?: number | null
  nmt_missing_pct?: number | null
  /** TWI = ln(a / tan β) */
  twi_mean?: number | null
  twi_p90?: number | null
  steep_share_pct?: number | null
  flow_consistency?: number | null
  method: string
}

export type Terrain = {
  /** zawsze 4 strefy w stałej kolejności: górka, stok, płasko, dołek */
  zones: TerrainZone[]
  zone_share_pct: Record<TerrainZoneKey, number>
  /** A5b-2b: etykieta ważona udziałem; 'zwiezla' – już nieużywane */
  soil_group: 'lekka' | 'srednia' | 'ciezka' | 'organiczna' | 'zwiezla' | 'nieznana'
  soil_group_label: string
  /** 2–3 zdania o terenie prostym językiem */
  summary: string
  relief_m?: number | null
  elev_min_m?: number | null
  elev_max_m?: number | null
  slope_mean_pct?: number | null
  slope_max_pct?: number | null
  main_flow_direction?: string | null
  main_flow_direction_short?: string | null
  main_flow_azimuth_deg?: number | null
  outlets?: TerrainOutlet[]
  inflow_from_outside_m2?: number | null
  inflow_from_outside_ratio?: number | null
  depressions_count?: number
  depressions_volume_m3?: number | null
  largest_depression?: TerrainDepression | null
  details: TerrainDetails
  confidence: Confidence
  limitations?: string[]
  source_tag: SourceTag
}

export type AnalysisResponse = {
  parcel: Parcel
  /** null = analiza bez uprawy („Stan działki”) */
  crop: CropId | null
  /** uprawa w poprzednim roku (jeśli podana) */
  previous_crop?: PreviousCropId | null
  analysis_date: ISODate
  historical: boolean
  generated_at: ISODateTime
  status: OverallStatus
  indicators: Indicators
  /** null bez uprawy */
  crop_season: CropSeason | null
  soil_water: SoilWaterState
  /** null bez uprawy */
  irrigation: IrrigationPlan | null
  soil: Soil
  /** A5b-1: „Stan działki” – pokazywać od razu po wybraniu działki, bez wymagania uprawy */
  field_state?: FieldState | null
  /** A5b-2a: ranking „Co tu posiać?” (null: grunt nierolny / brak danych) */
  suggestions?: CropSuggestions | null
  /** historia pola z zapytania: 1–3 lata, indeks 0 = rok temu (crop_id albo 'nie_wiem') */
  crop_history?: string[]
  /** powierzchnia uprawy użyta w rankingu, ha */
  cultivated_area_ha?: number | null
  /** A6: teren i spływ wody z NMT (null = brak danych, powód w terrain_note) */
  terrain?: Terrain | null
  /** A6: dlaczego brak analizy terenu */
  terrain_note?: string | null
  /** A5b-2b: werdykt działki (null: grunt nierolny / brak danych) */
  verdict?: Verdict | null
  /** A5b-2b: obszar przybliżony zamiast działki (analiza po punkcie lon/lat) */
  approximate_area?: ApproximateArea | null
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

// ── schemas/demo.py – GET /api/demo/examples ───────────────────────────────────────────────

/** przykład do oceny – wynik zawsze z normalnego GET /api/analysis */
export type DemoExample = {
  id: string
  title: string
  description: string
  parcel_id: string
  crop: CropId
  date: ISODate
  previous_crop?: PreviousCropId | null
}

// ── schemas/status.py – GET /api/status ────────────────────────────────────────────────────

export type WarmupState = 'wylaczona' | 'oczekuje' | 'w_toku' | 'gotowe' | 'blad'

export type ServiceStatus = {
  name: string
  used_for: string
  ok: boolean
  response_ms?: number | null
  error?: string | null
  cache_entries: number
  cache_newest_age_s?: number | null
}

export type WarmupItem = {
  id: string
  title: string
  state: WarmupState
  duration_ms?: number | null
  finished_at?: ISODateTime | null
  error?: string | null
}

export type StatusResponse = {
  checked_at: ISODateTime
  all_ok: boolean
  services: ServiceStatus[]
  warmup_enabled: boolean
  warmup: WarmupItem[]
}

// GET /api/report.pdf?parcel_id=&crop=&date=&previous_crop= – plik PDF (application/pdf)
