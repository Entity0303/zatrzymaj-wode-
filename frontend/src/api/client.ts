/** Klient API: zapytania do backendu i tłumaczenie błędów na prosty polski. Typy: ./types.ts */
import type { AnalysisResponse, CropId, Forecast, Parcel } from './types'

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

export const api = {
  parcelById: (id: string) => get<Parcel>('/api/parcel', { id }),
  parcelByPoint: (lon: number, lat: number) =>
    get<Parcel>('/api/parcel', { lon: lon.toFixed(7), lat: lat.toFixed(7) }),
  forecast: (lon: number, lat: number, signal?: AbortSignal) =>
    get<Forecast>('/api/forecast', { lon: lon.toFixed(3), lat: lat.toFixed(3), days: 7 }, signal),
  /** GET /api/analysis – backend zwraca na razie 501 „w budowie” (kontrakt: types.ts AnalysisResponse) */
  analysis: (parcelId: string, crop: CropId, date: string, signal?: AbortSignal) =>
    get<AnalysisResponse>('/api/analysis', { parcel_id: parcelId, crop, date }, signal),
}

export type ErrorInfo = { title: string; message: string; stillWorks?: string; retryable: boolean }

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
      title: `Usługa ${detail?.source ?? 'zewnętrzna'} nie odpowiada`,
      message: `Nie udało się pobrać danych działki (${detail?.message ?? 'błąd usługi'}).`,
      stillWorks,
      retryable: true,
    }
  return { title: 'Błąd serwera', message: `Serwer zwrócił błąd ${e.status}.`, stillWorks, retryable: true }
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
      title: `Usługa ${detail?.source ?? 'zewnętrzna'} nie odpowiada`,
      message: detail?.message ?? 'Nie udało się pobrać danych do analizy.',
      stillWorks,
      retryable: true,
    }
  return { title: 'Błąd serwera', message: `Serwer zwrócił błąd ${e.status}.`, stillWorks, retryable: true }
}
