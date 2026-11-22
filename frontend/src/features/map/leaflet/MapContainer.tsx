import L from 'leaflet'
import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { MapContext, type MapCtx } from './context'

type Props = L.MapOptions & {
  center: L.LatLngExpression
  zoom: number
  className?: string
  style?: CSSProperties
  id?: string
  'aria-label'?: string
  children?: ReactNode
}

/**
 * Mapa Leaflet. Opcje (center, zoom, minZoom, …) brane tylko przy utworzeniu – potem widok zmienia kod
 * (setView / flyToBounds przez ref). Dzieci renderowane dopiero, gdy mapa istnieje; ref = instancja L.Map.
 */
export const MapContainer = forwardRef<L.Map, Props>(function MapContainer(
  { center, zoom, className, style, id, 'aria-label': ariaLabel, children, ...options },
  ref,
) {
  const divRef = useRef<HTMLDivElement>(null)
  const [ctx, setCtx] = useState<MapCtx | null>(null)
  const initial = useRef({ center, zoom, options })

  // do czasu utworzenia mapy ref.current = null (jak wcześniej)
  useImperativeHandle(ref, () => ctx?.map as L.Map, [ctx])

  useEffect(() => {
    const el = divRef.current
    if (!el) return
    const { center: c, zoom: z, options: o } = initial.current
    const map = L.map(el, { ...o, center: c, zoom: z })
    setCtx({ map })
    return () => {
      setCtx(null)
      map.remove()
    }
  }, [])

  return (
    <>
      <div ref={divRef} id={id} className={className} style={style} aria-label={ariaLabel} />
      {ctx && <MapContext value={ctx}>{children}</MapContext>}
    </>
  )
})
