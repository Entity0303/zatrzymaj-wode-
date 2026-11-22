import L from 'leaflet'
import { useAddToMap, useLayerEvents, useLeafletObject, useMap } from './hooks'

type Props = L.TileLayerOptions & { url: string; eventHandlers?: L.LeafletEventHandlerFnMap }

/** Podkład kaflowy {z}/{x}/{y}. Zmiany: url, opacity, zIndex; reszta opcji tylko przy utworzeniu. */
export function TileLayer(props: Props) {
  const map = useMap()
  const layer = useLeafletObject(
    () => {
      const { url, eventHandlers: _eh, ...options } = props
      return L.tileLayer(url, options)
    },
    props,
    (l, next, prev) => {
      if (next.url !== prev.url) l.setUrl(next.url)
      if (next.opacity != null && next.opacity !== prev.opacity) l.setOpacity(next.opacity)
      if (next.zIndex != null && next.zIndex !== prev.zIndex) l.setZIndex(next.zIndex)
    },
  )
  useLayerEvents(layer, props.eventHandlers)
  useAddToMap(map, layer)
  return null
}
