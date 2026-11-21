import { CalendarRange, ChevronLeft, ChevronRight } from 'lucide-react'
import type { AnalysisResponse, YearStress } from '@/api/types'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { isoDate, minAnalysisIso, todayIso } from '@/lib/dates'
import { formatDatePl } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** Kolor roku: dni stresu względem średniej z widocznych lat (mniej = dobrze, dużo więcej = susza). */
function yearTone(y: YearStress, mean: number | null): string {
  if (y.stress_days == null || mean == null) return 'hatch-nodata'
  if (mean === 0) return y.stress_days === 0 ? 'bg-ok' : 'bg-risk'
  const r = y.stress_days / mean
  return r <= 0.75 ? 'bg-ok' : r <= 1.25 ? 'bg-warn' : r <= 2 ? 'bg-risk' : 'bg-danger'
}

/** Ta sama data w innym roku albo przesunięta o miesiące – w zakresie dziś − 10 lat … dziś. */
function shift(iso: string, { years = 0, months = 0 }: { years?: number; months?: number }) {
  const d = new Date(`${iso}T12:00:00`)
  d.setFullYear(d.getFullYear() + years, d.getMonth() + months)
  const out = isoDate(d)
  return out < minAnalysisIso() ? minAnalysisIso() : out > todayIso() ? todayIso() : out
}

/**
 * Oś czasu (SPEC 4.5, 9): ostatnie lata z kolorem stanu (dni stresu wodnego względem średniej),
 * wybrany rok wyróżniony, ◀ ▶ = miesiąc wstecz / naprzód, klik w rok = ta sama data w tamtym roku.
 */
export function TimelineCard({
  updated,
  analysis,
  asOf,
  onAsOfChange,
}: {
  updated: string | null
  analysis: AnalysisResponse | null
  asOf: string
  onAsOfChange: (iso: string) => void
}) {
  const { t } = useLang()
  const years = analysis ? [...analysis.history.stress_days_by_year].sort((a, b) => a.year - b.year) : []
  const known = years.filter((y) => y.stress_days != null)
  const mean = known.length ? known.reduce((s, y) => s + (y.stress_days ?? 0), 0) / known.length : null
  const curYear = Number(asOf.slice(0, 4))
  const canBack = asOf > minAnalysisIso()
  const canFwd = asOf < todayIso()

  return (
    <Card icon={CalendarRange} title="Oś czasu">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onAsOfChange(shift(asOf, { months: -1 }))}
          disabled={!canBack}
          aria-label={t('Miesiąc wstecz')}
          className="flex size-8 shrink-0 items-center justify-center rounded-full hover:bg-surface-2 disabled:opacity-40"
        >
          <ChevronLeft className="size-4" />
        </button>
        <span className="tabular min-w-0 flex-1 text-center text-sm font-semibold">{formatDatePl(asOf)}</span>
        <button
          type="button"
          onClick={() => onAsOfChange(shift(asOf, { months: 1 }))}
          disabled={!canFwd}
          aria-label={t('Miesiąc naprzód')}
          className="flex size-8 shrink-0 items-center justify-center rounded-full hover:bg-surface-2 disabled:opacity-40"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>

      {years.length ? (
        <ol className="mt-1 flex gap-0.5" aria-label={t('Lata – dni stresu wodnego względem średniej')}>
          {years.map((y) => (
            <li key={y.year} className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => onAsOfChange(shift(asOf, { years: y.year - curYear }))}
                title={y.stress_days == null ? `${y.year}: ${t('brak danych')}` : `${y.year}: ${t('{n} dni stresu', { n: y.stress_days })}`}
                className="group flex w-full flex-col items-center gap-0.5"
              >
                <span className={cn('h-5 w-full rounded-sm', yearTone(y, mean), y.year === curYear && 'ring-2 ring-brand ring-offset-1')} />
                <span className={cn('text-[11px] leading-3 text-text-muted', y.year === curYear && 'font-bold text-brand')}>
                  {String(y.year).slice(2)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="hatch-nodata mt-1 rounded-md px-2 py-1.5 text-sm leading-5 text-text-muted">{t('Lata pojawią się po analizie działki')}</p>
      )}
      <p className="mt-auto text-xs leading-4 text-text-muted">
        {t('Ostatnia aktualizacja danych:')} {updated ?? '—'}
      </p>
    </Card>
  )
}
