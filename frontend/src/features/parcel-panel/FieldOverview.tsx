import type { AnalysisResponse, CropId } from '@/api/types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { STATUS } from '@/theme/status'
import { ChoiceCard } from './ChoiceCard'
import { RankingCard } from './RankingCard'
import { RefineCard } from './RefineCard'
import { SatelliteCard } from './SatelliteCard'
import { HydroCard } from './HydroCard'
import { PeriodCard } from '@/features/period/PeriodCard'
import { useSettings } from '@/lib/storage'
import { SectionTitle } from './SectionTitle'
import { WhatToDo } from './WhatToDo'
import { VerdictCard } from './VerdictCard'

export type RefineProps = {
  crop: CropId | null
  onCropChange: (c: CropId | null) => void
  history: string[]
  onHistoryChange: (h: string[]) => void
  onAreaChange: (ha: number | null) => void
  /** A5e: plan upraw (do 3) */
  planned: string[]
  onPlannedChange: (p: string[]) => void
  /** F3: wybrany okres (znacznik) – karta „Okres” na górze */
  period?: string | null
}

/** Grupy upraw, które backend przyjmuje w planie (wybierze najlepszy gatunek z grupy). */
const PLAN_GROUPS = [
  { id: 'zboza_ozime', label: 'Zboża ozime (dowolne)' },
  { id: 'zboza_jare', label: 'Zboża jare (dowolne)' },
]

/** „Teraz: …” – stan wody dziś jednym zdaniem (bez uprawy: dla typowego pola); werdykt mówi o działce na lata. */
export function NowLine({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const s = STATUS[analysis.status.level]
  const Icon = s.icon
  return (
    <p className="flex items-center gap-2.5 rounded-xl border bg-surface px-3.5 py-2.5 text-sm leading-5">
      <Icon className={cn('size-5 shrink-0', s.fg)} aria-hidden />
      <span>
        <b>{t('Teraz:')}</b> {t(analysis.status.headline)}
      </span>
    </p>
  )
}

/**
 * Główny widok działki (F5, tryb Rolnik – krótko): zdania werdyktu (3 + „Pokaż wszystko”; nagłówek i „Teraz / Na dłuższą
 * metę” są wyżej w RiskSummary), „Teraz: …” tylko gdy stan wody nie jest dobry, „Co tu posiać?” (wybór + 3 najlepsze),
 * „Co zrobić?” (maks. 3 działania), „Doprecyzuj” (zwinięte). Na górze karta „Okres”, gdy wybrano okres (F3).
 * Tryb Doradca: dodatkowo od razu „Z satelity” i „Woda w okolicy” (w trybie Rolnik są w „Szczegółach”).
 */
export function FieldOverview({
  analysis,
  refine,
  onShowOnMap,
}: {
  analysis: AnalysisResponse
  refine: RefineProps
  /** „Pokaż na mapie” w działaniach */
  onShowOnMap?: (g: GeoJSON.Geometry) => void
}) {
  const { t } = useLang()
  const [settings] = useSettings()
  const advisor = settings.mode === 'doradca'
  const s = analysis.suggestions
  const planOptions = s
    ? [...PLAN_GROUPS, ...s.groups.flatMap((g) => g.items.map((i) => ({ id: i.crop_id, label: i.label }))), ...(s.perennials?.items ?? []).map((i) => ({ id: i.crop_id, label: i.label }))]
    : []
  const area = s?.area ?? (analysis.cultivated_area_ha ? { value_ha: analysis.cultivated_area_ha, estimated: false, note: '' } : null)
  return (
    <div className="space-y-3">
      <PeriodCard period={analysis.period} requested={!!refine.period} />
      {analysis.verdict && <VerdictCard verdict={analysis.verdict} bare limit={3} hideCrops={!!s} precip={analysis.precip_sources} />}
      {analysis.status.level !== 'ok' && analysis.status.level !== 'no_data' && <NowLine analysis={analysis} />}
      {advisor && analysis.satellite && <SatelliteCard satellite={analysis.satellite} />}
      {advisor && <HydroCard hydro={analysis.hydro} />}
      {s && <ChoiceCard suggestions={s} priceNow={analysis.price_now} />}
      {s && s.groups.some((g) => g.items.length) && <RankingCard suggestions={s} priceNow={analysis.price_now} />}
      {analysis.recommendations.length > 0 && (
        <section className="space-y-3 pt-1">
          <SectionTitle>{t('Co zrobić?')}</SectionTitle>
          <WhatToDo analysis={analysis} onShowOnMap={onShowOnMap} />
        </section>
      )}
      <RefineCard {...refine} area={area} rotationHint={s?.rotation_hint} planOptions={planOptions} />
    </div>
  )
}
