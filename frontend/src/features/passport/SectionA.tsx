import { Droplet, Droplets, Gauge, Layers, Leaf } from 'lucide-react'
import type { AnalysisResponse, Indicator } from '@/api/types'
import { MetricCard } from '@/components/MetricCard'
import { ScoreRing } from '@/components/ScoreRing'
import { StatusBadge } from '@/components/StatusBadge'
import { formatDatePl, formatNum } from '@/lib/format'
import { STATUS } from '@/theme/status'
import { useLang } from '@/lib/i18n'
import { PassportSection } from './PassportSection'
import { TerrainCard } from '@/features/parcel-panel/TerrainCard'

const val = (i: Indicator, digits = 0) => (i.value === null ? null : formatNum(i.value, digits))
const tagDate = (i: Indicator) => (i.source_tag.date ? formatDatePl(i.source_tag.date) : undefined)

/**
 * A. Stan obecny (SPEC 7.A): ogólny stan wodny 0–100 w okręgu, karty: woda w glebie (% i mm),
 * kondycja upraw, wilgotność roślin, ryzyko 7 dni, ile wody zmieści gleba; zdanie podsumowania.
 */
export function SectionA({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const { status, indicators: ind } = analysis
  const s = STATUS[status.level]
  return (
    <PassportSection id="pass-a" letter="A" title={t('Stan obecny')}>
      <div className="flex flex-wrap items-center gap-5 rounded-xl bg-surface p-4 shadow-card">
        <ScoreRing
          value={status.score ?? null}
          size={120}
          stroke={12}
          color={s.ring.color}
          track={s.ring.track}
          caption={status.score == null ? undefined : 'na 100'}
        />
        <div className="min-w-0 flex-1 basis-56 space-y-1.5">
          <StatusBadge status={status.level} />
          <p className="font-display text-xl leading-7 font-semibold">{t(status.headline)}</p>
          <p className="text-base leading-6">{t(status.summary)}</p>
          <p className="text-xs leading-4 text-text-muted">{t('Ogólny stan wodny: 100 = dużo wody, 0 = susza.')}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <MetricCard
          icon={Droplets}
          title="Woda w glebie"
          value={val(ind.soil_water_pct)}
          unit="%"
          tone="water"
          source={ind.soil_water_pct.source_tag.kind}
          sourceDate={tagDate(ind.soil_water_pct)}
          noDataText="Brak danych"
        >
          {ind.soil_water_mm.value !== null && (
            <p className="text-sm leading-5 text-text-muted">{t('to ok. {mm} mm wody', { mm: formatNum(ind.soil_water_mm.value, 0) })}</p>
          )}
        </MetricCard>
        <MetricCard
          icon={Gauge}
          title="Ryzyko na 7 dni"
          value={ind.risk_7d.label ? t(ind.risk_7d.label) : val(ind.risk_7d)}
          tone="warn"
          source={ind.risk_7d.source_tag.kind}
          sourceDate={tagDate(ind.risk_7d)}
          noDataText="Brak danych"
        >
          {ind.risk_7d.note && <p className="text-sm leading-5 text-text-muted">{t(ind.risk_7d.note)}</p>}
        </MetricCard>
        <MetricCard
          icon={Leaf}
          title="Kondycja upraw"
          value={ind.crop_health.label ? t(ind.crop_health.label) : val(ind.crop_health)}
          tone="brand"
          source={ind.crop_health.source_tag.kind}
          sourceDate={tagDate(ind.crop_health)}
          noDataText={ind.crop_health.note ?? 'Brak danych'}
        />
        <MetricCard
          icon={Droplet}
          title="Wilgotność roślin"
          value={ind.plant_moisture.label ? t(ind.plant_moisture.label) : val(ind.plant_moisture)}
          tone="water"
          source={ind.plant_moisture.source_tag.kind}
          sourceDate={tagDate(ind.plant_moisture)}
          noDataText={ind.plant_moisture.note ?? 'Brak danych'}
        />
        <MetricCard
          icon={Layers}
          title="Ile wody zmieści gleba"
          value={val(ind.soil_capacity)}
          unit="mm"
          tone="earth"
          source={ind.soil_capacity.source_tag.kind}
          sourceDate={tagDate(ind.soil_capacity)}
          noDataText="Brak danych"
        >
          {ind.soil_capacity.label && <p className="text-sm leading-5 text-text-muted">{t(ind.soil_capacity.label)}</p>}
        </MetricCard>
      </div>
      <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} />
    </PassportSection>
  )
}
