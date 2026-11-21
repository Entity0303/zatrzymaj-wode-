import type { SeasonalBalanceYear } from '@/api/types'
import { formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'

const H = 180
const PAD_TOP = 18
const PAD_BOTTOM = 22

/**
 * „Na tle 10 lat” (A5e): po jednym słupku na rok – ile wody zostało (spadło minus wyparowało) na ten sam dzień
 * sezonu. Ujemne w dół od zera. Bieżący rok wyróżniony: czerwony, gdy poniżej średniej, zielony – powyżej;
 * poprzednie lata szare; przerywana linia = średnia. Własny SVG (lekki, czytelny też w wydruku).
 */
export function SeasonBars({ years, mean, width = 640 }: { years: SeasonalBalanceYear[]; mean: number | null | undefined; width?: number }) {
  const { t } = useLang()
  const vals = years.map((y) => y.balance_mm)
  const lo = Math.min(0, ...vals, mean ?? 0)
  const hi = Math.max(0, ...vals, mean ?? 0)
  const span = Math.max(1, hi - lo)
  const y = (v: number) => PAD_TOP + ((hi - v) / span) * (H - PAD_TOP - PAD_BOTTOM)
  const n = years.length
  const slot = width / Math.max(1, n)
  const bw = Math.min(40, slot * 0.62)
  const zero = y(0)

  return (
    <svg viewBox={`0 0 ${width} ${H}`} className="h-auto w-full" role="img" aria-label={t('Ile wody zostało w każdym roku na ten sam dzień sezonu')}>
      <line x1="0" x2={width} y1={zero} y2={zero} stroke="var(--color-text-muted)" strokeOpacity=".4" />
      {years.map((yr, i) => {
        const cx = slot * i + slot / 2
        const top = Math.min(y(yr.balance_mm), zero)
        const h = Math.max(1, Math.abs(y(yr.balance_mm) - zero))
        const fill = yr.current ? (mean != null && yr.balance_mm < mean ? 'var(--color-danger)' : 'var(--color-ok)') : '#B8BDB9'
        return (
          <g key={yr.year}>
            <rect x={cx - bw / 2} y={top} width={bw} height={h} rx="3" fill={fill}>
              <title>{`${yr.year}: ${formatSigned(yr.balance_mm, 0)} mm`}</title>
            </rect>
            {yr.current && (
              // wartość po drugiej stronie zera niż słupek – nie wchodzi na podpis roku
              <text x={cx} y={yr.balance_mm < 0 ? zero - 6 : zero + 14} textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--color-text)">
                {formatSigned(yr.balance_mm, 0)}
              </text>
            )}
            <text x={cx} y={H - 6} textAnchor="middle" fontSize="11" fill={yr.current ? 'var(--color-text)' : 'var(--color-text-muted)'} fontWeight={yr.current ? 600 : 400}>
              {String(yr.year).slice(2)}
              {yr.current ? '*' : ''}
            </text>
          </g>
        )
      })}
      {mean != null && (
        <>
          <line x1="0" x2={width} y1={y(mean)} y2={y(mean)} stroke="var(--color-water)" strokeWidth="1.5" strokeDasharray="5 4" />
          <text
            x={4}
            y={y(mean) - 6}
            textAnchor="start"
            fontSize="12"
            fontWeight="600"
            fill="var(--color-water)"
            stroke="white"
            strokeWidth="3"
            paintOrder="stroke"
          >
            {t('średnia {v} mm', { v: formatSigned(mean, 0) })}
          </text>
        </>
      )}
    </svg>
  )
}
