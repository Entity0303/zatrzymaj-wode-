import {
  CircleCheck,
  CircleDashed,
  CircleAlert,
  TriangleAlert,
  Flame,
  type LucideIcon,
} from 'lucide-react'

/** Statusy wspólne dla mapy, odznak i raportu (SPEC 2.2). */
export type Status = 'ok' | 'warn' | 'risk' | 'danger' | 'nodata'

export const STATUS: Record<
  Status,
  { label: string; icon: LucideIcon; fg: string; bg: string; solid: string; hex: string }
> = {
  ok: { label: 'Dobrze', icon: CircleCheck, fg: 'text-brand', bg: 'bg-ok-soft', solid: 'bg-ok', hex: '#5BB37F' },
  warn: { label: 'Uwaga', icon: CircleAlert, fg: 'text-[#8a6a00]', bg: 'bg-warn-soft', solid: 'bg-warn', hex: '#E8B931' },
  risk: { label: 'Ryzyko', icon: TriangleAlert, fg: 'text-[#a24f17]', bg: 'bg-[#fbeadf]', solid: 'bg-risk', hex: '#E07B39' },
  danger: { label: 'Susza', icon: Flame, fg: 'text-danger', bg: 'bg-danger-soft', solid: 'bg-danger', hex: '#C8453B' },
  nodata: { label: 'Brak danych', icon: CircleDashed, fg: 'text-text-muted', bg: 'hatch-nodata', solid: 'bg-nodata', hex: '#B8BDB9' },
}
