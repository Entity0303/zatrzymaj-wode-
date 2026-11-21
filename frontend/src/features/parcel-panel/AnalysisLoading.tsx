import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { LoadingSteps, type Step } from '@/components/LoadingSteps'
import { Skeleton } from '@/components/ui/skeleton'
import { cropLabel } from '@/lib/crops'
import { formatDatePl } from '@/lib/format'
import type { CropId } from '@/api/types'
import { KeyMetrics } from './KeyMetrics'
import { SectionTitle } from './SectionTitle'

/** Ekran ładowania analizy w panelu (SPEC 13 krok 4, 15.1): kroki ✓/⏳, licznik sekund, szkielety kart. */
export function AnalysisLoading({
  steps,
  crop,
  asOf,
}: {
  steps: Step[]
  crop: CropId
  asOf: string
}) {
  // licznik od zamontowania – panel nadaje komponentowi `key` przebiegu, więc każde przeliczenie liczy od 0
  const [startedAt] = useState(() => Date.now())
  const [now, setNow] = useState(startedAt)
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(t)
  }, [])
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000))
  const done = steps.filter((s) => s.state === 'done').length
  const pct = Math.round((done / Math.max(1, steps.length)) * 100)

  return (
    <div className="space-y-5" aria-busy>
      <div className="rounded-xl border bg-ok-soft p-4">
        <div className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface text-brand">
            <Loader2 className="size-6 animate-spin" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-base leading-6 font-semibold">Liczę ocenę wody dla działki…</p>
            <p className="text-sm leading-5 text-text-muted">
              {cropLabel(crop)} · {formatDatePl(asOf)} · zwykle do 30 s
            </p>
          </div>
          <span className="tabular ml-auto text-sm font-semibold text-text-muted" aria-label={`${seconds} sekund`}>
            {seconds} s
          </span>
        </div>
        <div
          className="mt-3 h-2 overflow-hidden rounded-full bg-surface"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label="Postęp analizy"
        >
          <div className="h-full rounded-full bg-brand transition-[width] duration-500" style={{ width: `${pct}%` }} />
        </div>
        <LoadingSteps steps={steps} className="mt-3" />
      </div>
      <section className="space-y-3">
        <SectionTitle>Kluczowe wskaźniki</SectionTitle>
        <KeyMetrics loading />
      </section>
      <section className="space-y-3">
        <SectionTitle>Co zrobić?</SectionTitle>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full rounded-xl bg-surface-2" />
        ))}
      </section>
    </div>
  )
}
