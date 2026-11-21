/**
 * PROPOZYCJA KONTRAKTU (osoba B → A) – wyszukiwanie miejsca po nazwie: GET /api/places?q=Tczów
 * Jeszcze NIE jest częścią kontraktu (api/types.ts). Po uzgodnieniu z A: przenieść te typy do api/types.ts,
 * backend – app/schemas/places.py, a ten plik usunąć. Opis: .ai/status/b-frontend.md, dziennik B19.
 *
 * Źródło po stronie backendu (propozycja): ULDK GetRegionByNameOrId / GetCommuneByNameOrId
 * (nazwa obrębu / gminy → TERYT, gmina, powiat, granica → bbox).
 *
 * 200 → PlaceSearchResponse (posortowane: najpierw dokładna nazwa, potem początek nazwy)
 * 404 → nic nie znaleziono (ErrorDetail)
 */
export type PlaceKind = 'obreb' | 'gmina'

export type Place = {
  /** TERYT obrębu (np. „141206_2.0012”) albo gminy */
  id: string
  /** nazwa obrębu / gminy, np. „Tczów” */
  name: string
  kind: PlaceKind
  gmina: string
  powiat: string
  wojewodztwo: string
  /** lon_min, lat_min, lon_max, lat_max (EPSG:4326) – do przybliżenia mapy */
  bbox: [number, number, number, number]
}

export type PlaceSearchResponse = {
  places: Place[]
  /** wszystkich pasujących (lista może być przycięta) */
  total: number
}

/** Tekst bez cyfr (i nie identyfikator TERYT) = szukamy miejsca, nie działki. */
export const isPlaceQuery = (q: string) => !/\d/.test(q) && q.trim().length >= 2
