import type { AnalysisResponse } from '@/api/types'

export type SeasonKind = 'suchy sezon' | 'normalny sezon' | 'mokry sezon'

/**
 * Jedna liczba „ile wody zostało od początku sezonu” – ta sama w dolnej karcie „Bilans wody”, w paszporcie
 * i w raporcie: słupek bieżącego roku z `seasonal_balance_by_year` (A5e), a bez niego wskaźnik
 * `indicators.water_balance_season`, na końcu ostatni punkt serii narastającej.
 * Rodzaj sezonu z rankingu lat (`history.balance_rank`): suszej było w ≤ 30% lat = suchy, mokrzej w ≤ 30% = mokry.
 */
export function seasonBalance(a: AnalysisResponse): { mm: number | null; kind: SeasonKind | null; from: string } {
  const h = a.history
  const bar = a.seasonal_balance_by_year?.find((y) => y.current)
  let mm: number | null = bar?.balance_mm ?? a.indicators.water_balance_season.value ?? null
  if (mm == null) {
    for (let i = h.balance_cumulative.length - 1; i >= 0; i--) {
      const v = h.balance_cumulative[i].value
      if (v != null) {
        mm = v
        break
      }
    }
  }
  const r = h.balance_rank
  let kind: SeasonKind | null = null
  if (r && r.of_years > 0) {
    const limit = Math.floor(r.of_years * 0.3)
    kind = r.lower_years <= limit ? 'suchy sezon' : r.of_years - r.lower_years <= limit ? 'mokry sezon' : 'normalny sezon'
  }
  return { mm: mm == null ? null : Math.round(mm), kind, from: h.season_start }
}
