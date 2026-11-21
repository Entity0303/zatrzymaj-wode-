import type { AnalysisResponse, RecommendationCategory } from '@/api/types'
import { RecommendationCard } from '@/components/RecommendationCard'
import { REC_CATEGORY } from '@/theme/recommendations'

const ORDER: RecommendationCategory[] = ['retencja', 'agrotechnika', 'nawadnianie']

/**
 * D. Co mogę zrobić? (SPEC 7.D) – zawsze trzy grupy w kolejności retencja → agrotechnika → nawadnianie.
 * TODO (osoba B): „Pokaż na mapie” (recommendation.location), dane wejściowe w „Dlaczego?”.
 */
export function SectionD({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <section aria-labelledby="pass-d" className="space-y-4">
      <h3 id="pass-d" className="text-lg leading-6 font-semibold">
        Co mogę zrobić?
      </h3>
      {ORDER.map((cat) => {
        const recs = analysis.recommendations.filter((r) => r.category === cat)
        return (
          <div key={cat} className="space-y-2">
            <h4 className="text-base font-semibold">{REC_CATEGORY[cat].label}</h4>
            {recs.length === 0 && <p className="text-sm text-text-muted">Brak rekomendacji w tej grupie.</p>}
            {recs.map((r) => (
              <RecommendationCard key={r.id} category={r.category} title={r.title} text={r.description} why={r.why} />
            ))}
          </div>
        )
      })}
    </section>
  )
}
