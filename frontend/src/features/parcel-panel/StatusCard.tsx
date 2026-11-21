import type { AnalysisResponse, CropId } from '@/api/types'
import { StatusBadge } from '@/components/StatusBadge'
import { STATUS } from '@/theme/status'
import { cn } from '@/lib/utils'

/** 3. Karta stanu (SPEC 6.3). */
export function StatusCard({ crop, analysis }: { crop: CropId | null; analysis?: AnalysisResponse | null }) {
  if (analysis) return <AnalysisStatusCard analysis={analysis} />
  const s = STATUS.no_data
  const Icon = s.icon
  return (
    <div className={cn('flex gap-3 rounded-xl border border-nodata/50 p-4', s.bg)}>
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface text-text-muted">
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-base leading-6 font-semibold">Brak danych – analiza w budowie</p>
        </div>
        <p className="mt-0.5 text-sm leading-5 text-text-muted">
          {crop
            ? 'Ocena sytuacji wodnej (pogoda z 10 lat, gleba, teren, zdjęcia satelitarne) nie jest jeszcze liczona.'
            : 'Wybierz uprawę – od niej zależy ocena. Sama ocena sytuacji wodnej nie jest jeszcze liczona.'}
        </p>
        <StatusBadge status="no_data" size="sm" className="mt-2" />
      </div>
    </div>
  )
}

/** Karta stanu z wyniku analizy: tło w kolorze statusu „-soft”, nagłówek i jedno zdanie. */
function AnalysisStatusCard({ analysis }: { analysis: AnalysisResponse }) {
  const { level, headline, summary } = analysis.status
  const s = STATUS[level]
  const Icon = s.icon
  return (
    <div className={cn('flex gap-3 rounded-xl border p-4', level === 'no_data' && 'border-nodata/50', s.bg)}>
      <span className={cn('flex size-10 shrink-0 items-center justify-center rounded-full bg-surface', s.fg)}>
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-base leading-6 font-semibold">{headline}</p>
        <p className="mt-0.5 text-sm leading-5 text-text">{summary}</p>
        <StatusBadge status={level} size="sm" className="mt-2" />
      </div>
    </div>
  )
}
