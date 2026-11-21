import { BookOpenText, ChevronDown, Leaf, Loader2 } from 'lucide-react'
import type { CropId, Parcel } from '@/api/types'
import { ErrorNotice } from '@/components/ErrorNotice'
import { ScoreRing } from '@/components/ScoreRing'
import { StatusBadge } from '@/components/StatusBadge'
import { formatHa } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { STATUS } from '@/theme/status'
import { CropField } from './CropField'
import type { AnalysisRun } from './types'

/**
 * Zwinięty panel działki (komputer): tylko to, co najważniejsze – działka, uprawa, stan jednym zdaniem,
 * „Pełny panel” i „Paszport wodny”. Mniej rzeczy naraz na ekranie; całość jednym klikiem.
 */
export function ParcelSummary({
  parcel,
  crop,
  onCropChange,
  run,
  onRetryAnalysis,
  onExpand,
  onOpenPassport,
}: {
  parcel: Parcel
  crop: CropId | null
  onCropChange: (c: CropId) => void
  run: AnalysisRun
  onRetryAnalysis?: () => void
  onExpand: () => void
  onOpenPassport?: () => void
}) {
  const { t } = useLang()
  const analysis = run.phase === 'done' ? run.analysis : null
  const level = analysis?.status.level ?? 'no_data'
  const s = STATUS[level]
  const steps = run.phase === 'loading' ? run.steps : []
  const done = steps.filter((x) => x.state === 'done').length

  return (
    <div className="space-y-4 p-5">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
          <Leaf className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display truncate text-2xl leading-8 font-semibold">{t('Działka {numer}', { numer: parcel.numer })}</h2>
          <p className="truncate text-sm leading-5 text-text-muted">
            {t('gm. {gmina}, obręb {obreb}', { gmina: parcel.gmina, obreb: parcel.obreb })} · {formatHa(parcel.powierzchnia_ha)} ha
          </p>
        </div>
      </div>

      <CropField crop={crop} onChange={onCropChange} />

      {run.phase === 'loading' && (
        <div className="space-y-2 rounded-xl bg-surface-2/60 p-3.5">
          <p className="flex items-center gap-2 text-sm font-medium">
            <Loader2 className="size-4 animate-spin text-brand" aria-hidden />
            {t('Liczę ocenę wody dla działki…')}
          </p>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
            <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${(done / Math.max(1, steps.length)) * 100}%` }} />
          </div>
        </div>
      )}

      {run.phase === 'error' && <ErrorNotice {...run.error} onRetry={run.error.retryable ? onRetryAnalysis : undefined} />}

      {analysis && (
        <div className={`flex items-center gap-4 rounded-xl p-4 ${s.bg}`}>
          {analysis.status.score != null && (
            <ScoreRing value={analysis.status.score} size={64} stroke={7} color={s.ring.color} track={s.ring.track} />
          )}
          <div className="min-w-0 flex-1 space-y-1">
            <StatusBadge status={level} size="sm" />
            <p className="font-display line-clamp-2 text-lg leading-6 font-semibold">{t(analysis.status.headline)}</p>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onExpand}
          className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-md border bg-surface text-sm font-semibold hover:bg-surface-2"
        >
          {t('Pełny panel')} <ChevronDown className="size-4 text-text-muted" aria-hidden />
        </button>
        {analysis && onOpenPassport && (
          <button
            type="button"
            onClick={onOpenPassport}
            className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-md bg-brand-dark text-sm font-semibold text-white hover:bg-brand"
          >
            <BookOpenText className="size-4" aria-hidden /> {t('Paszport wodny')}
          </button>
        )}
      </div>
    </div>
  )
}
