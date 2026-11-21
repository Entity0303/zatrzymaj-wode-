import { ShowerHead } from 'lucide-react'
import type { IrrigationPlan, IrrigationStatus } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, formatDayMonth, formatNum } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** 1 dawka · 2–4 dawki · 5+ dawek */
const doses = (n: number) => (n === 1 ? '{n} dawka,' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? '{n} dawki,' : '{n} dawek,')

const STATUS: Record<IrrigationStatus, { label: string; cls: string }> = {
  zalecane: { label: 'Zalecane', cls: 'bg-water-soft text-[#1d5d96]' },
  niepotrzebne: { label: 'Niepotrzebne', cls: 'bg-ok-soft text-brand' },
  nieuzasadnione_w_fazie: { label: 'Nie w tej fazie', cls: 'bg-surface-2 text-text-muted' },
  nie_praktykowane: { label: 'Nie stosuje się', cls: 'bg-surface-2 text-text-muted' },
  brak_danych: { label: 'Brak danych', cls: 'border border-nodata/60 bg-nodata-soft text-text-muted' },
}

/**
 * Plan nawadniania (kontrakt `irrigation`, D33): dawka jednorazowa zależna od gleby, termin,
 * co ile dni powtarzać, suma na 7 dni. Zawsze na końcu „Co zrobić?” – po retencji i agrotechnice.
 */
export function IrrigationCard({ plan }: { plan: IrrigationPlan }) {
  const { t } = useLang()
  const s = STATUS[plan.status]
  const showPlan = plan.status === 'zalecane' && plan.dose_mm != null
  return (
    <section
      aria-label={t('Plan nawadniania')}
      className={cn('rounded-xl border bg-surface p-3.5', plan.status === 'brak_danych' && 'hatch-nodata')}
    >
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-earth">
          <ShowerHead className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="text-base leading-6 font-semibold">{t('Plan nawadniania')}</p>
            <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs leading-4 font-medium', s.cls)}>{t(s.label)}</span>
          </div>
          <p className="text-sm leading-5 text-text-muted">{t(plan.message)}</p>
        </div>
      </div>

      {showPlan && (
        <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-lg bg-water-soft/60 px-1 py-2">
            <dt className="text-xs leading-4 text-text-muted">{t('Ile wody')}</dt>
            <dd className="tabular text-lg leading-6 font-semibold">
              {formatNum(plan.dose_mm!, plan.dose_mm! % 1 ? 1 : 0)} <span className="text-sm font-medium text-text-muted">mm</span>
            </dd>
          </div>
          <div className="rounded-lg bg-water-soft/60 px-1 py-2">
            <dt className="text-xs leading-4 text-text-muted">{t('Kiedy')}</dt>
            <dd className="tabular text-lg leading-6 font-semibold" title={plan.first_date ? formatDatePl(plan.first_date) : undefined}>
              {plan.first_date ? formatDayMonth(plan.first_date) : '—'}
            </dd>
          </div>
          <div className="rounded-lg bg-water-soft/60 px-1 py-2">
            <dt className="text-xs leading-4 text-text-muted">{t('Powtarzaj')}</dt>
            <dd className="tabular text-lg leading-6 font-semibold">
              {plan.interval_days != null ? t('co {n} dni', { n: plan.interval_days }) : '—'}
            </dd>
          </div>
        </dl>
      )}
      {showPlan && plan.total_7d_mm != null && (
        <p className="mt-2 text-sm leading-5 text-text-muted">
          {t('W 7 dniach: {doses} ok. {mm} mm', {
            doses: plan.doses_7d != null ? t(doses(plan.doses_7d), { n: plan.doses_7d }) : '',
            mm: formatNum(plan.total_7d_mm, 0),
          })}
        </p>
      )}

      <div className="mt-2.5">
        <SourceTag
          kind={plan.source_tag.kind}
          date={plan.source_tag.date ? formatDatePl(plan.source_tag.date) : undefined}
          title={plan.source_tag.source ?? undefined}
        />
      </div>
    </section>
  )
}
