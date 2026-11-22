import { ChevronDown, CloudOff } from 'lucide-react'
import { useState } from 'react'
import type { AnalysisResponse, CauseFactor } from '@/api/types'
import { PrecipSourceNote } from '@/features/parcel-panel/PrecipSourceNote'
import { PeriodCard } from '@/features/period/PeriodCard'
import { SourceTag } from '@/components/SourceTag'
import { balanceText, formatDatePl, formatDayLong, formatShare, formatSigned } from '@/lib/format'
import { seasonBalance } from '@/lib/seasonBalance'
import { useLang } from '@/lib/i18n'
import { useSettings } from '@/lib/storage'
import { cn } from '@/lib/utils'
import { BalanceChart } from './charts/BalanceChart'
import { PrecipChart } from './charts/PrecipChart'
import { SeasonBars } from './charts/SeasonBars'
import { StressChart } from './charts/StressChart'
import { PassportCard } from './PassportCard'
import { PassportSection } from './PassportSection'

/** Kolor paska przyczyny (paleta paszportu). */
const CAUSE_BAR: Record<CauseFactor, string> = {
  opady: 'bg-pp-water',
  parowanie: 'bg-pp-warn',
  gleba: 'bg-pp-earth',
  teren: 'bg-paper-line',
  uprawa: 'bg-pp-ok',
  inne: 'bg-paper-line',
}

/** Zdanie-wniosek z rankingu lat (A5e: backend daje gotowe `history.summary` przy słupkach z każdego roku). */
function useConclusion(a: AnalysisResponse): string {
  const { t } = useLang()
  const h = a.history
  if ((a.seasonal_balance_by_year?.length ?? 0) > 0 && h.summary) return t(h.summary)
  const rank = h.balance_rank
  if (!rank || rank.of_years <= 0) return t('Brak porównania z poprzednimi latami dla tej działki.')
  const drier = rank.lower_years
  const wetter = rank.of_years - rank.lower_years
  if (drier <= Math.floor(rank.of_years * 0.3)) return t('Ten sezon jest suchszy niż zwykle – mniej wody było w {n} z {of} lat.', { n: drier, of: rank.of_years })
  if (wetter <= Math.floor(rank.of_years * 0.3)) return t('Ten sezon jest wilgotniejszy niż zwykle – więcej wody było w {n} z {of} lat.', { n: wetter, of: rank.of_years })
  return t('Ten sezon jest podobny do zwykłego – mniej wody było w {n} z {of} lat.', { n: drier, of: rank.of_years })
}

/**
 * 4. Woda na tle 10 lat (F6): zdanie-wniosek, wybrany okres (karta „Okres”), wykres słupkowy bilansu na rok
 * (w dół od zera, przerywana średnia, bieżący rok w kolorze ryzyka i pogrubiony, wartości pod słupkami).
 * Obok: „Dlaczego?” – poziome paski przyczyn z % i zdaniem (teren – informacyjnie, bez %) i „Źródła opadów”
 * (stacja + odległość, zdanie z API; porównanie z NASA rozwijane). Tryb Doradca – „Szczegóły” z dotychczasowymi
 * wykresami (bilans dzień po dniu, dni stresu, opady miesięczne).
 */
export function WaterHistorySection({ analysis, chartWidth }: { analysis: AnalysisResponse; chartWidth?: number }) {
  const { t } = useLang()
  const [settings] = useSettings()
  const [open, setOpen] = useState(!!chartWidth)
  const [precipOpen, setPrecipOpen] = useState(false)
  const h = analysis.history
  const conclusion = useConclusion(analysis)
  const season = seasonBalance(analysis)
  const years = analysis.seasonal_balance_by_year ?? []
  const until = analysis.weather_data_until ?? (h.balance_cumulative.length ? h.balance_cumulative[h.balance_cumulative.length - 1].date : h.period_end)
  const causes = [...analysis.causes].sort((a, b) => b.share - a.share)
  const advisor = settings.mode === 'doradca'

  return (
    <PassportSection id="pp-woda" title={t('Woda na tle 10 lat')}>
      <p className="font-display text-xl leading-7 font-bold md:text-2xl md:leading-8">{conclusion}</p>
      {analysis.period && <PeriodCard period={analysis.period} passport chartWidth={chartWidth} />}
      <div className="grid gap-4 lg:grid-cols-3">
        <PassportCard
          className="lg:col-span-2"
          title={t('Bilans wody w każdym roku')}
          aside={
            <span className="text-sm text-text-muted">
              {t('{okres} · dane pogodowe do {d}', {
                okres: analysis.seasonal_balance_label ? t(analysis.seasonal_balance_label) : t('od {d}', { d: formatDayLong(season.from) }),
                d: formatDatePl(until),
              })}
            </span>
          }
        >
          {season.mm != null && (
            <p className="mb-2 text-base leading-6">
              {t('W tym sezonie:')} <b className={cn('tabular', season.mm < 0 ? 'text-pp-bad' : 'text-pp-water')}>{t(...balanceText(season.mm))}</b>
              {h.balance_deviation_mm != null && Math.round(h.balance_deviation_mm) !== 0 && (
                <span className="text-text-muted"> · {t('{n} mm względem średniej z 10 lat', { n: formatSigned(h.balance_deviation_mm, 0) })}</span>
              )}
            </p>
          )}
          {years.length > 0 ? (
            <>
              <SeasonBars years={years} mean={analysis.seasonal_balance_mean_mm} width={chartWidth} />
              <p className="mt-1 text-xs leading-4 text-text-muted">{t('Opad minus parowanie, mm. Przerywana linia – średnia. Pogrubiony – ten sezon. 1 mm = 1 litr na m².')}</p>
            </>
          ) : (
            <p className="text-sm text-text-muted">{t('Brak porównania z poprzednimi latami dla tej działki.')}</p>
          )}
          {h.longest_dry_spell && (
            <p className="mt-3 flex items-center gap-1.5 text-sm">
              <CloudOff className="size-4 text-pp-warn" aria-hidden />
              {h.longest_dry_spell.end_date
                ? t('Najdłużej bez deszczu: {n} dni (do {d})', { n: h.longest_dry_spell.days, d: formatDatePl(h.longest_dry_spell.end_date) })
                : t('Najdłużej bez deszczu: {n} dni', { n: h.longest_dry_spell.days })}
            </p>
          )}
          <SourceTag kind={h.source_tag.kind} date={h.source_tag.date ? formatDatePl(h.source_tag.date) : undefined} title={h.source_tag.source ?? undefined} className="mt-3" />
        </PassportCard>

        <div className="grid content-start gap-4">
          <PassportCard title={t('Dlaczego?')}>
            {causes.length === 0 ? (
              <p className="text-sm text-text-muted">{t('Brakuje danych pogodowych albo o glebie')}</p>
            ) : (
              <ul className="space-y-3">
                {causes.map((c) => {
                  const info = c.factor === 'teren'
                  return (
                    <li key={c.factor + c.title} className="space-y-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-sm leading-5 font-semibold">{t(c.title)}</span>
                        <span className="tabular shrink-0 text-sm font-semibold text-text-muted">{info ? t('informacyjnie') : formatShare(c.share)}</span>
                      </div>
                      {!info && (
                        <div className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                          <div className={cn('h-full rounded-full', CAUSE_BAR[c.factor] ?? 'bg-paper-line')} style={{ width: `${Math.max(0, Math.min(1, c.share)) * 100}%` }} />
                        </div>
                      )}
                      <p className="text-sm leading-5 text-text-muted">{t(c.description)}</p>
                    </li>
                  )
                })}
              </ul>
            )}
            {causes.length > 0 && <p className="mt-3 text-xs leading-4 text-text-muted">{t('Procent = waga przyczyny w opisie.')}</p>}
          </PassportCard>

          {analysis.precip_sources && (
            <PassportCard title={t('Źródła opadów')}>
              <PrecipSourceNote sources={analysis.precip_sources} compact />
              <button
                type="button"
                aria-expanded={precipOpen}
                onClick={() => setPrecipOpen((o) => !o)}
                className="mt-2 inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-pp-brand"
              >
                {t('Porównanie z danymi NASA')} <ChevronDown className={cn('size-4 transition-transform', precipOpen && 'rotate-180')} aria-hidden />
              </button>
              {precipOpen && <PrecipSourceNote sources={analysis.precip_sources} className="mt-2" />}
            </PassportCard>
          )}
        </div>
      </div>

      {(advisor || chartWidth) && (
        <div>
          {!chartWidth && (
            <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-pp-brand">
              {t('Szczegóły')} <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
            </button>
          )}
          {open && (
            <div className="mt-2 space-y-4">
              {(years.length ? h.details : h.summary) && <p className="text-sm leading-5 text-text-muted">{t((years.length ? h.details : h.summary) ?? '')}</p>}
              <PassportCard title={t('Bilans wody od początku sezonu, dzień po dniu')}>
                <BalanceChart history={h} width={chartWidth} />
              </PassportCard>
              <div className="grid gap-4 lg:grid-cols-2">
                <PassportCard title={t('Dni, w których roślinom brakowało wody')}>
                  <StressChart years={h.stress_days_by_year} width={chartWidth ? chartWidth / 2 - 24 : undefined} />
                </PassportCard>
                <PassportCard title={t('Deszcz w kolejnych miesiącach')}>
                  <PrecipChart months={h.monthly_precip} width={chartWidth ? chartWidth / 2 - 24 : undefined} />
                </PassportCard>
              </div>
            </div>
          )}
        </div>
      )}
    </PassportSection>
  )
}
