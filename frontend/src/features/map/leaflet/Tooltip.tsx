import L from 'leaflet'
import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useMapContext } from './context'
import { createContentNode } from './content'
import { useLeafletObject } from './hooks'

type Props = L.TooltipOptions & { children?: ReactNode }

/**
 * Dymek przypięty do warstwy nadrzędnej (Marker, CircleMarker, …). Opcje (permanent, direction, offset, …)
 * tylko przy utworzeniu; treść = dzieci React (portal) – po zmianie treści otwarty dymek przelicza położenie.
 */
export function Tooltip({ children, ...options }: Props) {
  const { owner } = useMapContext()
  const [content] = useState(createContentNode)
  const tooltip = useLeafletObject(() => L.tooltip(options).setContent(content), options)

  useEffect(() => {
    if (!owner) return
    owner.bindTooltip(tooltip)
    return () => {
      if (owner.getTooltip() === tooltip) owner.unbindTooltip()
    }
  }, [owner, tooltip])

  // po każdym renderze treści: wymiary / wyśrodkowanie otwartego dymka
  useEffect(() => {
    if (tooltip.isOpen()) tooltip.update()
  })

  return createPortal(children, content)
}
