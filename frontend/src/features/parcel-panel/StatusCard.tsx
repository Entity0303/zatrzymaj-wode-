import type { AnalysisResponse, CropId } from '@/api/types'
import { ChevronRight } from 'lucide-react'
import { StatusBadge } from '@/components/StatusBadge'
import { STATUS } from '@/theme/status'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** 3. Karta stanu (SPEC 6.3). */
export function StatusCard({
  crop,
  analysis,
  onOpen,
}: {
  crop: CropId | null
  analysis?: AnalysisResponse | null
  /** › przewija do paszportu wodnego (SPEC 6.3) */
  onOpen?: () => void
}) {
  const { t } = useLang()
  if (analysis) return <AnalysisStatusCard analysis={analysis} onOpen={onOpen} />
  const s = STATUS.no_data
  const Icon = s.icon
  return (
    <div className={cn('flex gap-3.5 rounded-xl border border-nodata/50 p-4', s.bg)}>
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-surface text-text-muted">
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-display text-xl leading-7 font-semibold">{t('Brak danych – analiza w budowie')}</p>
        </div>
        <p className="mt-0.5 text-sm leading-5 text-text-muted">
          {t(
            crop
              ? 'Ocena sytuacji wodnej (pogoda z 10 lat, gleba, teren, zdjęcia satelitarne) nie jest jeszcze liczona.'
              : 'Wybierz uprawę – od niej zależy ocena. Sama ocena sytuacji wodnej nie jest jeszcze liczona.',
          )}
        </p>
        <StatusBadge status="no_data" size="sm" className="mt-2" />
      </div>
    </div>
  )
}

/** Karta stanu z wyniku analizy: tło w kolorze statusu „-soft”, nagłówek i jedno zdanie. */
function AnalysisStatusCard({ analysis, onOpen }: { analysis: AnalysisResponse; onOpen?: () => void }) {
  const { t } = useLang()
  const { level, headline, summary } = analysis.status
  const s = STATUS[level]
  const Icon = s.icon
  return (
    <div className={cn('flex items-start gap-3.5 rounded-xl p-4', level === 'no_data' && 'border border-nodata/50', s.bg)}>
      <span className={cn('flex size-11 shrink-0 items-center justify-center rounded-full bg-surface', s.fg)}>
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-display text-xl leading-7 font-semibold">{t(headline)}</p>
        <p className="mt-0.5 text-sm leading-5 text-text">{t(summary)}</p>
        <StatusBadge status={level} size="sm" className="mt-2" />
      </div>
      {/* › prowadzi do paszportu wodnego (SPEC 6.3) */}
      {onOpen ? (
        <button
          type="button"
          onClick={onOpen}
          aria-label={t('Zobacz pełny paszport wodny')}
          className="-mt-1 -mr-2 flex size-11 shrink-0 items-center justify-center rounded-full text-text-muted hover:bg-surface/70"
        >
          <ChevronRight className="size-5" aria-hidden />
        </button>
      ) : (
        <ChevronRight className="mt-2.5 size-5 shrink-0 text-text-muted" aria-hidden />
      )}
    </div>
  )
}
