import { CalendarRange } from 'lucide-react'
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PeriodSummary } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { balanceText, formatDatePl, formatNum } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * F10 (A17, backend dopiero dodaje – pola opcjonalne, typ lokalny): dane pogodowe kończą się przed wybranym końcem.
 * `requested_to` – koniec wybrany przez rolnika, `data_until` – ostatni dzień z danymi, `note` – zdanie dla rolnika.
 */
type PeriodDataExtras = { data_until?: string | null; requested_to?: string | null; filled_days?: number | null; note?: string | null; data_note?: string | null }

/**
 * Karta „Okres” (F3): jedno zdanie dużą czcionką (z serwera), sumy – opad / parowanie / bilans wody vs zwykle –
 * i mały wykres dzień po dniu (słupki deszczu, linia „bilans wody” narastająco). `requested` bez `period`
 * w odpowiedzi – informacja o braku podsumowania, nigdy błąd.
 */
export function PeriodCard({ period: p, requested, passport, chartWidth }: { period?: PeriodSummary | null; requested?: boolean; passport?: boolean; chartWidth?: number }) {
  const { t } = useLang()
  if (!p) {
    if (!requested) return null
    return (
      <section aria-label={t('Okres')} className="rounded-xl border bg-surface p-3.5">
        <p className="flex items-center gap-2 text-sm font-medium">
          <CalendarRange className="size-4 text-brand" aria-hidden /> {t('Okres')}
        </p>
        <p className="mt-1 text-sm leading-5 text-text-muted">{t('Brak podsumowania okresu dla tej daty – reszta wyniku jest pełna.')}</p>
      </section>
    )
  }
  const day = (iso: string) => {
    const [, m, d] = iso.split('-')
    return `${Number(d)}.${m}`
  }
  const chart = (
    <ComposedChart data={p.daily} width={chartWidth} height={passport ? 170 : 110} margin={{ top: 6, right: 4, bottom: 0, left: -22 }}>
      <CartesianGrid stroke="var(--color-line)" vertical={false} />
      <XAxis dataKey="date" tickFormatter={day} tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={{ stroke: 'var(--color-line)' }} minTickGap={24} />
      <YAxis width={44} tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={false} unit=" mm" />
      <ReferenceLine y={0} stroke="var(--color-text-muted)" strokeOpacity={0.4} />
      <Tooltip
        labelFormatter={(d) => formatDatePl(String(d))}
        formatter={(v, name) => [`${formatNum(Number(v), 1)} mm`, name]}
        contentStyle={{ borderRadius: 12, border: '1px solid var(--color-line)', fontSize: 13 }}
      />
      <Bar dataKey="precip_mm" name={t('deszcz w dniu')} fill="var(--color-water)" opacity={0.55} radius={[3, 3, 0, 0]} isAnimationActive={false} />
      <Line dataKey="balance_cum_mm" name={t('bilans wody od początku okresu')} stroke="var(--color-brand)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
    </ComposedChart>
  )
  const diff = p.balance_mm - p.normal_balance_mm
  // F10: dane kończą się przed wybranym końcem – nagłówek = zakres rolnika, pod nim szara nota z API
  const x = p as PeriodSummary & PeriodDataExtras
  const wantedTo = x.requested_to ?? p.to
  const cut = !!x.data_until && x.data_until < wantedTo
  const heading = cut ? `${formatDatePl(p.from)}–${formatDatePl(wantedTo)}` : t(p.label)
  const cutNote = cut
    ? (x.note ?? x.data_note)?.trim() ||
      t('Dane pogodowe są dostępne do {d} – ostatnie dni nie są jeszcze opublikowane.', { d: formatDatePl(x.data_until!) })
    : null
  return (
    <section aria-label={t('Okres')} className={cn('tabular space-y-3 rounded-xl bg-surface', passport ? 'p-4 shadow-card' : 'border p-3.5')}>
      <div className="flex items-center gap-2">
        <CalendarRange className="size-5 shrink-0 text-brand" aria-hidden />
        <h4 className="min-w-0 flex-1 text-sm leading-5 font-semibold text-text-muted">{heading}</h4>
      </div>
      {cutNote && <p className="-mt-2 text-sm leading-5 text-text-muted">{t(cutNote)}</p>}
      <p className={cn('font-display font-semibold text-brand-dark', passport ? 'text-xl leading-7' : 'text-lg leading-6')}>{t(p.sentence)}</p>
      <dl className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-water-soft/70 px-1 py-2">
          <dt className="text-xs leading-4 text-text-muted">{t('Opad')}</dt>
          <dd className="tabular text-lg leading-6 font-semibold">{formatNum(p.precip_mm, 0)} mm</dd>
        </div>
        <div className="rounded-lg bg-warn-soft/70 px-1 py-2">
          <dt className="text-xs leading-4 text-text-muted">{t('Parowanie')}</dt>
          <dd className="tabular text-lg leading-6 font-semibold">{formatNum(p.et0_mm, 0)} mm</dd>
        </div>
        <div className="rounded-lg bg-surface-2 px-1 py-2">
          <dt className="text-xs leading-4 text-text-muted">{t('Bilans wody')}</dt>
          <dd className={cn('tabular text-lg leading-6 font-semibold', p.balance_mm < 0 && 'text-danger')}>{t(...balanceText(p.balance_mm))}</dd>
        </div>
      </dl>
      <p className="text-sm leading-5">
        {t('Zwykle w tym okresie bilans wody: {n}', { n: t(...balanceText(p.normal_balance_mm)) })}
        {Math.round(diff) !== 0 && (
          <span className={cn('font-semibold', diff < 0 ? 'text-danger' : 'text-water')}>
            {' '}
            · {t(diff < 0 ? '{n} mm mniej niż zwykle' : '{n} mm więcej niż zwykle', { n: formatNum(Math.abs(diff), 0) })}
          </span>
        )}
        {p.stress_days != null && <span className="text-text-muted"> · {t('dni stresu wodnego: {n}', { n: p.stress_days })}</span>}
      </p>
      {p.daily.length > 1 && (
        <figure className="space-y-1">
          {chartWidth ? chart : <ResponsiveContainer width="100%" height={passport ? 170 : 110}>{chart}</ResponsiveContainer>}
          <figcaption className="text-xs leading-4 text-text-muted">{t('Słupki – deszcz w danym dniu; linia – bilans wody od początku okresu (opad minus parowanie).')}</figcaption>
        </figure>
      )}
      <SourceTag kind="obliczenia" title={t('Opad (IMGW / NASA) minus parowanie (FAO-56) – dzień po dniu')} />
    </section>
  )
}
