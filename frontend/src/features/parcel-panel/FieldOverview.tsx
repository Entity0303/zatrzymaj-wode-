import { MapPinned } from 'lucide-react'
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

/** Obszar przybliżony (brak granic z ULDK) – stały tekst; powodu technicznego nie pokazujemy. */
export function ApproxBanner() {
  const { t } = useLang()
  return (
    <p className="flex items-start gap-2 rounded-xl border border-warn bg-warn-soft px-3.5 py-2.5 text-sm leading-5 text-[#6b4a10]">
      <MapPinned className="mt-px size-4 shrink-0" aria-hidden />
      {t('Obszar przybliżony – brak dokładnych granic działki')}
    </p>
  )
}

/** „Teraz: …” – stan wody dziś jednym zdaniem (bez uprawy: dla typowego pola). */
export function NowLine({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const s = STATUS[analysis.status.level]
  const Icon = s.icon
  return (
    <p className={cn('flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm leading-5', s.bg)}>
      <Icon className={cn('size-5 shrink-0', s.fg)} aria-hidden />
      <span>
        <b>{t('Teraz:')}</b> {t(analysis.status.headline)}
      </span>
    </p>
  )
}

/**
 * Najważniejsze o działce, od razu po jej wybraniu – bez wymaganej uprawy (B3, „mniej na ekranie”):
 * werdykt (3 zdania + „Pokaż wszystko”), stan wody teraz, „Co tu posiać?” (3 najlepsze), „Doprecyzuj” (zwinięte).
 * Liczby, wykresy i źródła – w paszporcie („Pełny raport”) i pod „Szczegóły”.
 */
export function FieldOverview({ analysis, refine, showNow = true }: { analysis: AnalysisResponse; refine: RefineProps; showNow?: boolean }) {
  const s = analysis.suggestions
  const area = s?.area ?? (analysis.cultivated_area_ha ? { value_ha: analysis.cultivated_area_ha, estimated: false, note: '' } : null)
  return (
    <div className="space-y-3">
      {analysis.approximate_area && <ApproxBanner />}
      {analysis.verdict && <VerdictCard verdict={analysis.verdict} compact limit={3} hideCrops={!!s} />}
      {showNow && <NowLine analysis={analysis} />}
      {s && s.groups.some((g) => g.items.length) && <RankingCard suggestions={s} />}
      {!analysis.soil.non_agricultural && <RefineCard {...refine} area={area} rotationHint={s?.rotation_hint} />}
    </div>
  )
}
