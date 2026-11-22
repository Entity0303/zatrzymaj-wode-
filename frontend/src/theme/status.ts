import {
  CircleCheck,
  CircleDashed,
  CircleAlert,
  TriangleAlert,
  Flame,
  type LucideIcon,
} from 'lucide-react'
import type { StatusLevel, VerdictLevel } from '@/api/types'

/** Statusy wspólne dla mapy, odznak i raportu (SPEC 2.2) – wartości jak w kontrakcie API. */
export type Status = StatusLevel

export const STATUS: Record<
  Status,
  { label: string; icon: LucideIcon; fg: string; bg: string; solid: string; hex: string; ring: { color: string; track: string } }
> = {
  ok: { label: 'Dobrze', icon: CircleCheck, fg: 'text-brand', bg: 'bg-ok-soft', solid: 'bg-ok', hex: '#5F9F63', ring: { color: 'var(--color-ok)', track: 'var(--color-ok-soft)' } },
  warn: { label: 'Uwaga', icon: CircleAlert, fg: 'text-[#875a12]', bg: 'bg-warn-soft', solid: 'bg-warn', hex: '#E2A23B', ring: { color: 'var(--color-warn)', track: 'var(--color-warn-soft)' } },
  risk: { label: 'Ryzyko', icon: TriangleAlert, fg: 'text-[#a24f17]', bg: 'bg-[#f9e8dc]', solid: 'bg-risk', hex: '#D9773A', ring: { color: 'var(--color-risk)', track: '#f9e8dc' } },
  danger: { label: 'Susza', icon: Flame, fg: 'text-danger', bg: 'bg-danger-soft', solid: 'bg-danger', hex: '#C0473C', ring: { color: 'var(--color-danger)', track: 'var(--color-danger-soft)' } },
  no_data: { label: 'Brak danych', icon: CircleDashed, fg: 'text-text-muted', bg: 'hatch-nodata', solid: 'bg-nodata', hex: '#B8BDB5', ring: { color: 'var(--color-nodata)', track: 'var(--color-nodata-soft)' } },
}

/**
 * „Teraz: …” – stan wody dziś (status analizy). Razem z oceną na lata (werdykt) daje jedno zdanie bez pozornej
 * sprzeczności: „Teraz: woda w normie · Na dłuższą metę: wysokie ryzyko suszy”.
 */
export const NOW_LABEL: Record<Status, string> = {
  ok: 'woda w normie',
  warn: 'mało wody',
  risk: 'brakuje wody',
  danger: 'susza',
  no_data: 'brak danych',
}

/** „Na dłuższą metę: …” – ryzyko suszy na tej działce w latach (werdykt). */
export const LONG_TERM_LABEL: Record<VerdictLevel, string> = {
  ok: 'niskie ryzyko suszy',
  warn: 'średnie ryzyko suszy',
  bad: 'wysokie ryzyko suszy',
}
