import type { AnalysisResponse } from '@/api/types'
import { ScoreRing } from '@/components/ScoreRing'
import { StatusBadge } from '@/components/StatusBadge'
import { useLang } from '@/lib/i18n'

/**
 * A. Stan obecny (SPEC 7.A): wskaźnik w okręgu 0–100, karty wskaźników, zdanie podsumowania.
 * TODO (osoba B): karty woda w glebie (% i mm), kondycja, wilgotność roślin, ryzyko 7 dni, pojemność gleby.
 */
export function SectionA({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const { status } = analysis
  return (
    <section aria-labelledby="pass-a" className="space-y-3">
      <h3 id="pass-a" className="text-lg leading-6 font-semibold">
        {t('Stan obecny')}
      </h3>
      <div className="flex items-center gap-4">
        <ScoreRing value={status.score ?? null} size={96} stroke={9} />
        <div>
          <StatusBadge status={status.level} />
          <p className="mt-1 text-base">{t(status.summary)}</p>
        </div>
      </div>
    </section>
  )
}
