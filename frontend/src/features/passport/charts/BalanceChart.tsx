import { useMemo } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { History } from '@/api/types'
import { formatDayMonth, formatNum, formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'

type Row = { date: string; value: number | null; band: [number, number] | null; mean: number | null }

/**
 * Bilans wody narastająco od początku sezonu (SPEC 7.B, TrendChart): linia tego roku
 * na tle pasma min–max i średniej z 10 lat. `width` – stała szerokość (wydruk), inaczej dopasowanie.
 */
export function BalanceChart({ history, width }: { history: History; width?: number }) {
  const { t } = useLang()
  const data = useMemo<Row[]>(() => {
    const band = new Map(history.balance_band.map((b) => [b.date, b]))
    const dates = Array.from(new Set([...history.balance_band.map((b) => b.date), ...history.balance_cumulative.map((p) => p.date)])).sort()
    const cur = new Map(history.balance_cumulative.map((p) => [p.date, p.value]))
    return dates.map((date) => {
      const b = band.get(date)
      return {
        date,
        value: cur.get(date) ?? null,
        band: b && b.min != null && b.max != null ? [b.min, b.max] : null,
        mean: b?.mean ?? null,
      }
    })
  }, [history])

  if (!data.length) return <p className="text-sm text-text-muted">{t('Brak danych do wykresu')}</p>

  const chart = (
    <ComposedChart data={data} width={width} height={240} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
      <CartesianGrid stroke="var(--color-line)" vertical={false} />
      <XAxis
        dataKey="date"
        tickFormatter={formatDayMonth}
        minTickGap={36}
        tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
        tickLine={false}
        axisLine={{ stroke: 'var(--color-line)' }}
      />
      <YAxis
        unit=" mm"
        width={64}
        tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
        tickLine={false}
        axisLine={false}
      />
      <ReferenceLine y={0} stroke="var(--color-text-muted)" strokeOpacity={0.4} />
      <Area
        dataKey="band"
        name={t('Zakres z 10 lat')}
        stroke="none"
        fill="var(--color-sage)"
        fillOpacity={0.35}
        isAnimationActive={false}
        connectNulls
      />
      <Line
        dataKey="mean"
        name={t('Średnia z 10 lat')}
        stroke="var(--color-brand)"
        strokeDasharray="5 4"
        strokeWidth={1.5}
        dot={false}
        isAnimationActive={false}
        connectNulls
      />
      <Line
        dataKey="value"
        name={t('Ten rok')}
        stroke="var(--color-water)"
        strokeWidth={2.5}
        dot={false}
        isAnimationActive={false}
        connectNulls
      />
      <Tooltip
        labelFormatter={(d) => formatDayMonth(String(d))}
        formatter={(v, name) =>
          Array.isArray(v)
            ? [`${formatNum(Number(v[0]), 0)} … ${formatNum(Number(v[1]), 0)} mm`, name]
            : [`${formatSigned(Number(v), 0)} mm`, name]
        }
        contentStyle={{ borderRadius: 12, border: '1px solid var(--color-line)', fontSize: 13 }}
      />
    </ComposedChart>
  )
  return (
    <figure className="space-y-2">
      {width ? chart : <ResponsiveContainer width="100%" height={240}>{chart}</ResponsiveContainer>}
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs leading-4 text-text-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-[3px] w-5 rounded-full bg-water" aria-hidden /> {t('Ten rok')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0 w-5 border-t-2 border-dashed border-brand" aria-hidden /> {t('Średnia z 10 lat')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-5 rounded-sm bg-sage/40" aria-hidden /> {t('Zakres z 10 lat (od najsuchszego do najmokrzejszego)')}
        </span>
      </figcaption>
    </figure>
  )
}
