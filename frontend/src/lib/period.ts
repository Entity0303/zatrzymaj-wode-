import type { PeriodPreset } from '@/api/types'
import { minAnalysisIso, todayIso } from './dates'

/**
 * Okres analizy (F3) jako krótki znacznik – ten sam w adresie (`?okres=`) i w stanie aplikacji:
 * `30d` · `od_siewu` · `sezon` · `RRRR-MM-DD_RRRR-MM-DD` (własny zakres od–do).
 * Do zapytania: `period=30d|since_sowing|season` albo `date_from=&date_to=`.
 */
export type PeriodToken = string

const PRESETS: Record<string, PeriodPreset> = { '30d': '30d', od_siewu: 'since_sowing', sezon: 'season' }

export const PERIOD_OPTIONS: { token: PeriodToken; label: string; hint: string; needsCrop?: boolean }[] = [
  { token: '30d', label: 'Ostatnie 30 dni', hint: 'ile spadło i wyparowało przez ostatni miesiąc' },
  { token: 'od_siewu', label: 'Od siewu', hint: 'od siewu wybranej uprawy do daty analizy', needsCrop: true },
  { token: 'sezon', label: 'Sezon (1.04–30.09)', hint: 'cały sezon wegetacyjny' },
]

const isIso = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v))

/** Własny zakres: oba końce w dozwolonym przedziale (dziś − 10 lat … dziś), od ≤ do. */
export function customRange(token: PeriodToken | null): { from: string; to: string } | null {
  const m = token?.match(/^(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})$/)
  if (!m || !isIso(m[1]) || !isIso(m[2])) return null
  const [from, to] = [m[1], m[2]]
  return from <= to && from >= minAnalysisIso() && to <= todayIso() ? { from, to } : null
}

/** Znacznik z adresu albo null, gdy nieznany / poza zakresem. */
export function parsePeriod(v: string | null): PeriodToken | null {
  if (!v) return null
  if (v in PRESETS) return v
  return customRange(v) ? v : null
}

/** Parametry zapytania analizy dla okresu. */
export function periodParams(token: PeriodToken | null | undefined): Record<string, string> {
  if (!token) return {}
  if (token in PRESETS) return { period: PRESETS[token] }
  const r = customRange(token)
  return r ? { date_from: r.from, date_to: r.to } : {}
}

/** Krótki opis na przycisku („Ostatnie 30 dni”, „1.05–30.06.2026”). */
export function periodShortLabel(token: PeriodToken): string {
  const opt = PERIOD_OPTIONS.find((o) => o.token === token)
  if (opt) return opt.label
  const r = customRange(token)
  if (!r) return ''
  const d = (iso: string, year: boolean) => {
    const [y, m, dd] = iso.split('-')
    return `${Number(dd)}.${m}${year ? `.${y}` : ''}`
  }
  return `${d(r.from, r.from.slice(0, 4) !== r.to.slice(0, 4))}–${d(r.to, true)}`
}
