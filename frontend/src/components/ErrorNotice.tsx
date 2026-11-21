import { RotateCcw, TriangleAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** Błąd po polsku: co nie zadziałało, co działa dalej, „Spróbuj ponownie” (SPEC 14). */
export function ErrorNotice({
  title,
  message,
  stillWorks,
  onRetry,
  compact,
  className,
}: {
  title: string
  message: string
  stillWorks?: string
  onRetry?: () => void
  compact?: boolean
  className?: string
}) {
  return (
    <div role="alert" className={cn('rounded-xl border border-danger/25 bg-danger-soft p-3.5 text-sm leading-5', className)}>
      <div className="flex gap-2.5">
        <TriangleAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0">
          <p className="font-semibold text-text">{title}</p>
          <p className="text-text">{message}</p>
          {stillWorks && !compact && <p className="mt-1 text-text-muted">{stillWorks}</p>}
        </div>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-2.5 ml-7.5 h-11 rounded-md bg-surface px-3">
          <RotateCcw className="size-4" /> Spróbuj ponownie
        </Button>
      )}
    </div>
  )
}
