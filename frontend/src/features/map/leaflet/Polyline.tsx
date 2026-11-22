import L from 'leaflet'
import { sameJson, useAddToMap, useLayerEvents, useLeafletObject, useMap } from './hooks'
import { updatePath, type PathProps } from './path'

type Props = Omit<L.PolylineOptions, keyof PathProps> & PathProps & { positions: L.LatLngExpression[] }

/** Linia łamana. Zmiany: positions (po wartości), pathOptions, interactive. */
export function Polyline(props: Props) {
  const map = useMap()
  const layer = useLeafletObject(
    () => {
      const { positions, pathOptions, eventHandlers: _eh, ...options } = props
      return L.polyline(positions, { ...options, ...pathOptions })
    },
    props,
    (l, next, prev) => {
      if (!sameJson(next.positions, prev.positions)) l.setLatLngs(next.positions)
      updatePath(l, next, prev)
    },
  )
  useLayerEvents(layer, props.eventHandlers)
  useAddToMap(map, layer)
  return null
}
