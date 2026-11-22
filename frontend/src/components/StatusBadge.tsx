import { STATUS, type Status } from '@/theme/status'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** Odznaka stanu: kolor + ikona + tekst – nigdy sam kolor (SPEC 14, 16). */
export function StatusBadge({
  status,
  label,
  size = 'md',
  now,
  className,
}: {
  status: Status
  label?: string
  /** stan wody dziś – „Teraz: dobrze” (werdykt działki mówi o latach, ten status o dzisiejszym dniu) */
  now?: boolean
  size?: 'sm' | 'md'
  className?: string
}) {
  const { t } = useLang()
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
      {now ? `${t('Teraz:')} ${t(label ?? s.label).toLocaleLowerCase()}` : t(label ?? s.label)}
    </span>
  )
}
