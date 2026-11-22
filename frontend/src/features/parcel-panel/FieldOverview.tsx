import { BookOpenText, Layers, ListChecks, Mountain, Sprout, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'
import type { AnalysisResponse, CropId } from '@/api/types'
import { LoadingSteps, type Step } from '@/components/LoadingSteps'
import { irrigationShown } from '@/lib/crops'
import { useLang } from '@/lib/i18n'
import { formatDatePl } from '@/lib/format'
import { cn } from '@/lib/utils'
import { STATUS } from '@/theme/status'
import { ChoiceCard } from './ChoiceCard'
import { RankingCard } from './RankingCard'
import { requestPassportJump } from '@/features/passport/jump'
import { RefineCard } from './RefineCard'
import { SatelliteCard } from './SatelliteCard'
import { HydroCard } from './HydroCard'
import { PeriodCard } from '@/features/period/PeriodCard'
import { useSettings } from '@/lib/storage'
import { CropSeasonCard } from './CropSeasonCard'
import { DetailSection } from './DetailSection'
import { IrrigationCard } from './IrrigationCard'
import { KeyMetrics } from './KeyMetrics'
import { SoilCard } from './SoilCard'
import { SoilWaterCard } from './SoilWaterCard'
import { StatusCard } from './StatusCard'
import { TerrainCard } from './TerrainCard'
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
  /** F3: okres użyty w zapytaniu (znacznik) – karta „Okres” */
  period?: string | null
  /** F-MASTER A2: okres wybrany w formularzu (stan widoku) i jego zmiana */
  periodValue?: string | null
  onPeriodChange?: (p: string | null) => void
  /** data siewu wpisana przez rolnika – początek okresu „od siewu” */
  sowing?: string | null
  onSowingChange?: (d: string | null) => void
  asOf?: string
  historical?: boolean
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
        <b>{analysis.historical ? t('W dniu analizy ({d}):', { d: formatDatePl(analysis.analysis_date) }) : t('Teraz:')}</b> {t(analysis.status.headline)}
      </span>
    </p>
  )
}

/**
 * Widok działki pod kartą statusu (F-MASTER A1–A4): formularz „Twoja działka” (od razu rozwinięty) → przyciski
 * raportu (`actions`) → szczegóły w zwijanych sekcjach: „Dlaczego?” (rozwinięta – okres, werdykt: gleba, opady, teren,
 * rośliny), „Gleba i woda w glebie”, „Teren, rowy i satelita”, „Co tu posiać?” (ranking z przychodem),
 * „Co mogę zrobić?”, „Skąd dane”. `full` – panel działki (wszystkie sekcje); bez – zwinięty panel komputera
 * (Dlaczego, Co tu posiać, Co mogę zrobić). Przy przeliczaniu (F13) treść pod formularzem przyciemniona.
 */
export function FieldOverview({
  analysis,
  refine,
  onShowOnMap,
  recalculating,
  actions,
  full,
  steps,
  onOpenPassport,
}: {
  /** F13: trwa przeliczanie – reszta przyciemniona, formularz zostaje aktywny */
  recalculating?: boolean
  analysis: AnalysisResponse
  refine: RefineProps
  /** „Pokaż na mapie” w działaniach */
  onShowOnMap?: (g: GeoJSON.Geometry) => void
  /** przyciski raportu i paszportu – zaraz pod formularzem */
  actions?: ReactNode
  /** wszystkie sekcje szczegółów (panel działki) */
  full?: boolean
  /** kroki analizy – sekcja „Skąd dane” */
  steps?: Step[]
  onOpenPassport?: () => void
}) {
  const { t } = useLang()
  const [settings] = useSettings()
  const advisor = settings.mode === 'doradca'
  const s = analysis.suggestions
  const planOptions = s
    ? [...PLAN_GROUPS, ...s.groups.flatMap((g) => g.items.map((i) => ({ id: i.crop_id, label: i.label }))), ...(s.perennials?.items ?? []).map((i) => ({ id: i.crop_id, label: i.label }))]
    : []
  const area = s?.area ?? (analysis.cultivated_area_ha ? { value_ha: analysis.cultivated_area_ha, estimated: false, note: '' } : null)
  const crop = refine.crop
  const historicalDate = analysis.historical ? analysis.analysis_date : null
  return (
    <div className="space-y-3">
      {/* formularz – zawsze ten sam element (bez odmontowania przy przeliczaniu) */}
      <RefineCard
        {...refine}
        period={refine.periodValue ?? refine.period}
        typicalSowing={crop ? (analysis.crop_season?.season_start ?? null) : null}
        sowingNote={analysis.crop_season?.sowing_note ?? null}
        area={area}
        rotationHint={s?.rotation_hint}
        planOptions={planOptions}
      />
      {actions}
      <div aria-busy={recalculating || undefined} className={cn('space-y-3 transition-opacity', recalculating && 'pointer-events-none opacity-50')}>
        <DetailSection title="Dlaczego?" hint="Gleba, opady, teren i rośliny na tej działce" icon={ListChecks} defaultOpen>
          <PeriodCard period={analysis.period} requested={!!refine.period} />
          {analysis.verdict && <VerdictCard verdict={analysis.verdict} bare hideCrops={!!s} precip={analysis.precip_sources} />}
          {analysis.status.level !== 'ok' && analysis.status.level !== 'no_data' && <NowLine analysis={analysis} />}
        </DetailSection>
        {full && (
          <DetailSection title="Gleba i woda w glebie" hint="Zapas wody, faza uprawy, kategoria gleby" icon={Layers}>
            {crop && <StatusCard crop={crop} analysis={analysis} onOpen={onOpenPassport} />}
            <KeyMetrics analysis={analysis} />
            {analysis.crop_season && <CropSeasonCard season={analysis.crop_season} analysisDate={analysis.analysis_date} />}
            <SoilWaterCard state={analysis.soil_water} pct={analysis.indicators.soil_water_pct.value} />
            <SoilCard soil={analysis.soil} />
          </DetailSection>
        )}
        {(full || advisor) && (
          <DetailSection title="Teren, rowy i satelita" hint="Ukształtowanie terenu, woda w okolicy, zdjęcie satelitarne" icon={Mountain}>
            {full && <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} />}
            <HydroCard hydro={analysis.hydro} historicalDate={historicalDate} />
            {analysis.satellite && <SatelliteCard satellite={analysis.satellite} />}
          </DetailSection>
        )}
        {s && (s.groups.some((g) => g.items.length) || (s.choice?.length ?? 0) > 0) && (
          <DetailSection title="Co tu posiać?" hint="Ranking upraw z plonem i przychodem z pola" icon={Sprout}>
            <ChoiceCard suggestions={s} priceNow={analysis.price_now} />
            {s.groups.some((g) => g.items.length) && <RankingCard suggestions={s} priceNow={analysis.price_now} />}
            {onOpenPassport && (
              <button
                type="button"
                onClick={() => {
                  requestPassportJump('pp-ceny')
                  onOpenPassport()
                }}
                className="flex min-h-11 items-center text-sm font-semibold text-brand-dark underline-offset-2 hover:underline"
              >
                {t('Ceny i pogoda na tle lat →')}
              </button>
            )}
          </DetailSection>
        )}
        {analysis.recommendations.length > 0 && (
          <DetailSection title="Co mogę zrobić?" hint="Najpierw zatrzymanie wody, potem uprawa, na końcu nawadnianie" icon={Wrench}>
            <WhatToDo analysis={analysis} onShowOnMap={onShowOnMap} />
            {full && analysis.irrigation && irrigationShown(analysis) && <IrrigationCard plan={analysis.irrigation} />}
          </DetailSection>
        )}
        {full && steps && (
          <DetailSection title="Skąd dane" hint="Źródła i przebieg analizy" icon={BookOpenText}>
            <LoadingSteps steps={steps} />
          </DetailSection>
        )}
      </div>
    </div>
  )
}
