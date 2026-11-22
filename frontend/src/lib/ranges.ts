import type { CropRevenue, CropSuggestion } from '@/api/types'
import { formatNum, formatZl } from './format'

/**
 * F21: widełki wyniku rankingu z backendu A21 (pola *_range – warianty opadu i pojemności gleby).
 * Zakres pokazujemy, gdy min ≠ max; gdy równe albo brak – jedna liczba (wartość główna).
 */
export type Span = { min: number; max: number }

/** [min, max] z API → Span (null, gdy brak / niepoprawne). */
export function span(r: readonly number[] | null | undefined): Span | null {
  if (!r || r.length < 2 || r[0] == null || r[1] == null || !Number.isFinite(r[0]) || !Number.isFinite(r[1])) return null
  return { min: Math.min(r[0], r[1]), max: Math.max(r[0], r[1]) }
}

const join = (a: string, b: string) => (a === b ? a : `${a}–${b}`)

/** „3,4–3,9” albo „3,6” (1 miejsce po przecinku). */
export function fmtNumRange(r: readonly number[] | null | undefined, value: number | null | undefined, digits = 1): string | null {
  const s = span(r)
  if (s) return join(formatNum(s.min, digits), formatNum(s.max, digits))
  return value == null ? null : formatNum(value, digits)
}

/** Przychód: „4 600–5 200 zł” albo „4 900 zł” (bez „ok.” – dodaje tekst wokół). */
export function fmtZlRange(rev: CropRevenue): string {
  const s = span(rev.revenue_range)
  if (!s) return formatZl(rev.typical_zl)
  const a = formatZl(s.min).replace(/ zł$/, '')
  const b = formatZl(s.max).replace(/ zł$/, '')
  return a === b ? formatZl(s.min) : `${a}–${b} zł`
}

/** Ryzyko suszy: lata ze stratą > 20% – zakres [min, max] (F18: też dawna nazwa risk_years_range). */
export function riskSpan(s: CropSuggestion): Span {
  const r = span(s.drought_risk_range ?? (s as CropSuggestion & { risk_years_range?: number[] | null }).risk_years_range)
  return r ?? { min: s.drought_risk_years, max: s.drought_risk_years }
}

/** „1–4” albo „3”. */
export function fmtRisk(s: CropSuggestion): string {
  const r = riskSpan(s)
  return join(String(r.min), String(r.max))
}
