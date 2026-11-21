import { Check, CircleDashed, Loader2, X } from 'lucide-react'
import { cn } from '@/lib/utils'

import type { StepState } from '@/api/types'
import { useLang } from '@/lib/i18n'

export type { StepState }
export type Step = { label: string; state: StepState; note?: string }

/** Lista kroków analizy z ✓ / ⏳ / ✕ (SPEC 14, 15.1). */
export function LoadingSteps({ steps, className }: { steps: Step[]; className?: string }) {
  const { t } = useLang()
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
            {s.state === 'done' && <Check className="size-3.5" aria-label={t('gotowe')} />}
            {s.state === 'active' && <Loader2 className="size-4 animate-spin" aria-label={t('w toku')} />}
            {s.state === 'error' && <X className="size-3.5" aria-label={t('błąd')} />}
            {s.state === 'pending' && <CircleDashed className="size-4" aria-label={t('oczekuje')} />}
          </span>
          <span className={cn('min-w-0', s.state === 'pending' && 'text-text-muted')}>
            {t(s.label)}
            {s.note && <span className="block text-xs leading-4 text-text-muted">{t(s.note)}</span>}
          </span>
        </li>
      ))}
    </ol>
  )
}
