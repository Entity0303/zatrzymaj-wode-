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
 * Zakładka „Przegląd” (B3, „mniej na ekranie”): zdania werdyktu (3 + „Pokaż wszystko”; nagłówek jest wyżej
 * w RiskSummary), stan wody teraz, „Z satelity” (A11), „Woda w okolicy” (F3), „Co tu posiać?” (3 najlepsze,
 * z przychodem F3), „Doprecyzuj” (zwinięte). Na samej górze karta „Okres”, gdy rolnik wybrał okres (F3).
 */
export function FieldOverview({ analysis, refine, showNow = true }: { analysis: AnalysisResponse; refine: RefineProps; showNow?: boolean }) {
  const s = analysis.suggestions
  const planOptions = s
    ? [...PLAN_GROUPS, ...s.groups.flatMap((g) => g.items.map((i) => ({ id: i.crop_id, label: i.label }))), ...(s.perennials?.items ?? []).map((i) => ({ id: i.crop_id, label: i.label }))]
    : []
  const area = s?.area ?? (analysis.cultivated_area_ha ? { value_ha: analysis.cultivated_area_ha, estimated: false, note: '' } : null)
  return (
    <div className="space-y-3">
      <PeriodCard period={analysis.period} requested={!!refine.period} />
      {analysis.verdict && <VerdictCard verdict={analysis.verdict} bare limit={3} hideCrops={!!s} precip={analysis.precip_sources} />}
      {showNow && <NowLine analysis={analysis} />}
      {analysis.satellite && <SatelliteCard satellite={analysis.satellite} />}
      <HydroCard hydro={analysis.hydro} />
      {s && <ChoiceCard suggestions={s} priceNow={analysis.price_now} />}
      {s && s.groups.some((g) => g.items.length) && <RankingCard suggestions={s} priceNow={analysis.price_now} />}
      <RefineCard {...refine} area={area} rotationHint={s?.rotation_hint} planOptions={planOptions} />
    </div>
  )
}
