import L from 'leaflet'
import type { ReactNode } from 'react'
import { MapContext, useMapContext } from './context'
import { useAddToMap, useLayerEvents, useLeafletObject } from './hooks'

type Props = L.GeoJSONOptions & {
  /** dane wczytywane tylko przy utworzeniu – nowe dane = nowy `key` */
  data: GeoJSON.GeoJsonObject
  eventHandlers?: L.LeafletEventHandlerFnMap
  children?: ReactNode
}

/** Obiekty GeoJSON. `style` (obiekt lub funkcja) aktualizowany przy zmianie; reszta opcji przy utworzeniu. */
export function GeoJSON(props: Props) {
  const ctx = useMapContext()
  const layer = useLeafletObject(
    () => {
      const { data, eventHandlers: _eh, children: _c, ...options } = props
      return L.geoJSON(data, options)
    },
    props,
    (l, next, prev) => {
      if (next.style === prev.style) return
      if (next.style == null) l.resetStyle()
      else l.setStyle(next.style)
    },
  )
  useLayerEvents(layer, props.eventHandlers)
  useAddToMap(ctx.map, layer)
  return props.children ? <MapContext value={{ map: ctx.map, owner: layer }}>{props.children}</MapContext> : null
}
