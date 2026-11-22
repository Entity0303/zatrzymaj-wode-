import { BookOpenText, ChevronDown, ChevronUp, Leaf, Loader2, X } from 'lucide-react'
import type { Parcel } from '@/api/types'
import { ErrorNotice } from '@/components/ErrorNotice'
import { useLang } from '@/lib/i18n'
import { ApproxAreaBanner } from './ApproxAreaBanner'
import { FieldOverview, type RefineProps } from './FieldOverview'
import { NonAgriculturalCard } from './NonAgriculturalCard'
import { RiskSummary } from './RiskSummary'
import { useParcelTitle } from './parcelTitle'
import type { AnalysisRun } from './types'

/**
 * Zwinięty panel działki (komputer) – domyślny widok po wybraniu działki. Mało naraz (tryb Rolnik):
 * werdykt, „Co tu posiać?”, 3 działania, „Doprecyzuj”; „Pełny raport” (paszport) i „Szczegóły” na życzenie.
 */
export function ParcelSummary({
  parcel,
  refine,
  run,
  onRetryAnalysis,
  onExpand,
  onClose,
  onCollapse,
  onOpenPassport,
  onShowOnMap,
}: {
  /** zwija panel do samej belki z nazwą */
  onCollapse?: () => void
  parcel: Parcel
  refine: RefineProps
  run: AnalysisRun
  onRetryAnalysis?: () => void
  onExpand: () => void
  /** zamyka działkę – powrót do przeglądania mapy */
  onClose?: () => void
  onOpenPassport?: () => void
  /** „Pokaż na mapie” w działaniach */
  onShowOnMap?: (g: GeoJSON.Geometry) => void
}) {
  const { t } = useLang()
  const analysis = run.phase === 'done' ? run.analysis : null
  const steps = run.phase === 'loading' ? run.steps : []
  const done = steps.filter((x) => x.state === 'done').length
  const { title, sub } = useParcelTitle(parcel)

  return (
    <div className="space-y-4 p-5">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
          <Leaf className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-name line-clamp-2 text-xl leading-7 font-semibold">{title}</h2>
          <p className="text-sm leading-5 text-text-muted">{sub}</p>
        </div>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            aria-label={t('Zwiń panel')}
            title={t('Zwiń panel')}
            className="-mt-1 flex size-10 shrink-0 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
          >
            <ChevronUp className="size-5" />
          </button>
        )}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t('Zamknij działkę i wróć do mapy')}
            className="-mt-1 -mr-2 flex size-10 shrink-0 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
          >
            <X className="size-5" />
          </button>
        )}
      </div>

      {(parcel.source === 'approximate' || analysis?.approximate_area) && <ApproxAreaBanner />}

      {run.phase === 'loading' && (
        <div className="space-y-2 rounded-xl bg-surface-2/60 p-3.5">
          <p className="flex items-center gap-2 text-sm font-medium">
            <Loader2 className="size-4 animate-spin text-brand" aria-hidden />
            {t('Liczę analizę: gleba, pogoda z 10 lat, teren…')}
          </p>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
            <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${(done / Math.max(1, steps.length)) * 100}%` }} />
          </div>
        </div>
      )}

      {run.phase === 'error' && <ErrorNotice {...run.error} onRetry={run.error.retryable ? onRetryAnalysis : undefined} />}

      {analysis?.soil.non_agricultural && <NonAgriculturalCard soil={analysis.soil} onPickOther={onClose} />}
      {analysis && !analysis.soil.non_agricultural && (
        <>
          <RiskSummary analysis={analysis} />
          <FieldOverview analysis={analysis} refine={refine} onShowOnMap={onShowOnMap} />
        </>
      )}

      <div className="flex gap-2">
        {analysis && !analysis.soil.non_agricultural && onOpenPassport && (
          <button
            type="button"
            onClick={onOpenPassport}
            className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-md bg-brand-dark text-sm font-semibold text-white hover:bg-brand"
          >
            <BookOpenText className="size-4" aria-hidden /> {t('Pełny raport')}
          </button>
        )}
        <button
          type="button"
          onClick={onExpand}
          className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-md border bg-surface text-sm font-semibold hover:bg-surface-2"
        >
          {t('Szczegóły')} <ChevronDown className="size-4 text-text-muted" aria-hidden />
        </button>
      </div>
    </div>
  )
}
