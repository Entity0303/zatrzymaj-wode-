/** Klient API: zapytania do backendu i tłumaczenie błędów na prosty polski. Typy: ./types.ts */
import type {
  AnalysisRequest,
  AnalysisResponse,
  CropId,
  DemoExample,
  DroughtContext,
  Forecast,
  Hydro,
  Terrain,
  InfraReport,
  InfraReportIn,
  LayerKey,
  LayerResponse,
  Parcel,
  PointValue,
  Satellite,
  SearchResponse,
} from './types'
import { periodParams } from '@/lib/period'

/**
 * Adres backendu: `VITE_API_URL` (wdrożenie: Vercel → Render), domyślnie pusty = względne `/api`
 * (Docker, `npm run dev` z proxy). Wszystkie zapytania i pobieranie PDF przechodzą przez `apiUrl`.
 */
const API_BASE = (import.meta.env.VITE_API_URL ?? '').trim().replace(/\/+$/, '')
export const apiUrl = (path: string) => `${API_BASE}${path}`

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? (detail as { message?: string })?.message ?? `Błąd ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function get<T>(path: string, params: Record<string, string | number>, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))
  let res: Response
  try {
    res = await fetch(`${apiUrl(path)}?${qs}`, { signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, null, 'Brak połączenia z serwerem aplikacji.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body)
  return body as T
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response
  try {
    res = await fetch(apiUrl(path), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, null, 'Brak połączenia z serwerem aplikacji.')
  }
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data)
  return data as T
}

import type { PriceWeather } from './types'

export type { PriceWeather }

/** F30: odpowiedź POST /api/parcels-in-area (typ lokalny – poza kontraktem analizy). */
export type ParcelsInArea = { parcels: { id: string; obreb: string; gmina: string; numer: string; share: number }[]; note: string | null }

/** Parametry analizy (GET /api/analysis, GET /api/report.pdf). */
export type AnalysisQuery = {
  parcelId?: string | null
  point?: [number, number] | null
  /** A5c: pole narysowane przez rolnika (GeoJSON Polygon WGS84) – zapytania idą POST-em */
  geometry?: GeoJSON.Polygon | null
  crop?: CropId | null
  date: string
  /** 1–3 lata wstecz (pierwsza = rok temu), puste = „nie wiem” */
  cropHistory?: string[]
  area?: number | null
  /** A5e: „Co planujesz posiać?” – do 3 upraw lub grup (crop_id) */
  plannedCrops?: string[]
  /** A5e: raport PDF – skrócony (2 strony) / szczegółowy */
  reportType?: 'short' | 'full'
  /** F3: okres (znacznik z lib/period.ts) → period= albo date_from/date_to */
  period?: string | null
  /** F18: data siewu wpisana przez rolnika → sowing_date= (backend dodaje parametr; dopóki go nie zna – ignoruje) */
  sowingDate?: string | null
}

/** Samo miejsce: działka albo punkt (teren, woda w okolicy). */
function placeParams(q: AnalysisQuery): Record<string, string | number> {
  if (q.point) return { lon: q.point[0].toFixed(7), lat: q.point[1].toFixed(7) }
  return q.parcelId ? { parcel_id: q.parcelId } : {}
}

/** Treść POST (pole narysowane): te same pola co w GET, `geometry` zamiast działki / punktu. */
function analysisBody(q: AnalysisQuery): AnalysisRequest {
  const p = analysisParams({ ...q, parcelId: null, point: null, period: null })
  return {
    geometry: q.geometry,
    date: q.date,
    crop: q.crop ?? null,
    crop_history: (p.crop_history as string | undefined) ?? null,
    cultivated_area_ha: q.area && q.area > 0 ? q.area : null,
    planned_crops: q.plannedCrops?.length ? q.plannedCrops.slice(0, 3) : null,
    report_type: q.reportType ?? null,
    // F8: okres także dla pola narysowanego (POST /api/analysis i /api/report.pdf przyjmują period / date_from / date_to)
    ...(periodParams(q.period, q.date) as Pick<AnalysisRequest, 'period' | 'date_from' | 'date_to'>),
    // F18: pole spoza kontraktu (typ lokalny) – backend dodaje je w swoim zadaniu
    ...(q.sowingDate ? ({ sowing_date: q.sowingDate } as object) : {}),
  }
}

/** Zapytanie analizy / raportu: działka albo punkt, uprawa, historia pola, powierzchnia. */
function analysisParams(q: AnalysisQuery): Record<string, string | number> {
  const params: Record<string, string | number> = { date: q.date }
  if (q.point) {
    params.lon = q.point[0].toFixed(7)
    params.lat = q.point[1].toFixed(7)
  } else if (q.parcelId) params.parcel_id = q.parcelId
  if (q.crop) params.crop = q.crop
  if (q.cropHistory?.some((c) => c && c !== 'nie_wiem')) params.crop_history = q.cropHistory.map((c) => c || 'nie_wiem').join(',')
  if (q.area && q.area > 0) params.cultivated_area_ha = q.area
  if (q.plannedCrops?.length) params.planned_crops = q.plannedCrops.slice(0, 3).join(',')
  if (q.reportType) params.report_type = q.reportType
  Object.assign(params, periodParams(q.period, q.date))
  if (q.sowingDate) params.sowing_date = q.sowingDate
  return params
}

export const api = {
  parcelById: (id: string) => get<Parcel>('/api/parcel', { id }),
  parcelByPoint: (lon: number, lat: number) =>
    get<Parcel>('/api/parcel', { lon: lon.toFixed(7), lat: lat.toFixed(7) }),
  forecast: (lon: number, lat: number, signal?: AbortSignal) =>
    get<Forecast>('/api/forecast', { lon: lon.toFixed(3), lat: lat.toFixed(3), days: 7 }, signal),
  /**
   * GET /api/analysis – działka (`parcelId`) albo punkt bez granic działki (`point` → obszar przybliżony);
   * uprawa opcjonalna (bez uprawy = „Stan działki” + ranking „Co tu posiać?”).
   */
  analysis: (q: AnalysisQuery, signal?: AbortSignal) =>
    q.geometry
      ? post<AnalysisResponse>('/api/analysis', analysisBody({ ...q, reportType: undefined }), signal)
      : get<AnalysisResponse>('/api/analysis', analysisParams(q), signal),
  /**
   * GET /api/satellite (A11) – zdjęcie Sentinel-2 dla działki albo punktu; liczone na żywo (ok. 6–15 s), potem z cache.
   * Brak sceny / awaria = 200 ze `status: "brak_danych"`.
   */
  satellite: (q: AnalysisQuery, signal?: AbortSignal) => {
    if (q.geometry) return post<Satellite>('/api/satellite', { geometry: q.geometry, date: q.date }, signal)
    const p = analysisParams({ parcelId: q.parcelId, point: q.point, date: q.date })
    return get<Satellite>('/api/satellite', p, signal)
  },
  /**
   * F3: teren liczony w tle – GET /api/terrain?parcel_id= (lon/lat) albo POST { geometry } dla pola narysowanego.
   */
  terrain: (q: AnalysisQuery, signal?: AbortSignal) =>
    q.geometry ? post<Terrain>('/api/terrain', { geometry: q.geometry }, signal) : get<Terrain>('/api/terrain', placeParams(q), signal),
  /**
   * F3: woda w okolicy – GET /api/hydro?parcel_id=&date= (lon/lat) albo POST { geometry, date }. F-MASTER B1: zawsze
   * z datą analizy – bez niej backend bierze dziś i dla daty historycznej pokazywał dzisiejszy stan wodowskazu.
   */
  hydro: (q: AnalysisQuery, signal?: AbortSignal) =>
    q.geometry
      ? post<Hydro>('/api/hydro', { geometry: q.geometry, date: q.date }, signal)
      : get<Hydro>('/api/hydro', { ...placeParams(q), date: q.date }, signal),
  /**
   * F31: tło suszowe z Europejskiego Obserwatorium Suszy (A26) – GET /api/drought-context?parcel_id=&date=&our_status=
   * albo POST { geometry, date, our_status } dla pola narysowanego. Awaria usługi = 200 z `unavailable: true`.
   */
  droughtContext: (q: AnalysisQuery, ourStatus: string | null, signal?: AbortSignal) =>
    q.geometry
      ? post<DroughtContext>('/api/drought-context', { geometry: q.geometry, date: q.date, our_status: ourStatus }, signal)
      : get<DroughtContext>('/api/drought-context', { ...placeParams(q), date: q.date, ...(ourStatus ? { our_status: ourStatus } : {}) }, signal),
  /** GET /api/search?q= – jedno pole wyszukiwania: identyfikator, „obręb numer” albo nazwa miejscowości (A5c) */
  search: (q: string, signal?: AbortSignal) => get<SearchResponse>('/api/search', { q }, signal),
  /** GET /api/layers/{layer} – warstwa przycięta do obrysu działki (raster PNG + bbox, GeoJSON) */
  layer: (
    layer: LayerKey,
    parcelId: string,
    date: string,
    signal?: AbortSignal,
    geometry?: GeoJSON.Polygon | null,
    /** F29: obszar przybliżony – punkt [lon, lat] zamiast działki */
    point?: [number, number] | null,
  ) =>
    // F3/F29: pole narysowane (obrys) i obszar przybliżony (punkt) – wszystkie warstwy POST-em, jak analiza
    geometry
      ? post<LayerResponse>(`/api/layers/${layer}`, { geometry, date }, signal)
      : point
        ? post<LayerResponse>(`/api/layers/${layer}`, { lon: point[0], lat: point[1], date }, signal)
        : get<LayerResponse>(`/api/layers/${layer}`, { parcel_id: parcelId, date }, signal),
  /** GET /api/layers/{layer}/point – wartość warstwy w klikniętym punkcie (SPEC 5.4) */
  layerPoint: (layer: LayerKey, lon: number, lat: number, date: string) =>
    get<PointValue>(`/api/layers/${layer}/point`, { lon: lon.toFixed(7), lat: lat.toFixed(7), date }),
  /** GET /api/infra-reports – zgłoszenia rowów/zbiorników w prostokącie [lon_min, lat_min, lon_max, lat_max] */
  infraReports: (b: [number, number, number, number], signal?: AbortSignal) =>
    get<InfraReport[]>('/api/infra-reports', { lon_min: b[0], lat_min: b[1], lon_max: b[2], lat_max: b[3] }, signal),
  /** POST /api/infra-reports – nowe zgłoszenie (SPEC 11) */
  createInfraReport: (r: InfraReportIn) => post<InfraReport>('/api/infra-reports', r),
  /** POST /api/infra-reports/{id}/confirm – „Potwierdzam” */
  confirmInfraReport: (id: string) => post<InfraReport>(`/api/infra-reports/${encodeURIComponent(id)}/confirm`, {}),
  /** GET /api/demo/examples – przykłady „jednym klikiem” (działki rozgrzane w pamięci serwera) */
  demoExamples: (signal?: AbortSignal) => get<DemoExample[]>('/api/demo/examples', {}, signal),
  /** F32: GET /api/price-weather – ceny skupu, plon i opady IV–IX w regionie (województwo albo PL) na tle lat */
  priceWeather: (region: string, crop: string, toYear: number, signal?: AbortSignal) =>
    get<PriceWeather>('/api/price-weather', { region, crop, to_year: toYear }, signal),
  /** F30: POST /api/parcels-in-area – działki ewidencyjne pod polem narysowanym (udział w %) */
  parcelsInArea: (geometry: GeoJSON.Polygon, signal?: AbortSignal) => post<ParcelsInArea>('/api/parcels-in-area', { geometry }, signal),
  /** GET /api/report.pdf – te same parametry co analiza; odpowiedź to plik PDF */
  reportPdf: async (q: AnalysisQuery, signal?: AbortSignal): Promise<Blob> => {
    // bez uprawy = raport „Stan działki”; punkt zamiast działki = obszar przybliżony
    const params = Object.entries(analysisParams(q)).map(([k, v]) => [k, String(v)])
    let res: Response
    try {
      res = q.geometry
        ? await fetch(apiUrl('/api/report.pdf'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(analysisBody(q)), signal })
        : await fetch(`${apiUrl('/api/report.pdf')}?${new URLSearchParams(params)}`, { signal })
    } catch {
      throw new ApiError(0, null, 'Brak połączenia z serwerem aplikacji.')
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null)
      throw new ApiError(res.status, body?.detail ?? body)
    }
    return res.blob()
  },
}

/** Teksty po polsku (klucze tłumaczeń) – tłumaczy je ErrorNotice; {zmienne} w `vars`. */
export type ErrorInfo = {
  title: string
  message: string
  stillWorks?: string
  retryable: boolean
  vars?: Record<string, string | number>
}

/** Tłumaczy błąd API na komunikat dla rolnika (SPEC 14 ErrorNotice: co nie zadziałało, co działa dalej). */
export function describeError(e: unknown, kind: 'number' | 'point'): ErrorInfo {
  const stillWorks = 'Mapa działa dalej – możesz kliknąć pole na mapie albo wpisać inny numer.'
  if (!(e instanceof ApiError))
    return { title: 'Coś poszło nie tak', message: 'Nie udało się wyszukać działki.', stillWorks, retryable: true }
  const detail = e.detail as { source?: string; message?: string } | null
  if (e.status === 0)
    return {
      title: 'Brak połączenia',
      message: 'Nie można połączyć się z serwerem aplikacji. Sprawdź internet.',
      retryable: true,
    }
  if (e.status === 404) {
    if (detail?.message?.includes('poza Polską'))
      return { title: 'To miejsce leży poza Polską', message: 'Działki szukamy tylko na terenie Polski.', stillWorks, retryable: false }
    return kind === 'point'
      ? {
          title: 'Tu nie ma działki ewidencyjnej',
          message: 'W klikniętym miejscu ewidencja nie ma działki (np. droga lub woda). Kliknij w pole uprawne.',
          stillWorks,
          retryable: false,
        }
      : {
          title: 'Nie znaleziono działki',
          message: 'Sprawdź numer – pełny identyfikator wygląda tak: 201305_2.0038.6/1. Możesz też wpisać nazwę wsi i numer działki.',
          stillWorks,
          retryable: false,
        }
  }
  if (e.status === 502)
    // F12: bez technicznego {detail} – rolnik dostaje, co zrobić
    return {
      title: 'Nie udało się pobrać działki',
      message: 'Ewidencja gruntów chwilowo nie odpowiada. Spróbuj za chwilę.',
      stillWorks,
      retryable: true,
    }
  // bez surowego kodu błędu – co się stało i co zrobić
  return {
    title: 'Serwer chwilowo nie odpowiada poprawnie',
    message: e.status === 504 || e.status === 503 ? 'Liczenie trwało zbyt długo. Spróbuj ponownie za chwilę.' : 'Coś poszło nie tak po stronie serwera. Spróbuj ponownie za chwilę.',
    stillWorks,
    retryable: true,
  }
}

/** Błąd GET /api/analysis po polsku – mapa, dane działki i prognoza działają dalej. */
export function describeAnalysisError(e: unknown): ErrorInfo {
  const stillWorks = 'Mapa, granice działki i prognoza pogody działają dalej.'
  if (!(e instanceof ApiError))
    return { title: 'Nie udało się policzyć oceny', message: 'Coś poszło nie tak. Spróbuj jeszcze raz.', stillWorks, retryable: true }
  const detail = e.detail as { source?: string; message?: string } | null
  if (e.status === 0)
    return { title: 'Brak połączenia', message: 'Nie można połączyć się z serwerem aplikacji. Sprawdź internet.', retryable: true }
  if (e.status === 422 && detail?.message)
    return {
      title: 'Nie można policzyć tego pola',
      message: detail.message,
      stillWorks: 'Kliknij „Narysuj swoje pole” i popraw obrys albo wybierz działkę z mapy.',
      retryable: false,
    }
  if (e.status === 404)
    return {
      title: 'Brak danych dla tego miejsca',
      message: detail?.message ?? 'Serwer nie znalazł danych dla tego miejsca.',
      stillWorks: 'Kliknij inne pole na mapie albo wpisz numer działki.',
      retryable: false,
    }
  if (e.status === 501)
    return {
      title: 'Nie udało się policzyć oceny',
      message: 'Coś poszło nie tak. Spróbuj jeszcze raz.',
      stillWorks,
      retryable: false,
    }
  if (e.status === 502 || e.status === 504)
    return {
      title: 'Usługa {source} nie odpowiada',
      message: 'Jedno ze źródeł danych chwilowo nie odpowiada. Spróbuj za chwilę.',
      stillWorks,
      retryable: true,
      vars: { source: detail?.source ?? 'zewnętrzna' },
    }
  // bez surowego kodu błędu – co się stało i co zrobić
  return {
    title: 'Serwer chwilowo nie odpowiada poprawnie',
    message: e.status === 504 || e.status === 503 ? 'Liczenie trwało zbyt długo. Spróbuj ponownie za chwilę.' : 'Coś poszło nie tak po stronie serwera. Spróbuj ponownie za chwilę.',
    stillWorks,
    retryable: true,
  }
}
