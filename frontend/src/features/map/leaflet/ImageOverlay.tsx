import L from 'leaflet'
import { useAddToMap, useLayerEvents, useLeafletObject, useMap } from './hooks'

type Props = L.ImageOverlayOptions & {
  url: string
  bounds: L.LatLngBoundsExpression
  eventHandlers?: L.LeafletEventHandlerFnMap
}

/** Obraz w granicach `bounds` (raster warstwy). Zmiany: url, bounds (po wartości), opacity, zIndex. */
export function ImageOverlay(props: Props) {
  const map = useMap()
  const layer = useLeafletObject(
    () => {
      const { url, bounds, eventHandlers: _eh, ...options } = props
      return L.imageOverlay(url, bounds, options)
    },
    props,
    (l, next, prev) => {
      if (next.url !== prev.url) l.setUrl(next.url)
      const b = L.latLngBounds(next.bounds as L.LatLngBoundsLiteral)
      if (!b.equals(L.latLngBounds(prev.bounds as L.LatLngBoundsLiteral))) l.setBounds(b)
      if (next.opacity != null && next.opacity !== prev.opacity) l.setOpacity(next.opacity)
      if (next.zIndex != null && next.zIndex !== prev.zIndex) l.setZIndex(next.zIndex)
    },
  )
  useLayerEvents(layer, props.eventHandlers)
  useAddToMap(map, layer)
  return null
}
