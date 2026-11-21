import type { AnalysisResponse } from '@/api/types'
import { useLang } from '@/lib/i18n'

/** C. Dlaczego? (SPEC 7.C): czynniki z paskami udziału, od największego, każdy z liczbą. */
export function SectionC({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  return (
    <section aria-labelledby="pass-c" className="space-y-3">
      <h3 id="pass-c" className="text-lg leading-6 font-semibold">
        {t('Dlaczego?')}
      </h3>
      <ul className="space-y-2">
        {analysis.causes.map((c) => (
          <li key={c.factor + c.title}>
            <div className="flex justify-between text-sm font-medium">
              <span>{t(c.title)}</span>
              <span className="tabular">{Math.round(c.share * 100)}%</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-risk" style={{ width: `${c.share * 100}%` }} />
            </div>
            <p className="mt-0.5 text-sm text-text-muted">{t(c.description)}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
