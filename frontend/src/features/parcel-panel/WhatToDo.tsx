import type { AnalysisResponse, RecommendationCategory } from '@/api/types'
import { RecommendationCard } from '@/components/RecommendationCard'
import { useLang } from '@/lib/i18n'
import { RecommendationWhy } from './RecommendationWhy'

const ORDER: RecommendationCategory[] = ['retencja', 'agrotechnika', 'nawadnianie']

/** 5. „Co zrobić?” – kolejność retencja → agrotechnika → nawadnianie (SPEC 6.5). */
export function WhatToDo({
  analysis,
  onShowOnMap,
}: {
  analysis?: AnalysisResponse | null
  /** podświetla miejsce rekomendacji na mapie */
  onShowOnMap?: (g: GeoJSON.Geometry) => void
}) {
  const { t } = useLang()
  if (analysis?.recommendations.length) {
    // backend wskazuje, co pokazać w panelu (`in_panel`, po jednej z kategorii); bez flag – wg priorytetu
    const all = analysis.recommendations
    const flagged = all.filter((r) => r.in_panel)
    const recs = [...(flagged.length ? flagged : all)]
      .sort(
        (a, b) => ORDER.indexOf(a.category) - ORDER.indexOf(b.category) || (b.priority ?? 0) - (a.priority ?? 0),
      )
      .slice(0, 3) // panel: maks. 3 (SPEC 6.5); pełna lista w paszporcie
    return (
      <div className="space-y-3">
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
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <RecommendationCard
        noData
        category="retencja"
        title="Brak danych – analiza w budowie"
        text="Np. gdzie zatrzymać wodę spływającą z pola."
        why={
          <>
            {t(
              'Te rekomendacje policzymy z ukształtowania terenu (NMT GUGiK), rowów i zbiorników w okolicy (BDOT10k) oraz bilansu wody. Dziś te dane nie są jeszcze analizowane, więc niczego nie zalecamy.',
            )}
          </>
        }
      />
      <RecommendationCard
        noData
        category="agrotechnika"
        title="Brak danych – analiza w budowie"
        text="Np. zabiegi, które pomagają glebie trzymać wodę."
        why={t('Policzymy je z kategorii gleby (IUNG), wybranej uprawy i bilansu wody z ostatnich 10 lat.')}
      />
      <RecommendationCard
        noData
        category="nawadnianie"
        title="Brak danych – analiza w budowie"
        text="Czy i kiedy nawadniać – po analizie wody w glebie."
        why={t('Termin i dawkę policzymy z modelu wody w glebie i prognozy pogody na 16 dni.')}
      />
    </div>
  )
}
