import { ChartNoAxesCombined } from 'lucide-react'
import { useMemo } from 'react'
import type { AnalysisResponse } from '@/api/types'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { NoDataNote as NoData } from '@/components/NoDataNote'
import { SourceTag } from '@/components/SourceTag'
import { formatDayLong, formatNum, formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { seasonBalance } from '@/lib/seasonBalance'

const W = 220
const H = 56

/**
 * Bilans wody (SPEC 4.5): podpisany, CZYJ to bilans („Działka 6/1”), ta sama liczba co w paszporcie –
 * „od 1 marca: −192 mm (suchy sezon)” – i wyjaśnienie prostymi słowami („221 mm mniej wody niż średnio
 * w ostatnich 10 latach”); mała linia sezonu na tle pasma 10 lat. Grunt nierolny – karty nie ma.
 */
export function BalanceCard({ analysis }: { analysis: AnalysisResponse | null }) {
  const { t } = useLang()
  const h = analysis?.history
  const geom = useMemo(() => {
    if (!h || h.balance_cumulative.length < 2) return null
    const band = h.balance_band
    const vals = [
      ...h.balance_cumulative.map((p) => p.value),
      ...band.flatMap((b) => [b.min, b.max, b.mean]),
    ].filter((v): v is number => v != null)
    if (!vals.length) return null
    const lo = Math.min(...vals)
    const hi = Math.max(...vals)
    const n = Math.max(band.length, h.balance_cumulative.length)
    const x = (i: number) => (i / Math.max(1, n - 1)) * W
    const y = (v: number) => H - 4 - ((v - lo) / Math.max(1, hi - lo)) * (H - 8)
    const line = (pts: (number | null | undefined)[]) =>
      pts.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(' ')
    const top = band.map((b, i) => (b.max == null ? null : `${x(i).toFixed(1)},${y(b.max).toFixed(1)}`)).filter(Boolean)
    const bottom = band.map((b, i) => (b.min == null ? null : `${x(i).toFixed(1)},${y(b.min).toFixed(1)}`)).filter(Boolean).reverse()
    return {
      area: top.length && bottom.length ? [...top, ...bottom].join(' ') : null,
      mean: line(band.map((b) => b.mean)),
      cur: line(h.balance_cumulative.map((p) => p.value)),
      zero: lo < 0 && hi > 0 ? y(0) : null,
    }
  }, [h])

  if (!analysis || !h || !geom)
    return (
      <Card icon={ChartNoAxesCombined} title="Bilans wody">
        <NoData text={analysis ? 'Brak danych o wodzie w sezonie dla tej działki' : 'Wybierz działkę – pokażemy, ile wody zostało w sezonie'} />
      </Card>
    )
  const dev = h.balance_deviation_mm
  // ta sama liczba co w paszporcie i raporcie (słupek bieżącego roku)
  const { mm: now, kind: season, from } = seasonBalance(analysis)
  const whose = analysis.parcel.source === 'approximate' ? t('Obszar przybliżony') : t('Działka {numer}', { numer: analysis.parcel.numer })
  return (
    <Card icon={ChartNoAxesCombined} title="Bilans wody" aside={<span className="text-xs text-text-muted">{whose}</span>}>
      {now != null && (
        <p className="text-sm leading-5">
          {t('od {d}:', { d: formatDayLong(from) })} <b className="tabular">{formatSigned(now, 0)} mm</b>
          {season && <span className="text-text-muted"> ({t(season)})</span>}
        </p>
      )}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-14 w-full" role="img" aria-label={t('Bilans wody w sezonie na tle 10 lat')}>
        {geom.area && <polygon points={geom.area} fill="var(--color-sage)" opacity=".35" />}
        {geom.zero != null && <line x1="0" x2={W} y1={geom.zero} y2={geom.zero} stroke="var(--color-text-muted)" strokeOpacity=".35" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
        <polyline points={geom.mean} fill="none" stroke="var(--color-brand)" strokeDasharray="4 3" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
        <polyline points={geom.cur} fill="none" stroke="var(--color-water)" strokeWidth="2.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <p className="mt-auto flex flex-wrap items-center gap-x-1.5 text-sm leading-5">
        {dev != null ? (
          <span>
            {Math.round(dev) === 0
              ? t('Tyle wody, ile średnio w ostatnich 10 latach')
              : t(dev < 0 ? '{n} mm mniej wody niż średnio w ostatnich 10 latach' : '{n} mm więcej wody niż średnio w ostatnich 10 latach', {
                  n: formatNum(Math.abs(dev), 0),
                })}
          </span>
        ) : (
          <span className="text-text-muted">{t('Średnia z 10 lat: brak danych')}</span>
        )}
        <SourceTag kind={h.source_tag.kind} title={h.source_tag.source ?? undefined} className="ml-auto" />
      </p>
    </Card>
  )
}
