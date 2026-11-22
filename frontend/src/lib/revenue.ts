import type { CropRevenue, PriceNow } from '@/api/types'

/** F8: pomocnicze do kolumny „Przychód z pola” (features/parcel-panel/RevenueCell). */

const MONTHS_GEN = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia']

/** Tydzień notowania ZSRIR („10–16.11.2026”, „05.07.2026”) → „lipca 2026”; nieznany format – tekst bez zmian. */
export function priceNowMonth(week: string): string {
  const m = week.match(/(\d{1,2})\.(\d{2})\.(\d{4})\s*$/)
  const month = m ? MONTHS_GEN[Number(m[2]) - 1] : undefined
  return m && month ? `${month} ${m[3]}` : week
}

/**
 * F9: podpis ceny bieżącej z API (`price_now[].price_source`, np. „cena z lipca 2026 (ZSRIR)”) – pole opcjonalne,
 * dopisywane przez backend; brak = podpis składany z tygodnia notowania i źródła (zachowanie z F8).
 */
export type PriceNowExtras = PriceNow & { price_source?: string | null }

export function priceNowSource(p: PriceNowExtras, t: (key: string, vars?: Record<string, string | number>) => string): string {
  const api = p.price_source?.trim()
  return api ? t(api) : t('cena z {m} ({src})', { m: priceNowMonth(p.week), src: p.source.split(' ')[0] })
}

/** Kwota nadaje się do pokazania (nigdy „0 zł”, „NaN”, „null”). */
export const okZl = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0

/** Przychód z pola nadaje się do pokazania – typowy rok > 0 zł. */
export const hasRevenue = (r: CropRevenue | null | undefined): r is CropRevenue => !!r && okZl(r.typical_zl)
