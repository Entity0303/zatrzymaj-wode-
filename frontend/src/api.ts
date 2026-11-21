export type DataSource = {
  nazwa: string
  url: string
  pobrano: string
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

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? (detail as { message?: string })?.message ?? `Błąd ${status}`)
    this.status = status
    this.detail = detail
  }
}

async function get<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))
  let res: Response
  try {
    res = await fetch(`${path}?${qs}`)
  } catch {
    throw new ApiError(0, null, 'Brak połączenia z serwerem aplikacji. Sprawdź internet.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body)
  return body as T
}

export const api = {
  parcelById: (id: string) => get<Parcel>('/api/parcel', { id }),
  parcelByPoint: (lon: number, lat: number) =>
    get<Parcel>('/api/parcel', { lon: lon.toFixed(7), lat: lat.toFixed(7) }),
}

/** Tłumaczy błąd API na prosty komunikat dla rolnika. */
export function describeError(e: unknown, kind: 'number' | 'point'): string {
  if (!(e instanceof ApiError)) return 'Coś poszło nie tak. Spróbuj ponownie.'
  const detail = e.detail as { source?: string; message?: string } | null
  if (e.status === 0) return e.message
  if (e.status === 404) {
    if (detail?.message?.includes('poza Polską')) return 'To miejsce leży poza Polską.'
    return kind === 'point'
      ? 'W tym miejscu nie znaleziono działki ewidencyjnej (np. droga, woda). Kliknij w pole uprawne.'
      : 'Nie znaleziono działki o takim numerze. Sprawdź pisownię, np. „Szczytno 112/11” albo pełny identyfikator.'
  }
  if (e.status === 502)
    return `Usługa ${detail?.source ?? 'zewnętrzna'} chwilowo nie odpowiada (${detail?.message ?? 'błąd'}). Spróbuj ponownie za chwilę.`
  if (e.status === 422) return 'Wpisz numer działki albo kliknij pole na mapie.'
  return `Błąd serwera (${e.status}). Spróbuj ponownie.`
}
