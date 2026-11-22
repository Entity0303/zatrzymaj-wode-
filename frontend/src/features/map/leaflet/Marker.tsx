import L from 'leaflet'
import type { ReactNode } from 'react'
import { MapContext, useMapContext } from './context'
import { useAddToMap, useLayerEvents, useLeafletObject } from './hooks'

type Props = L.MarkerOptions & {
  position: L.LatLngExpression
  eventHandlers?: L.LeafletEventHandlerFnMap
  /** Tooltip / Popup przypinane do znacznika */
  children?: ReactNode
}

const sameIcon = (a: L.Icon | L.DivIcon | undefined, b: L.Icon | L.DivIcon | undefined) =>
  a === b || (!!a && !!b && JSON.stringify(a.options) === JSON.stringify(b.options))

/** Znacznik punktowy. Zmiany: position, icon (po opcjach), title, opacity, zIndexOffset. */
export function Marker(props: Props) {
  const ctx = useMapContext()
  const layer = useLeafletObject(
    () => {
      const { position, eventHandlers: _eh, children: _c, ...options } = props
      return L.marker(position, options)
    },
    props,
    (m, next, prev) => {
      if (!L.latLng(next.position).equals(L.latLng(prev.position))) m.setLatLng(next.position)
      if (next.icon && !sameIcon(next.icon, prev.icon)) m.setIcon(next.icon)
      if (next.title !== prev.title) {
        m.options.title = next.title
        m.getElement()?.setAttribute('title', next.title ?? '')
      }
      if (next.opacity != null && next.opacity !== prev.opacity) m.setOpacity(next.opacity)
      if (next.zIndexOffset != null && next.zIndexOffset !== prev.zIndexOffset) m.setZIndexOffset(next.zIndexOffset)
    },
  )
  useLayerEvents(layer, props.eventHandlers)
  useAddToMap(ctx.map, layer)
  return props.children ? <MapContext value={{ map: ctx.map, owner: layer }}>{props.children}</MapContext> : null
}
