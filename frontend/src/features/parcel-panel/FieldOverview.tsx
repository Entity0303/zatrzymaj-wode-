import type { AnalysisResponse, CropId } from '@/api/types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { STATUS } from '@/theme/status'
import { RankingCard } from './RankingCard'
import { RefineCard } from './RefineCard'
import { VerdictCard } from './VerdictCard'

export type RefineProps = {
  crop: CropId | null
  onCropChange: (c: CropId | null) => void
  history: string[]
  onHistoryChange: (h: string[]) => void
  onAreaChange: (ha: number | null) => void
}

/** „Teraz: …” – stan wody dziś jednym zdaniem (bez uprawy: dla typowego pola). */
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
 * w RiskSummary), stan wody teraz, „Co tu posiać?” (3 najlepsze), „Doprecyzuj” (zwinięte).
 */
export function FieldOverview({ analysis, refine, showNow = true }: { analysis: AnalysisResponse; refine: RefineProps; showNow?: boolean }) {
  const s = analysis.suggestions
  const area = s?.area ?? (analysis.cultivated_area_ha ? { value_ha: analysis.cultivated_area_ha, estimated: false, note: '' } : null)
  return (
    <div className="space-y-3">
      {analysis.verdict && <VerdictCard verdict={analysis.verdict} bare limit={3} hideCrops={!!s} />}
      {showNow && <NowLine analysis={analysis} />}
      {s && s.groups.some((g) => g.items.length) && <RankingCard suggestions={s} />}
      <RefineCard {...refine} area={area} rotationHint={s?.rotation_hint} />
    </div>
  )
}
