import { ArrowDown, ArrowUp, ChartNoAxesCombined, Droplets, Gauge, Leaf } from 'lucide-react'
import { MetricCard } from '@/components/MetricCard'
import { ScoreRing } from '@/components/ScoreRing'
import type { AnalysisResponse, Indicator } from '@/api/types'
import { formatDatePl, formatNum, formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'

/** Wartość wskaźnika jako tekst; null = brak danych (karta pokaże kreskowanie). */
const num = (i: Indicator, digits = 0, signed = false) =>
  i.value === null ? null : signed ? formatSigned(i.value, digits) : formatNum(i.value, digits)
const tagDate = (i: Indicator) => (i.source_tag.date ? formatDatePl(i.source_tag.date) : undefined)

/** 4. Kluczowe wskaźniki 2×2 (SPEC 6.4). */
export function KeyMetrics({ loading, analysis }: { loading?: boolean; analysis?: AnalysisResponse | null }) {
  if (analysis && !loading) return <AnalysisMetrics analysis={analysis} />
  return (
    <div className="grid grid-cols-2 gap-3">
      <MetricCard icon={Droplets} title="Zapas wody w glebie" value={null} unit="% pełnego" tone="water" source="szacunek_modelu" loading={loading}>
        <div className="h-1.5 rounded-full bg-surface-2" aria-hidden />
      </MetricCard>
      <MetricCard icon={Gauge} title="Ryzyko na 7 dni" value={null} tone="warn" source="prognoza" loading={loading} />
      <MetricCard icon={Leaf} title="Kondycja upraw" value={null} tone="brand" source="satelita" loading={loading}>
        {!loading && <ScoreRing value={null} size={56} stroke={6} className="self-start" />}
      </MetricCard>
      <MetricCard
        icon={ChartNoAxesCombined}
        title="Bilans wody w sezonie"
        value={null}
        unit="mm"
        tone="water"
        source="obliczenia"
        loading={loading}
      />
    </div>
  )
}

function AnalysisMetrics({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const { soil_water_pct: water, risk_7d: risk, crop_health: health, water_balance_season: balance } = analysis.indicators
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-3">
      <MetricCard
        icon={Droplets}
        title="Zapas wody w glebie"
        value={num(water)}
        unit={(water.unit ?? '%') === '%' ? '% pełnego' : water.unit!}
        tone="water"
        source={water.source_tag.kind}
        sourceDate={tagDate(water)}
      >
        {water.value !== null && (
          <>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
              <div className="h-full rounded-full bg-water" style={{ width: `${Math.max(0, Math.min(100, water.value))}%` }} />
            </div>
            <p className="text-sm leading-5 text-text-muted">{t('tyle wody dostępnej dla roślin jest teraz w glebie')}</p>
          </>
        )}
      </MetricCard>
      <MetricCard
        icon={Gauge}
        title="Ryzyko na 7 dni"
        value={risk.value === null && !risk.label ? null : risk.label ? t(risk.label) : num(risk)}
        tone="warn"
        source={risk.source_tag.kind}
        sourceDate={tagDate(risk)}
      >
        {risk.note && <p className="text-sm leading-5 text-text-muted">{t(risk.note)}</p>}
      </MetricCard>
      <MetricCard
        icon={Leaf}
        title="Kondycja upraw"
        value={health.value === null ? null : health.label ? t(health.label) : num(health)}
        tone="brand"
        source={health.source_tag.kind}
        sourceDate={tagDate(health)}
      >
        <ScoreRing value={health.value} size={56} stroke={6} caption="na 100" className="self-start" />
      </MetricCard>
      <MetricCard
        icon={ChartNoAxesCombined}
        title="Bilans wody w sezonie"
        value={balance.value === null ? null : formatNum(Math.abs(balance.value), 0)}
        unit={balance.unit ?? 'mm'}
        tone={balance.value !== null && balance.value < 0 ? 'danger' : 'water'}
        valuePrefix={
          balance.value === null || balance.value === 0 ? undefined : balance.value < 0 ? (
            // F12: ujemny bilans = „zabrakło X mm”, nie „−X mm”
            <span className="flex items-center gap-1 self-center text-base font-semibold text-danger">
              <ArrowDown className="size-5" strokeWidth={2.25} aria-hidden />
              {t('zabrakło')}
            </span>
          ) : (
            <ArrowUp className="size-6 self-center text-water" strokeWidth={2.25} aria-hidden />
          )
        }
        source={balance.source_tag.kind}
        sourceDate={tagDate(balance)}
      >
        {balance.note && <p className="text-sm leading-5 text-text-muted">{t(balance.note)}</p>}
      </MetricCard>
      </div>
      <p className="text-xs leading-4 text-text-muted">{t('1 mm wody = 1 litr na każdy metr kwadratowy pola.')}</p>
    </div>
  )
}
