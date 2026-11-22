import type L from 'leaflet'
import { createContext, use } from 'react'

/**
 * Własna, cienka warstwa React nad Leafletem (BSD-2-Clause) – zamiast react-leaflet (Hippocratic License).
 * Kontekst: instancja mapy + warstwa „właściciel”, do której dymki (Tooltip / Popup) w środku są przypinane.
 */
export type MapCtx = {
  map: L.Map
  /** warstwa nadrzędna (Marker, CircleMarker, …) – Tooltip i Popup w środku przypinają się do niej */
  owner?: L.Layer
}

export const MapContext = createContext<MapCtx | null>(null)

export function useMapContext(): MapCtx {
  const ctx = use(MapContext)
  if (!ctx) throw new Error('Komponent mapy musi być wewnątrz <MapContainer>')
  return ctx
}
