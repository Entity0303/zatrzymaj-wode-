import { CloudOff, TrendingDown, TrendingUp, Trophy } from 'lucide-react'
import type { AnalysisResponse } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { BalanceChart } from './charts/BalanceChart'
import { PrecipChart } from './charts/PrecipChart'
import { StressChart } from './charts/StressChart'
import { PassportSection } from './PassportSection'

/**
 * B. Na tle 10 lat (SPEC 7.B): bilans wody narastająco na tle pasma i średniej, dni stresu w latach,
 * opady miesięczne, zdanie podsumowania. `chartWidth` – stała szerokość wykresów (wydruk).
 */
export function SectionB({ analysis, chartWidth }: { analysis: AnalysisResponse; chartWidth?: number }) {
  const { t } = useLang()
  const h = analysis.history
  const dev = h.balance_deviation_mm
  return (
    <PassportSection id="pass-b" letter="B" title={t('Na tle 10 lat')}>
      {h.summary && <p className="text-base leading-6">{t(h.summary)}</p>}

      <ul className="flex flex-wrap gap-2">
        {dev != null && (
          <li className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${dev < 0 ? 'bg-danger-soft text-danger' : 'bg-water-soft text-water'}`}>
            {dev < 0 ? <TrendingDown className="size-4" aria-hidden /> : <TrendingUp className="size-4" aria-hidden />}
            {t('{mm} mm względem średniej', { mm: formatSigned(dev, 0) })}
          </li>
        )}
        {h.balance_rank && (
          <li className="flex items-center gap-1.5 rounded-full bg-surface-2 px-3 py-1 text-sm font-medium">
            <Trophy className="size-4 text-amber" aria-hidden />
            {t('Bilans niższy niż teraz: {n} z {of} lat', { n: h.balance_rank.lower_years, of: h.balance_rank.of_years })}
          </li>
        )}
        {h.longest_dry_spell && (
          <li className="flex items-center gap-1.5 rounded-full bg-amber-soft px-3 py-1 text-sm font-medium">
            <CloudOff className="size-4 text-amber" aria-hidden />
            {h.longest_dry_spell.end_date
              ? t('Najdłużej bez deszczu: {n} dni (do {d})', { n: h.longest_dry_spell.days, d: formatDatePl(h.longest_dry_spell.end_date) })
              : t('Najdłużej bez deszczu: {n} dni', { n: h.longest_dry_spell.days })}
          </li>
        )}
      </ul>

      <div className="space-y-2 rounded-xl bg-surface p-4 shadow-card">
        <h4 className="text-base leading-6 font-semibold">{t('Woda od początku sezonu (opad minus parowanie)')}</h4>
        <p className="text-sm leading-5 text-text-muted">{t('Poniżej zera = więcej wody wyparowało, niż spadło. 1 mm = 1 litr na m².')}</p>
        <BalanceChart history={h} width={chartWidth} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="min-w-0 space-y-2 rounded-xl bg-surface p-4 shadow-card">
          <h4 className="text-base leading-6 font-semibold">{t('Dni, w których roślinom brakowało wody')}</h4>
          <StressChart years={h.stress_days_by_year} width={chartWidth ? chartWidth / 2 - 24 : undefined} />
        </div>
        <div className="min-w-0 space-y-2 rounded-xl bg-surface p-4 shadow-card">
          <h4 className="text-base leading-6 font-semibold">{t('Deszcz w kolejnych miesiącach')}</h4>
          <PrecipChart months={h.monthly_precip} width={chartWidth ? chartWidth / 2 - 24 : undefined} />
        </div>
      </div>

      <SourceTag
        kind={h.source_tag.kind}
        date={h.source_tag.date ? formatDatePl(h.source_tag.date) : undefined}
        title={h.source_tag.source ?? undefined}
      />
    </PassportSection>
  )
}
