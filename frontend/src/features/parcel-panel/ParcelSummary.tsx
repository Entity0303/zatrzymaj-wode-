import { BookOpenText, ChevronDown, Leaf, Loader2, X } from 'lucide-react'
import type { Parcel } from '@/api/types'
import { ErrorNotice } from '@/components/ErrorNotice'
import { useLang } from '@/lib/i18n'
import { FieldOverview, type RefineProps } from './FieldOverview'
import { useParcelTitle } from './parcelTitle'
import type { AnalysisRun } from './types'

/**
 * Zwinięty panel działki (komputer) – domyślny widok po wybraniu działki. Mało naraz (uwagi z testów):
 * werdykt, „teraz”, 3 najlepsze uprawy, „Doprecyzuj”; „Pełny raport” (paszport) i „Szczegóły” na życzenie.
 */
export function ParcelSummary({
  parcel,
  refine,
  run,
  onRetryAnalysis,
  onExpand,
  onClose,
  onOpenPassport,
}: {
  parcel: Parcel
  refine: RefineProps
  run: AnalysisRun
  onRetryAnalysis?: () => void
  onExpand: () => void
  /** zamyka działkę – powrót do przeglądania mapy */
  onClose?: () => void
  onOpenPassport?: () => void
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
          <h2 className="font-display truncate text-2xl leading-8 font-semibold">{title}</h2>
          <p className="truncate text-sm leading-5 text-text-muted">{sub}</p>
        </div>
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

      {run.phase === 'loading' && (
        <div className="space-y-2 rounded-xl bg-surface-2/60 p-3.5">
          <p className="flex items-center gap-2 text-sm font-medium">
            <Loader2 className="size-4 animate-spin text-brand" aria-hidden />
            {t('Sprawdzam działkę: gleba, pogoda z 10 lat, teren…')}
          </p>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
            <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${(done / Math.max(1, steps.length)) * 100}%` }} />
          </div>
        </div>
      )}

      {run.phase === 'error' && <ErrorNotice {...run.error} onRetry={run.error.retryable ? onRetryAnalysis : undefined} />}

      {analysis && <FieldOverview analysis={analysis} refine={refine} />}

      <div className="flex gap-2">
        {analysis && onOpenPassport && (
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
