import { ChevronDown, CloudOff } from 'lucide-react'
import { useState } from 'react'
import type { AnalysisResponse } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, formatSigned } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'
import { BalanceChart } from './charts/BalanceChart'
import { PrecipChart } from './charts/PrecipChart'
import { SeasonBars } from './charts/SeasonBars'
import { StressChart } from './charts/StressChart'
import { PassportSection } from './PassportSection'

/** Ostatnia wartość serii, która nie jest pusta. */
function lastValue<T>(arr: T[], get: (x: T) => number | null | undefined): number | null {
  for (let i = arr.length - 1; i >= 0; i--) {
    const v = get(arr[i])
    if (v != null) return v
  }
  return null
}

/**
 * Na tle 10 lat (SPEC 7.B, uwagi z testów): jedno duże zdanie na górze (suchszy / wilgotniejszy / podobny,
 * z rankingu lat), prosty wykres słupkowy „Ten rok” vs „Średnio” z najsuchszym i najmokrzejszym rokiem
 * (na ten sam dzień sezonu), ta sama liczba co w dolnej karcie (`balance_deviation_mm`), „dane pogodowe do …”.
 * Szczegóły (liczby, linia sezonu, opady, dni stresu) – pod „Pokaż szczegóły”.
 * 10 słupków (po roku) – gdy kontrakt dostanie bilans każdego roku (prośba do A).
 */
export function SectionB({ analysis, chartWidth }: { analysis: AnalysisResponse; chartWidth?: number }) {
  const { t } = useLang()
  const [open, setOpen] = useState(!!chartWidth)
  const h = analysis.history
  const dev = h.balance_deviation_mm
  const rank = h.balance_rank
  const untilFromSeries = h.balance_cumulative.length ? h.balance_cumulative[h.balance_cumulative.length - 1].date : h.period_end
  const now = lastValue(h.balance_cumulative, (p) => p.value)
  const mean = lastValue(h.balance_band, (b) => b.mean)
  const min = lastValue(h.balance_band, (b) => b.min)
  const max = lastValue(h.balance_band, (b) => b.max)

  // jedno zdanie: ile lat było suchszych niż teraz
  let sentence: string
  if (rank && rank.of_years > 0) {
    const drier = rank.lower_years
    const wetter = rank.of_years - rank.lower_years
    sentence =
      drier <= Math.floor(rank.of_years * 0.3)
        ? t('Ten rok jest suchszy niż zwykle – suszej było tylko w {n} z ostatnich {of} lat.', { n: drier, of: rank.of_years })
        : wetter <= Math.floor(rank.of_years * 0.3)
          ? t('Ten rok jest wilgotniejszy niż zwykle – mokrzej było tylko w {n} z ostatnich {of} lat.', { n: wetter, of: rank.of_years })
          : t('Ten rok jest podobny do zwykłego – suszej było w {n} z ostatnich {of} lat.', { n: drier, of: rank.of_years })
  } else sentence = t('Brak porównania z poprzednimi latami dla tej działki.')
  // A5e: backend daje proste zdanie i słupki z każdego roku
  const yearsBars = analysis.seasonal_balance_by_year ?? []
  if (yearsBars.length && h.summary) sentence = t(h.summary)
  const until = analysis.weather_data_until ?? untilFromSeries

  // słupki: ten rok, średnio, najsuchszy i najmokrzejszy rok (ten sam dzień sezonu)
  const bars = [
    { key: 'now', label: t('Ten rok'), value: now, cls: 'bg-water' },
    { key: 'mean', label: t('Średnio (10 lat)'), value: mean, cls: 'bg-sage' },
    { key: 'min', label: t('Najsuchszy rok'), value: min, cls: 'bg-danger/70' },
    { key: 'max', label: t('Najmokrzejszy rok'), value: max, cls: 'bg-brand/60' },
  ].filter((b) => b.value != null) as { key: string; label: string; value: number; cls: string }[]
  const span = Math.max(1, ...bars.map((b) => Math.abs(b.value)))

  return (
    <PassportSection id="pass-b" letter="B" title={t('Na tle 10 lat')}>
      <p className="font-display text-2xl leading-8 font-semibold text-brand-dark">{sentence}</p>

      <div className="space-y-3 rounded-xl bg-surface p-4 shadow-card">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h4 className="text-base leading-6 font-semibold">{t('Ile wody zostało: spadło minus wyparowało')}</h4>
          <span className="text-sm text-text-muted">
            {t('od {a} · dane pogodowe do {b}', { a: formatDatePl(h.season_start), b: formatDatePl(until) })}
          </span>
        </div>
        {dev != null && (
          <p className="text-base leading-6">
            <b className={cn('tabular text-xl', dev < 0 ? 'text-danger' : 'text-water')}>{formatSigned(dev, 0)} mm</b>{' '}
            <span className="text-text-muted">{t('względem średniej z 10 lat')}</span>
          </p>
        )}
        {yearsBars.length > 0 ? (
          <>
            <SeasonBars years={yearsBars} mean={analysis.seasonal_balance_mean_mm} width={chartWidth} />
            <p className="text-xs leading-4 text-text-muted">
              {t('Ile wody zostało {okres} w każdym roku (spadło minus wyparowało, mm). * – ten rok.', {
                okres: analysis.seasonal_balance_label ? t(analysis.seasonal_balance_label) : t('od początku sezonu'),
              })}
            </p>
          </>
        ) : (
        <>
        {/* poziome słupki od zera: na lewo = więcej wyparowało, na prawo = więcej spadło */}
        <ul className="space-y-2" aria-label={t('Porównanie z poprzednimi latami')}>
          {bars.map((b) => {
            const w = (Math.abs(b.value) / span) * 50
            return (
              <li key={b.key} className="grid grid-cols-[8.5rem_1fr_4.5rem] items-center gap-2 text-sm">
                <span className={cn('truncate', b.key === 'now' && 'font-semibold')}>{b.label}</span>
                <span className="relative h-5 rounded bg-surface-2/70">
                  <span className="absolute inset-y-0 left-1/2 w-px bg-text-muted/40" aria-hidden />
                  <span
                    className={cn('absolute inset-y-0.5 rounded', b.cls)}
                    style={b.value < 0 ? { right: '50%', width: `${w}%` } : { left: '50%', width: `${w}%` }}
                    aria-hidden
                  />
                </span>
                <span className={cn('tabular text-right', b.key === 'now' && 'font-semibold')}>{formatSigned(b.value, 0)} mm</span>
              </li>
            )
          })}
        </ul>
        <p className="text-xs leading-4 text-text-muted">{t('Na lewo od kreski – więcej wody wyparowało, niż spadło. 1 mm = 1 litr na m².')}</p>
        </>
        )}
        {analysis.precip_sources?.sentence && <p className="text-xs leading-4 text-text-muted">{t(analysis.precip_sources.sentence)}</p>}
      </div>

      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-brand hover:underline"
      >
        {t(open ? 'Ukryj szczegóły' : 'Pokaż szczegóły')} <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
      </button>

      {open && (
        <div className="space-y-3">
          {(yearsBars.length ? h.details : h.summary) && <p className="text-sm leading-5 text-text-muted">{t((yearsBars.length ? h.details : h.summary) ?? '')}</p>}
          {h.longest_dry_spell && (
            <p className="flex items-center gap-1.5 text-sm">
              <CloudOff className="size-4 text-amber" aria-hidden />
              {h.longest_dry_spell.end_date
                ? t('Najdłużej bez deszczu: {n} dni (do {d})', { n: h.longest_dry_spell.days, d: formatDatePl(h.longest_dry_spell.end_date) })
                : t('Najdłużej bez deszczu: {n} dni', { n: h.longest_dry_spell.days })}
            </p>
          )}
          <div className="space-y-2 rounded-xl bg-surface p-4 shadow-card">
            <h4 className="text-base leading-6 font-semibold">{t('Woda od początku sezonu, dzień po dniu')}</h4>
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
        </div>
      )}

      <SourceTag
        kind={h.source_tag.kind}
        date={h.source_tag.date ? formatDatePl(h.source_tag.date) : undefined}
        title={h.source_tag.source ?? undefined}
      />
    </PassportSection>
  )
}
