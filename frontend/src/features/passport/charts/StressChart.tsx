import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { YearStress } from '@/api/types'
import { useLang } from '@/lib/i18n'

/** Dni stresu wodnego w kolejnych latach; bieżący rok wyróżniony (SPEC 7.B). Lata bez danych pominięte. */
export function StressChart({ years, width }: { years: YearStress[]; width?: number }) {
  const { t } = useLang()
  const data = [...years].filter((y) => y.stress_days != null).sort((a, b) => a.year - b.year)
  if (!data.length) return <p className="text-sm text-text-muted">{t('Brak danych do wykresu')}</p>
  const chart = (
    <BarChart data={data} width={width} height={180} margin={{ top: 18, right: 8, bottom: 0, left: -24 }}>
      <CartesianGrid stroke="var(--color-line)" vertical={false} />
      <XAxis dataKey="year" tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={{ stroke: 'var(--color-line)' }} />
      <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }} tickLine={false} axisLine={false} />
      <Tooltip
        formatter={(v) => [t('{n} dni stresu', { n: Number(v) }), t('Dni stresu')]}
        contentStyle={{ borderRadius: 12, border: '1px solid var(--color-line)', fontSize: 13 }}
        cursor={{ fill: 'var(--color-surface-2)' }}
      />
      <Bar dataKey="stress_days" radius={[6, 6, 0, 0]} isAnimationActive={false}>
        {data.map((y) => (
          <Cell key={y.year} fill={y.is_current ? 'var(--color-risk)' : 'var(--color-sage)'} />
        ))}
        <LabelList dataKey="stress_days" position="top" style={{ fontSize: 12, fill: 'var(--color-text)' }} />
      </Bar>
    </BarChart>
  )
  return width ? chart : <ResponsiveContainer width="100%" height={180}>{chart}</ResponsiveContainer>
}
