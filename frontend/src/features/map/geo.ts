import L from 'leaflet'
import type { Parcel } from '@/api/types'

/** Marginesy (px), w których nie ma zasłaniających mapę paneli – do flyToBounds. */
export type MapInsets = { top: number; right: number; bottom: number; left: number }

export function parcelBounds(p: Parcel) {
  return L.geoJSON(p.geometria).getBounds()
}

/** Czy punkt leży w poligonie działki (ray casting, wystarczające dla małych obszarów). */
export function parcelContains(p: Parcel, lon: number, lat: number): boolean {
  const polys = p.geometria.type === 'Polygon' ? [p.geometria.coordinates] : p.geometria.coordinates
  return polys.some((rings) => {
    let inside = false
    rings.forEach((ring, ri) => {
      let c = false
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i]
        const [xj, yj] = ring[j]
        if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) c = !c
      }
      if (ri === 0) inside = c
      else if (c) inside = false // otwór
    })
    return inside
  })
}
