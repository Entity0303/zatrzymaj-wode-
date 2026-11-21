import type { Recommendation } from '@/api/types'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'

const CONFIDENCE = { wysoka: 'wysoka', srednia: 'średnia', ograniczona: 'ograniczone dane' } as const

/** Treść „Dlaczego?” rekomendacji: uzasadnienie, dane wejściowe ze źródłem i datą, pewność (SPEC 7.D). */
export function RecommendationWhy({ rec }: { rec: Recommendation }) {
  const { t } = useLang()
  return (
    <>
      <p>{t(rec.why)}</p>
      {rec.inputs.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {rec.inputs.map((e) => (
            <li key={e.name}>
              {t(e.name)}:{' '}
              <b className="tabular">
                {e.value ?? t('brak danych')}
                {e.unit ? ` ${e.unit}` : ''}
              </b>{' '}
              <span className="text-text-muted">
                ({e.source}
                {e.date ? `, ${formatDatePl(e.date)}` : ''})
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-text-muted">
        {t('Pewność')}: {t(CONFIDENCE[rec.confidence])}
      </p>
    </>
  )
}
