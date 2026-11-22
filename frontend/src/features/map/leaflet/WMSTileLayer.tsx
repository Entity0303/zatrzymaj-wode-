import L from 'leaflet'
import { shallowEqual, useAddToMap, useLayerEvents, useLeafletObject, useMap } from './hooks'

type Props = L.TileLayerOptions & {
  url: string
  /** parametry zapytania WMS (layers, format, transparent, …) */
  params?: L.WMSParams
  eventHandlers?: L.LeafletEventHandlerFnMap
}

/** Warstwa WMS. Zmiana parametrów (po wartości) = setParams; opacity / zIndex na bieżąco. */
export function WMSTileLayer(props: Props) {
  const map = useMap()
  const layer = useLeafletObject(
    () => {
      const { url, params, eventHandlers: _eh, ...options } = props
      return L.tileLayer.wms(url, { ...params, ...options })
    },
    props,
    (l, next, prev) => {
      if (next.params && !shallowEqual(next.params, prev.params)) l.setParams(next.params)
      if (next.opacity != null && next.opacity !== prev.opacity) l.setOpacity(next.opacity)
      if (next.zIndex != null && next.zIndex !== prev.zIndex) l.setZIndex(next.zIndex)
    },
  )
  useLayerEvents(layer, props.eventHandlers)
  useAddToMap(map, layer)
  return null
}
