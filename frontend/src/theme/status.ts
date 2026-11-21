import {
  CircleCheck,
  CircleDashed,
  CircleAlert,
  TriangleAlert,
  Flame,
  type LucideIcon,
} from 'lucide-react'
import type { StatusLevel } from '@/api/types'

/** Statusy wspólne dla mapy, odznak i raportu (SPEC 2.2) – wartości jak w kontrakcie API. */
export type Status = StatusLevel

export const STATUS: Record<
  Status,
  { label: string; icon: LucideIcon; fg: string; bg: string; solid: string; hex: string; ring: { color: string; track: string } }
> = {
  ok: { label: 'Dobrze', icon: CircleCheck, fg: 'text-brand', bg: 'bg-ok-soft', solid: 'bg-ok', hex: '#5BB37F', ring: { color: 'var(--color-ok)', track: 'var(--color-ok-soft)' } },
  warn: { label: 'Uwaga', icon: CircleAlert, fg: 'text-[#8a6a00]', bg: 'bg-warn-soft', solid: 'bg-warn', hex: '#E8B931', ring: { color: 'var(--color-warn)', track: 'var(--color-warn-soft)' } },
  risk: { label: 'Ryzyko', icon: TriangleAlert, fg: 'text-[#a24f17]', bg: 'bg-[#fbeadf]', solid: 'bg-risk', hex: '#E07B39', ring: { color: 'var(--color-risk)', track: '#fbeadf' } },
  danger: { label: 'Susza', icon: Flame, fg: 'text-danger', bg: 'bg-danger-soft', solid: 'bg-danger', hex: '#C8453B', ring: { color: 'var(--color-danger)', track: 'var(--color-danger-soft)' } },
  no_data: { label: 'Brak danych', icon: CircleDashed, fg: 'text-text-muted', bg: 'hatch-nodata', solid: 'bg-nodata', hex: '#B8BDB9', ring: { color: 'var(--color-nodata)', track: 'var(--color-nodata-soft)' } },
}
