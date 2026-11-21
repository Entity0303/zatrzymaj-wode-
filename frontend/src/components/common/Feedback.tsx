import { RotateCcw, TriangleAlert, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** Pusty stan: ilustracja + tytuł + instrukcja + akcja (SPEC 14). */
export function EmptyState({
  illustration,
  title,
  description,
  children,
  className,
}: {
  illustration?: ReactNode
  title: string
  description?: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center text-center', className)}>
      {illustration}
      <h3 className="mt-3 text-lg leading-6 font-semibold">{title}</h3>
      {description && <p className="mt-1 text-sm leading-5 text-text-muted">{description}</p>}
      {children && <div className="mt-3 w-full">{children}</div>}
    </div>
  )
}

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

/** Baner „Brak połączenia” (SPEC 15.1). */
export function OfflineBanner() {
  return (
    <div
      role="status"
      className="pointer-events-auto flex items-center gap-2 rounded-full bg-text px-4 py-2 text-sm font-medium text-white shadow-float"
    >
      <WifiOff className="size-4" aria-hidden />
      Brak połączenia – pokazujemy ostatnio zapisane dane
    </div>
  )
}
