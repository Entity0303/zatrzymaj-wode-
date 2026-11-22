import type { SeasonalBalanceYear } from '@/api/types'
import { formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'

const H = 220
const PAD_TOP = 22
/** miejsce na wartość pod najniższym słupkiem i rok */
const PAD_BOTTOM = 40
/** F35: prawy margines na podpis średniej – poza słupkami, żeby nie zasłaniał ich wartości */
const PAD_RIGHT = 84
/** wysokość podpisu wartości nad linią pisma i pod nią (do sprawdzenia kolizji z linią średniej) */
const LABEL_UP = 10
const LABEL_DOWN = 3

/**
 * „Woda na tle 10 lat” (A5e, F6): po jednym słupku na rok – bilans wody (opad minus parowanie) na ten sam dzień
 * sezonu. Ujemne w dół od zera, wartości pod słupkami (nad – dla dodatnich), przerywana linia = średnia.
 * Bieżący rok pogrubiony: kolor ryzyka (#E07B39), gdy poniżej średniej, kolor wody – powyżej; poprzednie lata szare.
 * F35: podpis średniej stoi przy prawej krawędzi, poza słupkami; wartość słupka, na którą wypadłaby linia średniej,
 * jest odsunięta pod linię (dodatnia – nad linię), a wartości rysujemy po linii, z białą obwódką.
 * Własny SVG (lekki, czytelny też w wydruku).
 */
export function SeasonBars({ years, mean, width = 640 }: { years: SeasonalBalanceYear[]; mean: number | null | undefined; width?: number }) {
  const { t } = useLang()
  const vals = years.map((y) => y.balance_mm)
  const lo = Math.min(0, ...vals, mean ?? 0)
  const hi = Math.max(0, ...vals, mean ?? 0)
  const span = Math.max(1, hi - lo)
  const y = (v: number) => PAD_TOP + ((hi - v) / span) * (H - PAD_TOP - PAD_BOTTOM)
  const n = years.length
  const plotW = mean != null ? width - PAD_RIGHT : width
  const slot = plotW / Math.max(1, n)
  const bw = Math.min(40, slot * 0.62)
  const zero = y(0)
  const meanY = mean != null ? y(mean) : null
  const bars = years.map((yr, i) => {
    const cx = slot * i + slot / 2
    const end = y(yr.balance_mm)
    // wartość pod słupkiem (ujemne) albo nad nim (dodatnie)
    let labelY = yr.balance_mm < 0 ? end + 13 : end - 5
    if (meanY != null && labelY - LABEL_UP <= meanY && meanY <= labelY + LABEL_DOWN) {
      labelY = yr.balance_mm < 0 ? meanY + LABEL_UP + 4 : meanY - LABEL_DOWN - 3
    }
    return { yr, cx, end, labelY: Math.min(labelY, H - 22) }
  })

  return (
    <svg viewBox={`0 0 ${width} ${H}`} className="tabular h-auto w-full" role="img" aria-label={t('Bilans wody w każdym roku na ten sam dzień sezonu')}>
      <line x1="0" x2={plotW} y1={zero} y2={zero} stroke="var(--color-text-muted)" strokeOpacity=".4" />
      {bars.map(({ yr, cx, end }) => {
        const top = Math.min(end, zero)
        const h = Math.max(1, Math.abs(end - zero))
        const fill = yr.current ? (mean != null && yr.balance_mm < mean ? 'var(--color-pp-risk)' : 'var(--color-pp-water)') : '#C9CCC6'
        return (
          <rect key={yr.year} x={cx - bw / 2} y={top} width={bw} height={h} rx="3" fill={fill}>
            <title>{`${yr.year}: ${formatSigned(yr.balance_mm, 0)} mm`}</title>
          </rect>
        )
      })}
      {mean != null && meanY != null && (
        <>
          <line x1="0" x2={plotW} y1={meanY} y2={meanY} stroke="var(--color-pp-water)" strokeWidth="1.5" strokeDasharray="5 4" />
          <text x={plotW + 6} y={meanY - 2} textAnchor="start" fontSize="12" fontWeight="600" fill="var(--color-pp-water)">
            {t('średnia')}
          </text>
          <text x={plotW + 6} y={meanY + 12} textAnchor="start" fontSize="12" fontWeight="600" fill="var(--color-pp-water)">
            {formatSigned(mean, 0)} mm
          </text>
        </>
      )}
      {bars.map(({ yr, cx, labelY }) => {
        const weight = yr.current ? 700 : 400
        const color = yr.current ? 'var(--color-text)' : 'var(--color-text-muted)'
        return (
          <g key={yr.year}>
            <text x={cx} y={labelY} textAnchor="middle" fontSize={yr.current ? 12 : 10.5} fontWeight={weight} fill={color} stroke="white" strokeWidth="3" paintOrder="stroke">
              {formatSigned(yr.balance_mm, 0)}
            </text>
            <text x={cx} y={H - 6} textAnchor="middle" fontSize="11" fill={color} fontWeight={weight}>
              {yr.year}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
