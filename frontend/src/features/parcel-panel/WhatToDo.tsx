import type { AnalysisResponse, RecommendationCategory } from '@/api/types'
import { RecommendationCard } from '@/components/RecommendationCard'
import { formatDatePl } from '@/lib/format'

const ORDER: RecommendationCategory[] = ['retencja', 'agrotechnika', 'nawadnianie']
const CONFIDENCE = { wysoka: 'wysoka', srednia: 'średnia', ograniczona: 'ograniczone dane' } as const

/** 5. „Co zrobić?” – kolejność retencja → agrotechnika → nawadnianie (SPEC 6.5). */
export function WhatToDo({ analysis }: { analysis?: AnalysisResponse | null }) {
  if (analysis?.recommendations.length) {
    const recs = [...analysis.recommendations]
      .sort((a, b) => ORDER.indexOf(a.category) - ORDER.indexOf(b.category))
      .slice(0, 3) // panel: maks. 3 (SPEC 6.5); pełna lista w paszporcie
    return (
      <div className="space-y-3">
        {recs.map((r) => (
          <RecommendationCard
            key={r.id}
            category={r.category}
            title={r.title}
            text={r.description}
            why={
              <>
                <p>{r.why}</p>
                {r.inputs.length > 0 && (
                  <ul className="mt-2 space-y-0.5">
                    {r.inputs.map((e) => (
                      <li key={e.name}>
                        {e.name}: <b className="tabular">{e.value ?? 'brak danych'}{e.unit ? ` ${e.unit}` : ''}</b>{' '}
                        <span className="text-text-muted">
                          ({e.source}
                          {e.date ? `, ${formatDatePl(e.date)}` : ''})
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 text-text-muted">Pewność: {CONFIDENCE[r.confidence]}</p>
              </>
            }
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
            Te rekomendacje policzymy z ukształtowania terenu (NMT GUGiK), rowów i zbiorników w okolicy (BDOT10k)
            oraz bilansu wody. Dziś te dane nie są jeszcze analizowane, więc niczego nie zalecamy.
          </>
        }
      />
      <RecommendationCard
        noData
        category="agrotechnika"
        title="Brak danych – analiza w budowie"
        text="Np. zabiegi, które pomagają glebie trzymać wodę."
        why={<>Policzymy je z kategorii gleby (IUNG), wybranej uprawy i bilansu wody z ostatnich 10 lat.</>}
      />
      <RecommendationCard
        noData
        category="nawadnianie"
        title="Brak danych – analiza w budowie"
        text="Czy i kiedy nawadniać – po analizie wody w glebie."
        why={<>Termin i dawkę policzymy z modelu wody w glebie i prognozy pogody na 16 dni.</>}
      />
    </div>
  )
}
