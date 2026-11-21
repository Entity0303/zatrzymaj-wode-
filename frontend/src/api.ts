export type Parcel = {
  id: string
  voivodeship: string
  county: string
  commune: string
  region: string
  number: string
  teryt_commune: string
  area_ha: number
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon
  source: string
}

export type SoilShare = { code: number; label: string; share: number }

export type Soil = {
  parcel_id: string
  dominant_code: number | null
  dominant_label: string | null
  shares: SoilShare[]
  agricultural_share: number
  wod_mm: number | null
  source: string
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    const msg =
      typeof detail === 'string'
        ? detail
        : ((detail as { message?: string })?.message ?? `Błąd ${status}`)
    super(msg)
    this.status = status
    this.detail = detail
  }
}

async function get<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))
  const res = await fetch(`${path}?${qs}`)
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body)
  return body as T
}

export const api = {
  parcelById: (id: string) => get<Parcel>('/api/parcel', { id }),
  parcelByPoint: (lon: number, lat: number) => get<Parcel>('/api/parcel', { lon, lat }),
  soil: (id: string) => get<Soil>('/api/soil', { id }),
}
