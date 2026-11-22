import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { SatelliteSeriesPoint } from '@/api/types'
import { formatDatePl, formatNum } from '@/lib/format'
import { locale, useLang } from '@/lib/i18n'

/** Kolory z kontraktu A11: kondycja (NDVI) zielona, wilgotność roślin (NDMI) niebieska. */
const GREEN = '#3F8E4E'
const BLUE = '#2F80C9'

/**
 * Mały wykres szeregu zdjęć z 12 miesięcy (A11 `satellite.series`): linia „kondycja roślin”, w paszporcie także
 * „wilgotność roślin”. Bez liczb na osi w panelu – liczby wskaźników są w szczegółach.
 */
export function SatelliteSeriesChart({
  series,
  withMoisture,
  height = 110,
  width,
}: {
  series: SatelliteSeriesPoint[]
  withMoisture?: boolean
  height?: number
  /** stała szerokość (wydruk) */
  width?: number
}) {
  const { t } = useLang()
  const data = series.filter((p) => p.ndvi != null || p.ndmi != null)
  if (data.length < 2) return null
  const month = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { month: 'short' })
  const chart = (
    <LineChart data={data} width={width} height={height} margin={{ top: 6, right: 8, bottom: 0, left: withMoisture ? -18 : 8 }}>
      <CartesianGrid stroke="var(--color-line)" vertical={false} />
      <XAxis
        dataKey="date"
        tickFormatter={month}
        tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
        tickLine={false}
        axisLine={{ stroke: 'var(--color-line)' }}
        minTickGap={18}
      />
      <YAxis domain={withMoisture ? [-0.4, 1] : [0, 1]} hide={!withMoisture} width={44} tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={false} tickFormatter={(v) => formatNum(Number(v), 1)} />
      <Tooltip
        labelFormatter={(d) => t('zdjęcie z {d}', { d: formatDatePl(String(d)) })}
        formatter={(v, name) => [v == null ? t('brak danych') : formatNum(Number(v), 2), name]}
        contentStyle={{ borderRadius: 12, border: '1px solid var(--color-line)', fontSize: 13 }}
      />
      <Line dataKey="ndvi" name={t('kondycja roślin')} stroke={GREEN} strokeWidth={2.5} dot={{ r: 2.5 }} connectNulls isAnimationActive={false} />
      {withMoisture && (
        <Line dataKey="ndmi" name={t('wilgotność roślin')} stroke={BLUE} strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
      )}
    </LineChart>
  )
  return (
    <figure className="space-y-1.5">
      {width ? chart : <ResponsiveContainer width="100%" height={height}>{chart}</ResponsiveContainer>}
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs leading-4 text-text-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full" style={{ background: GREEN }} aria-hidden /> {t('kondycja roślin (wyżej = bujniej)')}
        </span>
        {withMoisture && (
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ background: BLUE }} aria-hidden /> {t('wilgotność roślin (wyżej = więcej wody)')}
          </span>
        )}
      </figcaption>
    </figure>
  )
}
