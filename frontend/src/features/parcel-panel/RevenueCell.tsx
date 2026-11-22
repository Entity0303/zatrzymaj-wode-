import { fmtZlRange } from '@/lib/ranges'
import type { CropRevenue, PriceNow } from '@/api/types'
import { formatNum, formatZl } from '@/lib/format'
import { hasRevenue, okZl, priceNowSource } from '@/lib/revenue'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * F8: pola przychodu, które backend dopiero dopisuje (inna sesja) – opcjonalne, brak = nie pokazujemy.
 * `revenue_note` – powód braku ceny skupu dla tej uprawy (np. „GUS nie podaje ceny kiszonki”);
 * F9: `price_source` – gotowy podpis ceny z API przy uprawie bez przychodu (np. „cena z lipca 2026 (ZSRIR)”).
 */
export type RevenueExtras = { revenue_note?: string | null; price_source?: string | null }

/**
 * Kolumna „Przychód z pola” w rankingu „Co tu posiać?”: typowy rok pogrubiony („ok. 2 100 zł”), pod spodem
 * „słaby rok: ok. 1 500 zł”; kwoty do 100 zł. Brak ceny – szary powód z API albo „brak ceny skupu”.
 * Na telefonie (pod plonem) z podpisem „Przychód z pola:”.
 */
export function RevenueCell({
  revenue: r,
  note,
  priceNow,
  priceSource,
  className,
}: {
  /** F9: podpis ceny z API (pozycja rankingu) – pierwszeństwo przed podpisem z ceny bieżącej */
  priceSource?: string | null
  revenue?: CropRevenue | null
  note?: string | null
  /** bieżąca cena tej uprawy (ZSRIR) – przy braku przychodu pokazana szaro, bez liczenia przychodu */
  priceNow?: PriceNow | null
  className?: string
}) {
  const { t } = useLang()
  const label = <span className="text-text-muted sm:hidden">{t('Przychód z pola:')} </span>
  if (!hasRevenue(r))
    return (
      <span className={cn('block text-sm leading-5 text-text-muted', className)}>
        {label}
        {t(note?.trim() || 'brak ceny skupu')}
        {priceNow && Number.isFinite(priceNow.zl_t) && priceNow.zl_t > 0 ? (
          <span className="block">
            {priceSource?.trim() ? t(priceSource.trim()) : priceNowSource(priceNow, t)}: {t('{p} zł/t', { p: formatNum(priceNow.zl_t, 0) })}
          </span>
        ) : (
          priceSource?.trim() && <span className="block">{t(priceSource.trim())}</span>
        )}
      </span>
    )
  return (
    <span className={cn('block text-sm leading-5', className)}>
      <span className="block">
        {label}
        <b className="tabular whitespace-nowrap">{t('ok. {zl}', { zl: fmtZlRange(r) })}</b>
      </span>
      {okZl(r.weak_year_zl) && (
        <span className="block text-text-muted">{t('słaby rok: ok. {zl}', { zl: formatZl(r.weak_year_zl) })}</span>
      )}
    </span>
  )
}
