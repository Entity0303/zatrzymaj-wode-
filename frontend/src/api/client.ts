/** Klient API: zapytania do backendu i tłumaczenie błędów na prosty polski. Typy: ./types.ts */
import type {
  AnalysisResponse,
  CropId,
  Forecast,
  InfraReport,
  InfraReportIn,
  LayerKey,
  LayerResponse,
  Parcel,
  PointValue,
} from './types'
import type { PlaceSearchResponse } from './places.proposal'

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
    res = await fetch(`${path}?${qs}`, { signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, null, 'Brak połączenia z serwerem aplikacji.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body)
  return body as T
}

async function post<T>(path: string, body: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  } catch {
    throw new ApiError(0, null, 'Brak połączenia z serwerem aplikacji.')
  }
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data)
  return data as T
}

/** bez polskich znaków i wielkości liter – do porównań nazw */
const fold = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l').replace(/Ł/g, 'L').toLowerCase().trim()

export const api = {
  parcelById: (id: string) => get<Parcel>('/api/parcel', { id }),
  parcelByPoint: (lon: number, lat: number) =>
    get<Parcel>('/api/parcel', { lon: lon.toFixed(7), lat: lat.toFixed(7) }),
  forecast: (lon: number, lat: number, signal?: AbortSignal) =>
    get<Forecast>('/api/forecast', { lon: lon.toFixed(3), lat: lat.toFixed(3), days: 7 }, signal),
  /** GET /api/analysis – backend zwraca na razie 501 „w budowie” (kontrakt: types.ts AnalysisResponse) */
  analysis: (parcelId: string, crop: CropId, date: string, signal?: AbortSignal) =>
    get<AnalysisResponse>('/api/analysis', { parcel_id: parcelId, crop, date }, signal),
  /** GET /api/layers/{layer} – warstwa przycięta do obrysu działki (raster PNG + bbox, GeoJSON) */
  layer: (layer: LayerKey, parcelId: string, date: string, signal?: AbortSignal) =>
    get<LayerResponse>(`/api/layers/${layer}`, { parcel_id: parcelId, date }, signal),
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
  /**
   * GET /api/places?q= – miejsce (obręb / gmina) po nazwie. PROPOZYCJA kontraktu (api/places.proposal.ts).
   * Tryb deweloperski + ?dane=przykladowe: mock z mocks/places.sample.json.
   */
  places: async (q: string, signal?: AbortSignal): Promise<PlaceSearchResponse> => {
    if (import.meta.env.DEV && new URLSearchParams(window.location.search).get('dane') === 'przykladowe') {
      const data = (await import('@/mocks/places.sample.json')).default as unknown as PlaceSearchResponse
      const f = fold(q)
      const places = data.places
        .filter((p) => fold(p.name).startsWith(f))
        .sort((a, b) => Number(fold(b.name) === f) - Number(fold(a.name) === f))
      if (!places.length) throw new ApiError(404, { message: 'nie znaleziono miejsca' })
      return { places, total: places.length }
    }
    return get<PlaceSearchResponse>('/api/places', { q }, signal)
  },
  /** GET /api/report.pdf – te same parametry co analiza; odpowiedź to plik PDF */
  reportPdf: async (parcelId: string, crop: CropId, date: string): Promise<Blob> => {
    const params: Record<string, string> = { parcel_id: parcelId, crop, date }
    let res: Response
    try {
      res = await fetch(`/api/report.pdf?${new URLSearchParams(params)}`)
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
          message: 'Sprawdź numer. Przykłady: „Szczytno 112/11” albo „143203_2.0027.112/11”.',
          stillWorks,
          retryable: false,
        }
  }
  if (e.status === 502)
    return {
      title: 'Usługa {source} nie odpowiada',
      message: 'Nie udało się pobrać danych działki ({detail}).',
      stillWorks,
      retryable: true,
      vars: { source: detail?.source ?? 'zewnętrzna', detail: detail?.message ?? 'błąd usługi' },
    }
  return { title: 'Błąd serwera', message: 'Serwer zwrócił błąd {status}.', stillWorks, retryable: true, vars: { status: e.status } }
}

/** Błąd GET /api/analysis po polsku – mapa, dane działki i prognoza działają dalej. */
export function describeAnalysisError(e: unknown): ErrorInfo {
  const stillWorks = 'Mapa, granice działki i prognoza pogody działają dalej.'
  if (!(e instanceof ApiError))
    return { title: 'Nie udało się policzyć oceny', message: 'Wystąpił nieoczekiwany błąd.', stillWorks, retryable: true }
  const detail = e.detail as { source?: string; message?: string } | null
  if (e.status === 0)
    return { title: 'Brak połączenia', message: 'Nie można połączyć się z serwerem aplikacji. Sprawdź internet.', retryable: true }
  if (e.status === 501)
    return {
      title: 'Ocena sytuacji wodnej jest jeszcze w budowie',
      message: 'Serwer nie liczy jeszcze analizy działki.',
      stillWorks,
      retryable: false,
    }
  if (e.status === 502 || e.status === 504)
    return {
      title: 'Usługa {source} nie odpowiada',
      message: detail?.message ?? 'Nie udało się pobrać danych do analizy.',
      stillWorks,
      retryable: true,
      vars: { source: detail?.source ?? 'zewnętrzna' },
    }
  return { title: 'Błąd serwera', message: 'Serwer zwrócił błąd {status}.', stillWorks, retryable: true, vars: { status: e.status } }
}
