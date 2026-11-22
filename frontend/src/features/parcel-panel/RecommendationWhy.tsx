import type { Recommendation } from '@/api/types'
import { formatDatePl, formatNum } from '@/lib/format'
import { useLang } from '@/lib/i18n'

const CONFIDENCE = { wysoka: 'wysoka', srednia: 'średnia', ograniczona: 'ograniczone dane' } as const

/**
 * Nazwy danych wejściowych, które backend czasem podaje technicznie (klucz zamiast opisu) – dla rolnika po polsku.
 * Te same podmiany w zdaniu „why” (np. „Dane: stress_ratio: 2,7” → „Dane: dni stresu względem średniej: 2,7”).
 */
const INPUT_LABEL: Record<string, string> = {
  stress_ratio: 'dni stresu względem średniej z 10 lat (razy)',
}

const label = (name: string) => INPUT_LABEL[name] ?? name
const cleanWhy = (s: string) => Object.entries(INPUT_LABEL).reduce((acc, [k, v]) => acc.replaceAll(k, v), s)

/** Liczba po polsku: przecinek dziesiętny, całe – bez części ułamkowej, małe – do 2 miejsc. */
function value(v: number | string | null | undefined): string | null {
  if (v == null) return null
  if (typeof v !== 'number') return String(v)
  if (Number.isInteger(v)) return formatNum(v, 0)
  return formatNum(v, Math.abs(v) < 10 ? 1 : 0)
}

/** Treść „Dlaczego?” rekomendacji: uzasadnienie, dane wejściowe ze źródłem i datą, pewność (SPEC 7.D). */
export function RecommendationWhy({ rec }: { rec: Recommendation }) {
  const { t } = useLang()
  return (
    <>
      <p>{cleanWhy(t(rec.why))}</p>
      {rec.inputs.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {rec.inputs.map((e) => (
            <li key={e.name}>
              {t(label(e.name))}:{' '}
              <b className="tabular">
                {value(e.value) ?? t('brak danych')}
                {e.unit ? ` ${e.unit}` : ''}
              </b>{' '}
              <span className="text-text-muted">
                ({t(e.source)}
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
