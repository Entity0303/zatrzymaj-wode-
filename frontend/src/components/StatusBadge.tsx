import { STATUS, type Status } from '@/theme/status'
import { cn } from '@/lib/utils'

/** Odznaka stanu: kolor + ikona + tekst – nigdy sam kolor (SPEC 14, 16). */
export function StatusBadge({
  status,
  label,
  size = 'md',
  className,
}: {
  status: Status
  label?: string
  size?: 'sm' | 'md'
  className?: string
}) {
  const s = STATUS[status]
  const Icon = s.icon
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-full font-medium whitespace-nowrap',
        status === 'no_data' ? 'border border-nodata/60 bg-nodata-soft' : s.bg,
        s.fg,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
        className,
      )}
    >
      <Icon className={size === 'sm' ? 'size-3.5' : 'size-4'} aria-hidden />
      {label ?? s.label}
    </span>
  )
}
