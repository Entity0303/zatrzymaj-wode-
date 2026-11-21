import type { AnalysisResponse } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'

/**
 * B. Na tle 10 lat (SPEC 7.B): bilans wody narastająco na tle pasma min–max i średniej,
 * słupki dni stresu w latach, opady miesięczne.
 * TODO (osoba B): wykresy Recharts (TrendChart z SPEC 14) z history.balance_cumulative / balance_band.
 */
export function SectionB({ analysis }: { analysis: AnalysisResponse }) {
  const { history } = analysis
  return (
    <section aria-labelledby="pass-b" className="space-y-3">
      <h3 id="pass-b" className="text-lg leading-6 font-semibold">
        Na tle 10 lat
      </h3>
      {history.summary && <p className="text-base">{history.summary}</p>}
      <ul className="flex flex-wrap gap-2 text-sm">
        {history.stress_days_by_year.map((y) => (
          <li key={y.year} className={y.is_current ? 'font-semibold text-brand' : 'text-text-muted'}>
            {y.year}: {y.stress_days ?? '—'} dni stresu
          </li>
        ))}
      </ul>
      <SourceTag kind={history.source_tag.kind} title={history.source_tag.source ?? undefined} />
    </section>
  )
}
