/**
 * Powierzchnia wielokąta [lon, lat] (WGS84) w hektarach – wzór sferyczny (jak w Leaflet.draw / turf `area`),
 * tylko do podglądu przy rysowaniu pola. Wynik do analizy liczy serwer z kształtu w EPSG:2180.
 */
const R = 6378137

export function ringAreaHa(points: [number, number][]): number {
  if (points.length < 3) return 0
  let sum = 0
  for (let i = 0; i < points.length; i++) {
    const [lon1, lat1] = points[i]
    const [lon2, lat2] = points[(i + 1) % points.length]
    sum += ((lon2 - lon1) * Math.PI) / 180 * (2 + Math.sin((lat1 * Math.PI) / 180) + Math.sin((lat2 * Math.PI) / 180))
  }
  return Math.abs((sum * R * R) / 2) / 10000
}

/** Czy odcinki wielokąta się przecinają (pomijając sąsiednie) – „obrys przecina sam siebie”. */
export function selfIntersects(points: [number, number][]): boolean {
  const n = points.length
  if (n < 4) return false
  const cross = (a: number[], b: number[], c: number[]) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
  const hit = (p1: number[], p2: number[], p3: number[], p4: number[]) =>
    cross(p1, p2, p3) * cross(p1, p2, p4) < 0 && cross(p3, p4, p1) * cross(p3, p4, p2) < 0
  for (let i = 0; i < n; i++)
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue
      if (hit(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n])) return true
    }
  return false
}

/** Zamknięty GeoJSON Polygon z punktów rysowania. */
export function toPolygon(points: [number, number][]): GeoJSON.Polygon {
  return { type: 'Polygon', coordinates: [[...points, points[0]]] }
}

/** Limity obrysu – te same co w backendzie (A5c): 0,05–200 ha. */
export const MIN_HA = 0.05
export const MAX_HA = 200

/** Co jest nie tak z obrysem (klucz tłumaczenia) albo null, gdy można liczyć. */
export function drawProblem(points: [number, number][]): string | null {
  if (points.length < 3) return null
  const ha = ringAreaHa(points)
  if (selfIntersects(points)) return 'Obrys przecina sam siebie – cofnij ostatni punkt.'
  if (ha < MIN_HA) return 'Pole jest za małe – najmniej 0,05 ha (500 m²).'
  if (ha > MAX_HA) return 'Pole jest za duże – najwyżej 200 ha. Narysuj jedną działkę.'
  return null
}

