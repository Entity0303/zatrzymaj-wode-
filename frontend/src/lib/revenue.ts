import type { CropRevenue } from '@/api/types'

/** F8: pomocnicze do kolumny „Przychód z pola” (features/parcel-panel/RevenueCell). */

const MONTHS_GEN = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia']

/** Tydzień notowania ZSRIR („10–16.11.2026”, „05.07.2026”) → „lipca 2026”; nieznany format – tekst bez zmian. */
export function priceNowMonth(week: string): string {
  const m = week.match(/(\d{1,2})\.(\d{2})\.(\d{4})\s*$/)
  const month = m ? MONTHS_GEN[Number(m[2]) - 1] : undefined
  return m && month ? `${month} ${m[3]}` : week
}

/** Kwota nadaje się do pokazania (nigdy „0 zł”, „NaN”, „null”). */
export const okZl = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0

/** Przychód z pola nadaje się do pokazania – typowy rok > 0 zł. */
export const hasRevenue = (r: CropRevenue | null | undefined): r is CropRevenue => !!r && okZl(r.typical_zl)
