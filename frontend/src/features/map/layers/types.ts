import type { LucideIcon } from 'lucide-react'
import type { ComponentType } from 'react'
import type { LayerKey, Parcel } from '@/api/types'

export type { LayerKey }

export type LegendSpec =
  | { kind: 'gradient'; colors: string[]; left: string; right: string; note?: string }
  | { kind: 'classes'; items: { color: string; label: string }[]; note?: string }
  | { kind: 'symbols'; items: { symbol: 'arrow' | 'spot' | 'outflow' | 'line' | 'pin'; label: string }[] }

/** Co dostaje warstwa rysowana wewnątrz mapy (react-leaflet). */
export type LayerOverlayProps = { parcel: Parcel; analysisDate: string }

/** Jedna warstwa mapy (SPEC 5.3) = jeden plik w tym katalogu. */
export type MapLayer = {
  key: LayerKey
  label: string
  short: string
  icon: LucideIcon
  legend: LegendSpec
  /** Rysowanie danych przyciętych do obrysu działki; null = warstwa jeszcze nie liczona. */
  Overlay: ComponentType<LayerOverlayProps> | null
}
