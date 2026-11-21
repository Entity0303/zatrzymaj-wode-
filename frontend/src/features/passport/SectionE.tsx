import type { AnalysisResponse } from '@/api/types'
import { formatDatePl } from '@/lib/format'

const CONFIDENCE = { wysoka: 'Wysoka', srednia: 'Średnia', ograniczona: 'Ograniczone dane' } as const
const AVAIL = { ok: '✓', czesciowo: '⚠ częściowo', brak: '✕ brak' } as const

/**
 * E. Wiarygodność danych (SPEC 7.E): pewność, tabela źródeł, kompletność, ograniczenia.
 * TODO (osoba B): ConfidenceBadge z dymkiem, pasek kompletności.
 */
export function SectionE({ analysis }: { analysis: AnalysisResponse }) {
  const r = analysis.reliability
  return (
    <section aria-labelledby="pass-e" className="space-y-3">
      <h3 id="pass-e" className="text-lg leading-6 font-semibold">
        Wiarygodność danych
      </h3>
      <p className="text-base">
        Pewność: <b>{CONFIDENCE[r.confidence]}</b> – {r.reason}
      </p>
      <p className="text-sm text-text-muted">
        Kompletność: {r.completeness.available} z {r.completeness.total} źródeł
      </p>
      <table className="w-full text-left text-sm">
        <thead className="text-text-muted">
          <tr>
            <th className="py-1 font-medium">Źródło</th>
            <th className="py-1 font-medium">Co wzięto</th>
            <th className="py-1 font-medium">Data</th>
            <th className="py-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {r.sources.map((s) => (
            <tr key={s.name} className="border-t">
              <td className="py-1">{s.name}</td>
              <td className="py-1">{s.used_for}</td>
              <td className="py-1">{s.data_date ? formatDatePl(s.data_date) : '—'}</td>
              <td className="py-1">{AVAIL[s.status]}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="list-disc pl-5 text-sm text-text-muted">
        {r.limitations.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </section>
  )
}
