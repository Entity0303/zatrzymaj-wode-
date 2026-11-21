import { Check, CircleDashed, Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export type StepState = 'done' | 'active' | 'error' | 'pending'
export type Step = { label: string; state: StepState; note?: string }

/** Lista kroków analizy z ✓ / ⏳ / ✕ (SPEC 14, 15.1). */
export function LoadingSteps({ steps, className }: { steps: Step[]; className?: string }) {
  return (
    <ol className={cn('space-y-1.5', className)} aria-live="polite">
      {steps.map((s) => (
        <li key={s.label} className="flex items-start gap-2.5 text-sm leading-5">
          <span
            className={cn(
              'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full',
              s.state === 'done' && 'bg-ok text-white',
              s.state === 'active' && 'text-brand',
              s.state === 'error' && 'bg-danger text-white',
              s.state === 'pending' && 'text-nodata',
            )}
          >
            {s.state === 'done' && <Check className="size-3.5" aria-label="gotowe" />}
            {s.state === 'active' && <Loader2 className="size-4 animate-spin" aria-label="w toku" />}
            {s.state === 'error' && <X className="size-3.5" aria-label="błąd" />}
            {s.state === 'pending' && <CircleDashed className="size-4" aria-label="oczekuje" />}
          </span>
          <span className={cn('min-w-0', s.state === 'pending' && 'text-text-muted')}>
            {s.label}
            {s.note && <span className="block text-xs leading-4 text-text-muted">{s.note}</span>}
          </span>
        </li>
      ))}
    </ol>
  )
}
