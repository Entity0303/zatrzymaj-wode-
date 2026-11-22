import L from 'leaflet'
import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useMapContext } from './context'
import { createContentNode } from './content'
import { useLayerEvents, useLeafletObject } from './hooks'

type Props = L.PopupOptions & {
  /** samodzielny dymek w punkcie (bez warstwy nadrzędnej) – otwierany od razu */
  position?: L.LatLngExpression
  eventHandlers?: L.LeafletEventHandlerFnMap
  children?: ReactNode
}

/**
 * Okienko po kliknięciu. Wewnątrz warstwy (CircleMarker, Marker) – przypięte do niej, otwiera się po kliknięciu;
 * z `position` – otwarte od razu w tym punkcie. Treść = dzieci React (portal, działają przyciski i onClick).
 * Zdejmowanie z kodu (odmontowanie) nie wywołuje `eventHandlers.remove` – tylko zamknięcie przez użytkownika / mapę.
 */
export function Popup({ children, position, eventHandlers, ...options }: Props) {
  const { map, owner } = useMapContext()
  const [content] = useState(createContentNode)
  const popup = useLeafletObject(() => L.popup(options).setContent(content), options)
  const pos = position ? L.latLng(position) : null
  const lat = pos?.lat
  const lng = pos?.lng

  useLayerEvents(popup, eventHandlers)

  useEffect(() => {
    if (owner) owner.bindPopup(popup)
    else if (lat != null && lng != null) popup.setLatLng([lat, lng]).openOn(map)
    return () => {
      if (owner && owner.getPopup() === popup) owner.unbindPopup()
      map.removeLayer(popup)
    }
  }, [map, owner, popup, lat, lng])

  // po każdym renderze treści: rozmiar i położenie otwartego okienka
  useEffect(() => {
    if (popup.isOpen()) popup.update()
  })

  return createPortal(children, content)
}
