import { ChevronDown, ExternalLink, MapPin, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import type { AnalysisResponse, Recommendation, RecommendationCategory } from '@/api/types'
import { IrrigationCard } from '@/features/parcel-panel/IrrigationCard'
import { RecommendationWhy } from '@/features/parcel-panel/RecommendationWhy'
import { irrigationShown } from '@/lib/crops'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { REC_CATEGORY } from '@/theme/recommendations'
import { PassportSection } from './PassportSection'

const ORDER: RecommendationCategory[] = ['retencja', 'agrotechnika', 'nawadnianie']
/** Paszport: maks. 5 działań (uwagi mentora; panel – 3) – 3 karty w rzędzie, reszta pod spodem. */
const MAX = 5

const PERMIT: Record<Recommendation['permit'], string> = {
  none: 'bez formalności',
  maybe: 'sprawdź formalności',
  required: 'wymaga zgłoszenia',
}

/** Karta działania: kategoria, termin, tytuł, opis, „Dlaczego?”, na dole formalności. */
function ActionCard({ r, first, whenLabel, onShowOnMap }: { r: Recommendation; first: boolean; whenLabel: string; onShowOnMap?: (g: GeoJSON.Geometry) => void }) {
  const { t } = useLang()
  const [why, setWhy] = useState(false)
  const cat = REC_CATEGORY[r.category]
  const Icon = cat.icon
  return (
    <article
      className={cn(
        'flex min-w-0 flex-col rounded-[18px] border bg-surface p-5',
        first ? 'border-pp-brand ring-1 ring-pp-brand/30' : 'border-paper-line',
      )}
    >
      <p className={cn('text-xs leading-4 font-semibold tracking-wide uppercase', first ? 'text-pp-brand' : 'text-text-muted')}>
        {first ? `${t('Najważniejsze')} · ${whenLabel}` : whenLabel}
      </p>
      <div className="mt-2 flex items-start gap-2.5">
        <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', cat.cls)}>
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-xs leading-4 text-text-muted">{t(cat.label)}</p>
          <h4 className="text-base leading-6 font-bold">{t(r.title)}</h4>
        </div>
      </div>
      <p className="mt-2 text-sm leading-5">{t(r.description)}</p>
      {r.warning && (
        <p className="mt-2 flex gap-1.5 rounded-lg bg-warn-soft px-3 py-2 text-sm leading-5">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-[#875a12]" aria-hidden /> {t(r.warning)}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-x-4">
        <button type="button" aria-expanded={why} onClick={() => setWhy((w) => !w)} className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-pp-brand">
          {t('Dlaczego?')} <ChevronDown className={cn('size-4 transition-transform', why && 'rotate-180')} aria-hidden />
        </button>
        {r.location && onShowOnMap && (
          <button type="button" onClick={() => onShowOnMap(r.location!)} className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-pp-brand">
            <MapPin className="size-4" aria-hidden /> {t('Pokaż na mapie')}
          </button>
        )}
      </div>
      {why && (
        <div className="text-sm leading-5 text-text-muted">
          <RecommendationWhy rec={r} />
        </div>
      )}
      {/* formalności na dole karty */}
      <div className="mt-auto border-t border-paper-line pt-3 text-sm leading-5">
        <p>
          <b className={cn('font-semibold', r.permit === 'required' ? 'text-pp-bad' : r.permit === 'maybe' ? 'text-[#875a12]' : 'text-pp-brand')}>
            {t(PERMIT[r.permit])}
          </b>
          {r.permit_note && <span className="text-text-muted"> – {t(r.permit_note)}</span>}
          {r.permit_url && (
            <a href={r.permit_url} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center gap-0.5 font-medium text-pp-brand hover:underline">
              {t('Wody Polskie')} <ExternalLink className="size-3.5" aria-hidden />
            </a>
          )}
        </p>
        {r.eco_scheme && (
          <p className="mt-1 text-text-muted">
            <span className="font-semibold text-text">{t('Ekoschemat:')}</span> {t(r.eco_scheme.name)} – {t(r.eco_scheme.practice)}
            {r.eco_scheme.note && <span className="block text-xs leading-4">{t(r.eco_scheme.note)}</span>}
          </p>
        )}
      </div>
    </article>
  )
}

/**
 * 6. Co mogę zrobić? (F6): kolejność retencja → agrotechnika → nawadnianie (w grupie wg priorytetu), 3 karty obok
 * siebie – pierwsza wyróżniona „Najważniejsze · teraz / w dniu analizy”, pozostałe z etykietą terminu; na dole każdej
 * formalności (bez formalności / sprawdź / wymaga zgłoszenia) i ekoschemat. Kolejne (do 5) – pod spodem. Plan
 * nawadniania – gdy dotyczy tej uprawy.
 */
export function ActionsSection({ analysis, onShowOnMap }: { analysis: AnalysisResponse; onShowOnMap?: (g: GeoJSON.Geometry) => void }) {
  const { t } = useLang()
  const irrigation = irrigationShown(analysis)
  const recs = [...analysis.recommendations]
    .filter((r) => r.category !== 'nawadnianie' || irrigation)
    .sort((a, b) => ORDER.indexOf(a.category) - ORDER.indexOf(b.category) || (b.priority ?? 0) - (a.priority ?? 0))
    .slice(0, MAX)
  // termin: „teraz” przy dacie historycznej = „w dniu analizy (dd.mm.rrrr)”
  const when = (r: Recommendation) =>
    r.when === 'teraz' && analysis.historical ? t('w dniu analizy ({d})', { d: formatDatePl(analysis.analysis_date) }) : t(r.when_label)
  return (
    <PassportSection id="pp-dzialania" title={t('Co mogę zrobić?')}>
      {recs.length === 0 ? (
        <p className="rounded-[18px] border border-paper-line bg-surface px-5 py-4 text-sm text-text-muted">{t('Brak zaleceń dla tej działki i daty.')}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {recs.map((r, i) => (
            <ActionCard key={r.id} r={r} first={i === 0} whenLabel={when(r)} onShowOnMap={onShowOnMap} />
          ))}
        </div>
      )}
      {irrigation && analysis.irrigation && <IrrigationCard plan={analysis.irrigation} />}
    </PassportSection>
  )
}
