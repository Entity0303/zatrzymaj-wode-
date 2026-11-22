import { fmtNumRange, fmtRevenue, fmtRisk } from '@/lib/ranges'
import { CircleAlert, CircleCheck, CircleX, type LucideIcon } from 'lucide-react'
import type { CropSuggestion, PriceNow, SuggestionCategory } from '@/api/types'
import { formatNum, formatZl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { okZl, priceNowSource } from '@/lib/revenue'
import type { RevenueExtras } from './RevenueCell'

/** ✅ / 🟡 / ❌ – te same kolory co werdykt i raport PDF. */
const CROP_CAT: Record<SuggestionCategory, { icon: LucideIcon; color: string; label: string }> = {
  polecane: { icon: CircleCheck, color: '#5BB37F', label: 'polecane' },
  mozliwe: { icon: CircleAlert, color: '#E8B931', label: 'możliwe' },
  odradzane: { icon: CircleX, color: '#C8453B', label: 'odradzane' },
}

const num = (v: number | null | undefined) => (v == null ? null : formatNum(v, 1))

/** Części drugiej linii – każda bez łamania w środku, zawijanie tylko między częściami. */
function Parts({ parts, className }: { parts: string[]; className?: string }) {
  return (
    <span className={className}>
      {parts.map((p, i) => (
        <span key={p} className="whitespace-nowrap">
          {i > 0 && ' · '}
          {p}
        </span>
      ))}
    </span>
  )
}

/**
 * Uprawa w 2–3 liniach (dopisek do F8/F6 – wąski panel i paszport < 560 px, zamiast tabeli):
 * 1) ikona statusu + nazwa (pogrubiona) … po prawej przychód „ok. 1 200 zł” (pogrubiony);
 * 2) „typowo 3,2 t/ha · ok. 1,9 t z pola” (szary); 3) „słaby rok: ok. 900 zł · ryzyko 3 na 10 lat” (mały, szary).
 * Brak ceny – po prawej „brak ceny”, powód z API w trzeciej linii.
 */
export function CropLine({ s, priceNow }: { s: CropSuggestion; priceNow?: PriceNow | null }) {
  const { t } = useLang()
  const c = CROP_CAT[s.category]
  const Icon = c.icon
  const rev = s.revenue && okZl(s.revenue.typical_zl) ? s.revenue : null
  const note = (s as CropSuggestion & RevenueExtras).revenue_note
  const typ = fmtNumRange(s.yield_typical_range, s.yield_typical_t_ha)
  const line2 = typ
    ? [t('typowo {v} t/ha', { v: typ }), ...(s.total_typical_t != null ? [t('ok. {v} t z pola', { v: num(s.total_typical_t) ?? '' })] : [])]
    : [t('Brak danych o plonie')]
  const risk = t('ryzyko {n} na {of} lat', { n: fmtRisk(s), of: s.years_simulated || 10 })
  const line3 = rev
    ? [...(okZl(rev.weak_year_zl) ? [t('słaby rok: ok. {zl}', { zl: formatZl(rev.weak_year_zl) })] : []), risk]
    : [
        ...(priceNow ? [`${priceNowSource(priceNow, t)}: ${formatNum(priceNow.zl_t, 0)} zł/t`] : [t(note?.trim() || 'brak ceny skupu')]),
        risk,
      ]
  return (
    <span className="flex min-w-0 flex-1 gap-2.5">
      <Icon className="mt-0.5 size-5 shrink-0" style={{ color: c.color }} aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-3">
          <span className="min-w-0 text-base leading-6 font-semibold">
            <span className="sr-only">{t(c.label)}: </span>
            {t(s.label)}
          </span>
          <span className={rev ? 'tabular shrink-0 text-base font-semibold whitespace-nowrap' : 'shrink-0 text-sm whitespace-nowrap text-text-muted'}>
            {rev ? fmtRevenue(rev, t) : t('brak ceny')}
          </span>
        </span>
        <Parts parts={line2} className="block text-sm leading-5 text-text-muted" />
        <Parts parts={line3} className="block text-xs leading-4 text-text-muted" />
      </span>
    </span>
  )
}
