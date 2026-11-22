import { Coins } from 'lucide-react'
import type { CropRevenue, PriceNow } from '@/api/types'
import { formatHa, formatNum, formatZl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** „10–16.11.2026” → „10–16.11” */
const shortWeek = (w: string) => w.replace(/\.\d{4}$/, '')

/**
 * Przychód z pola (F3, `revenue`): „ok. 7 900 zł z pola (w słabym roku ok. 5 600 zł)”, małym drukiem cena i źródło
 * (GUS – zawsze); w szczegółach cena za tonę i „cena teraz: 840 zł/t (ZSRIR, 10–16.11)”. Brak `revenue` – nic (stary backend).
 */
export function RevenueLine({
  revenue: r,
  priceNow,
  details,
  className,
}: {
  revenue?: CropRevenue | null
  /** bieżąca cena tej uprawy (analysis.price_now) */
  priceNow?: PriceNow | null
  /** pokaż cenę i źródło (rozwinięta pozycja) */
  details?: boolean
  className?: string
}) {
  const { t } = useLang()
  if (!r) return null
  return (
    <span className={cn('block text-sm leading-5', className)}>
      <span className="flex items-start gap-1.5">
        <Coins className="mt-0.5 size-4 shrink-0 text-amber" aria-hidden />
        <span>
          {t('ok. {zl} z pola', { zl: formatZl(r.typical_zl) })}
          <span className="text-text-muted"> ({t('w słabym roku ok. {zl}', { zl: formatZl(r.weak_year_zl) })})</span>
        </span>
      </span>
      <span className="mt-0.5 block pl-[22px] text-xs leading-4 text-text-muted">
        {details ? t('{p} zł/t × plon z {area} ha', { p: formatNum(r.price_zl_t, 0), area: formatHa(r.for_area_ha) }) + ' · ' : ''}
        {t(r.price_source)}
        {details && priceNow && (
          <span className="block">
            {t('cena teraz: {p} zł/t ({src}, {week})', { p: formatNum(priceNow.zl_t, 0), src: priceNow.source.split(' ')[0], week: shortWeek(priceNow.week) })}
          </span>
        )}
      </span>
    </span>
  )
}
