import type L from 'leaflet'
import { useEffect, useRef, useState } from 'react'
import { useMapContext } from './context'

/** Instancja mapy Leaflet (wewnątrz <MapContainer>). */
export function useMap(): L.Map {
  return useMapContext().map
}

/** Zdarzenia mapy (click, moveend, …); nowy obiekt = ponowne podpięcie. Zwraca mapę. */
export function useMapEvents(handlers: L.LeafletEventHandlerFnMap): L.Map {
  const map = useMap()
  useEffect(() => {
    map.on(handlers)
    return () => {
      map.off(handlers)
    }
  }, [map, handlers])
  return map
}

/**
 * Obiekt Leafletu tworzony raz (przy pierwszym renderze – dzięki temu dzieci, np. Tooltip, mogą się do niego
 * przypiąć, zanim trafi na mapę). Zmiany właściwości przekazuje `update(obiekt, nowe, poprzednie)` po renderze.
 */
export function useLeafletObject<T, P>(create: () => T, props: P, update?: (obj: T, next: P, prev: P) => void): T {
  const [obj] = useState(create)
  const prev = useRef(props)
  useEffect(() => {
    if (prev.current === props) return
    update?.(obj, props, prev.current)
    prev.current = props
  })
  return obj
}

/**
 * Zdarzenia warstwy (`eventHandlers`). Wywoływać PRZED useAddToMap – przy odmontowaniu najpierw odpinamy
 * zdarzenia, potem zdejmujemy warstwę (zdejmowanie z kodu nie wywołuje np. `remove` → „zamknięto dymek”).
 */
export function useLayerEvents(target: L.Evented, handlers?: L.LeafletEventHandlerFnMap) {
  useEffect(() => {
    if (!handlers) return
    target.on(handlers)
    return () => {
      target.off(handlers)
    }
  }, [target, handlers])
}

/** Warstwa na mapie od zamontowania do odmontowania komponentu. */
export function useAddToMap(map: L.Map, layer: L.Layer) {
  useEffect(() => {
    map.addLayer(layer)
    return () => {
      map.removeLayer(layer)
    }
  }, [map, layer])
}

/** Płytkie porównanie opcji (style ścieżek podawane jako nowe obiekty przy każdym renderze). */
export function shallowEqual(a: object | undefined, b: object | undefined): boolean {
  if (a === b) return true
  if (!a || !b) return false
  const ka = Object.keys(a) as (keyof typeof a)[]
  const kb = Object.keys(b)
  return ka.length === kb.length && ka.every((k) => a[k] === b[k])
}

/** Ta sama lista współrzędnych (wielokąty rysowane z nowych tablic przy każdym renderze). */
export const sameJson = (a: unknown, b: unknown) => a === b || JSON.stringify(a) === JSON.stringify(b)
