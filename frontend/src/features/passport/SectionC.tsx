import type { AnalysisResponse } from '@/api/types'

/** C. Dlaczego? (SPEC 7.C): czynniki z paskami udziału, od największego, każdy z liczbą. */
export function SectionC({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <section aria-labelledby="pass-c" className="space-y-3">
      <h3 id="pass-c" className="text-lg leading-6 font-semibold">
        Dlaczego?
      </h3>
      <ul className="space-y-2">
        {analysis.causes.map((c) => (
          <li key={c.factor + c.title}>
            <div className="flex justify-between text-sm font-medium">
              <span>{c.title}</span>
              <span className="tabular">{Math.round(c.share * 100)}%</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-risk" style={{ width: `${c.share * 100}%` }} />
            </div>
            <p className="mt-0.5 text-sm text-text-muted">{c.description}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
