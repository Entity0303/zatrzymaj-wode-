import type { AnalysisResponse } from '@/api/types'
import { cropLabel } from '@/lib/crops'
import { formatDatePl } from '@/lib/format'
import { SectionA } from './SectionA'
import { SectionB } from './SectionB'
import { SectionC } from './SectionC'
import { SectionD } from './SectionD'
import { SectionE } from './SectionE'

/**
 * Paszport wodny (SPEC 7) – SZKIELET, jeszcze niepodpięty w UI.
 * TODO (osoba B): komputer – panel 640 px zamiast prawego panelu (zakładki A–E), telefon – pełna szuflada;
 * przyciski „Pobierz PDF”, „Drukuj”, „Udostępnij link”.
 */
export function Passport({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <article className="space-y-6">
      <header>
        <h2 className="text-[22px] leading-7 font-semibold">
          Paszport wodny · Działka {analysis.parcel.numer} · {cropLabel(analysis.crop)} · stan na{' '}
          {formatDatePl(analysis.analysis_date)}
        </h2>
        {analysis.historical && <p className="text-sm text-text-muted">Analiza historyczna</p>}
      </header>
      <SectionA analysis={analysis} />
      <SectionB analysis={analysis} />
      <SectionC analysis={analysis} />
      <SectionD analysis={analysis} />
      <SectionE analysis={analysis} />
    </article>
  )
}
