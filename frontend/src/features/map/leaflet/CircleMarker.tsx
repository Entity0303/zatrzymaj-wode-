import L from 'leaflet'
import type { ReactNode } from 'react'
import { MapContext, useMapContext } from './context'
import { useAddToMap, useLayerEvents, useLeafletObject } from './hooks'
import { updatePath, type PathProps } from './path'

type Props = Omit<L.CircleMarkerOptions, keyof PathProps> &
  PathProps & {
    center: L.LatLngExpression
    /** Tooltip / Popup przypinane do kropki */
    children?: ReactNode
  }

/** Kropka o stałym promieniu w pikselach. Zmiany: center, radius, pathOptions, interactive. */
export function CircleMarker(props: Props) {
  const ctx = useMapContext()
  const layer = useLeafletObject(
    () => {
      const { center, pathOptions, eventHandlers: _eh, children: _c, ...options } = props
      return L.circleMarker(center, { ...options, ...pathOptions })
    },
    props,
    (l, next, prev) => {
      if (!L.latLng(next.center).equals(L.latLng(prev.center))) l.setLatLng(next.center)
      if (next.radius != null && next.radius !== prev.radius) l.setRadius(next.radius)
      updatePath(l, next, prev)
    },
  )
  useLayerEvents(layer, props.eventHandlers)
  useAddToMap(ctx.map, layer)
  return props.children ? <MapContext value={{ map: ctx.map, owner: layer }}>{props.children}</MapContext> : null
}
