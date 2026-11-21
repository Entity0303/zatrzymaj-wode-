export type DataSource = {
  nazwa: string
  url: string
  pobrano?: string
  uwagi?: string
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

export type Candidates = { total: number; candidates: Parcel[] }

export type WeatherIcon = 'sun' | 'cloud-sun' | 'cloud' | 'fog' | 'drizzle' | 'rain' | 'snow' | 'storm' | 'unknown'

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
  teraz: { czas: string | null; temperatura: number | null; opis: string; ikona: WeatherIcon; dzien: boolean }
  dni: ForecastDay[]
  bilans_okresu_mm: number | null
  zrodlo: DataSource
}

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
