import L from 'leaflet'
import { shallowEqual } from './hooks'

/** Wspólne właściwości ścieżek (CircleMarker, Polygon, Polyline). */
export type PathProps = {
  /** styl ścieżki – porównywany po wartości, zmiana = setStyle */
  pathOptions?: L.PathOptions
  interactive?: boolean
  eventHandlers?: L.LeafletEventHandlerFnMap
}

/**
 * Aktualizacja stylu i klikalności ścieżki. Leaflet nie ma settera `interactive` – przełączamy opcję i klasę
 * `leaflet-interactive` (ona decyduje o pointer-events), np. pierwszy wierzchołek rysowanego pola staje się
 * klikalny dopiero przy ≥ 3 punktach.
 */
export function updatePath(layer: L.Path, next: PathProps, prev: PathProps) {
  if (!shallowEqual(next.pathOptions, prev.pathOptions)) layer.setStyle(next.pathOptions ?? {})
  const on = next.interactive ?? true
  if (on !== (prev.interactive ?? true)) {
    layer.options.interactive = on
    const el = layer.getElement()
    if (el) L.DomUtil[on ? 'addClass' : 'removeClass'](el as HTMLElement, 'leaflet-interactive')
  }
}
