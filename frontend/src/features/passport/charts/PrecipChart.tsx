import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { MonthlyPrecip } from '@/api/types'
import { formatNum } from '@/lib/format'
import { locale, useLang } from '@/lib/i18n'

/** Opady miesięczne: ten rok vs średnia z 10 lat (SPEC 7.B). */
export function PrecipChart({ months, width }: { months: MonthlyPrecip[]; width?: number }) {
  const { t } = useLang()
  if (!months.length) return <p className="text-sm text-text-muted">{t('Brak danych do wykresu')}</p>
  const monthName = (m: number) => new Date(2020, m - 1, 15).toLocaleDateString(locale(), { month: 'short' })
  const chart = (
    <BarChart data={months} width={width} height={180} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={2}>
      <CartesianGrid stroke="var(--color-line)" vertical={false} />
      <XAxis
        dataKey="month"
        tickFormatter={monthName}
        tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
        tickLine={false}
        axisLine={{ stroke: 'var(--color-line)' }}
      />
      <YAxis unit=" mm" width={56} tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={false} />
      <Tooltip
        labelFormatter={(m) => monthName(Number(m))}
        formatter={(v, name) => [v == null ? t('brak danych') : `${formatNum(Number(v), 0)} mm`, name]}
        contentStyle={{ borderRadius: 12, border: '1px solid var(--color-line)', fontSize: 13 }}
        cursor={{ fill: 'var(--color-surface-2)' }}
      />
      <Bar dataKey="current_mm" name={t('Ten rok')} fill="var(--color-water)" radius={[6, 6, 0, 0]} isAnimationActive={false} />
      <Bar dataKey="mean_mm" name={t('Średnio')} fill="var(--color-sage)" radius={[6, 6, 0, 0]} isAnimationActive={false} />
    </BarChart>
  )
  return (
    <figure className="space-y-2">
      {width ? chart : <ResponsiveContainer width="100%" height={180}>{chart}</ResponsiveContainer>}
      <figcaption className="flex gap-4 text-xs leading-4 text-text-muted">
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-water" aria-hidden /> {t('Ten rok')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-sage" aria-hidden /> {t('Średnio z 10 lat')}
        </span>
      </figcaption>
    </figure>
  )
}
