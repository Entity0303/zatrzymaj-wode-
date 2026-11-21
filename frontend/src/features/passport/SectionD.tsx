import type { AnalysisResponse, RecommendationCategory } from '@/api/types'
import { RecommendationCard } from '@/components/RecommendationCard'
import { IrrigationCard } from '@/features/parcel-panel/IrrigationCard'
import { RecommendationWhy } from '@/features/parcel-panel/RecommendationWhy'
import { REC_CATEGORY } from '@/theme/recommendations'
import { useLang } from '@/lib/i18n'
import { PassportSection } from './PassportSection'

const ORDER: RecommendationCategory[] = ['retencja', 'agrotechnika', 'nawadnianie']

/** Paszport: maks. 5 rekomendacji (uwagi mentora; panel – 3). */
const MAX = 5

/**
 * D. Co mogę zrobić? (SPEC 7.D) – zawsze trzy grupy w kolejności retencja → agrotechnika → nawadnianie,
 * w grupie wg priorytetu; „Dlaczego?” z danymi; „Pokaż na mapie”, gdy jest miejsce.
 */
export function SectionD({ analysis, onShowOnMap }: { analysis: AnalysisResponse; onShowOnMap?: (g: GeoJSON.Geometry) => void }) {
  const { t } = useLang()
  const sorted = [...analysis.recommendations]
    .sort((a, b) => ORDER.indexOf(a.category) - ORDER.indexOf(b.category) || (b.priority ?? 0) - (a.priority ?? 0))
    .slice(0, MAX)
  return (
    <PassportSection id="pass-d" letter="D" title={t('Co mogę zrobić?')}>
      {ORDER.map((cat) => {
        const recs = sorted.filter((r) => r.category === cat)
        const Icon = REC_CATEGORY[cat].icon
        return (
          <div key={cat} className="space-y-2.5">
            <h4 className="flex items-center gap-2 text-base leading-6 font-semibold">
              <Icon className="size-5 text-brand" aria-hidden /> {t(REC_CATEGORY[cat].label)}
            </h4>
            {recs.length === 0 && cat !== 'nawadnianie' && (
              <p className="rounded-xl bg-surface-2/60 px-4 py-3 text-sm text-text-muted">{t('Brak zaleceń w tej grupie dla tej działki i daty.')}</p>
            )}
            {recs.map((r) => (
              <RecommendationCard
                key={r.id}
                category={r.category}
                title={r.title}
                text={r.description}
                why={<RecommendationWhy rec={r} />}
                onShowOnMap={r.location && onShowOnMap ? () => onShowOnMap(r.location!) : undefined}
              />
            ))}
            {cat === 'nawadnianie' && analysis.irrigation && <IrrigationCard plan={analysis.irrigation} />}
          </div>
        )
      })}
    </PassportSection>
  )
}
