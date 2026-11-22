import type { VerdictLevel } from '@/api/types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { LONG_TERM_LABEL, NOW_LABEL, STATUS, type Status } from '@/theme/status'

/** Kolor kropki ryzyka na lata – ten sam co pasek karty ryzyka w panelu. */
const LONG_TERM_DOT: Record<VerdictLevel, string> = { ok: 'bg-ok', warn: 'bg-amber', bad: 'bg-danger' }

/**
 * Stan działki w dwóch równych wierszach (F9/F10) – wspólny dla dymka na mapie (ParcelLabel) i panelu (RiskSummary):
 * „Teraz: woda w normie” (ikona stanu) / „Na dłuższą metę: wysokie ryzyko suszy” (kropka koloru ryzyka).
 * Bez separatora-kropki; `no_data` / brak werdyktu – wiersz pominięty.
 */
export function StatusRows({
  now,
  longTerm,
  size = 'sm',
  className,
}: {
  now: Status | null
  longTerm: VerdictLevel | null | undefined
  /** xs – dymek na mapie, sm – panel */
  size?: 'xs' | 'sm'
  className?: string
}) {
  const { t } = useLang()
  const showNow = !!now && now !== 'no_data'
  if (!showNow && !longTerm) return null
  const Icon = showNow ? STATUS[now].icon : null
  const xs = size === 'xs'
  const slot = cn('flex shrink-0 items-center justify-center', xs ? 'h-4 w-3.5' : 'h-5 w-4')
  const label = xs ? 'text-text-muted' : 'font-semibold'
  return (
    <span className={cn('flex flex-col', xs ? 'gap-0.5 text-xs leading-4 font-medium' : 'gap-1 text-sm leading-5 text-text', className)}>
      {showNow && Icon && (
        <span className="flex items-start gap-1.5">
          <span className={slot}>
            <Icon className={cn(xs ? 'size-3.5' : 'size-4', STATUS[now].fg)} aria-hidden />
          </span>
          <span>
            <span className={label}>{t('Teraz:')}</span> {t(NOW_LABEL[now])}
          </span>
        </span>
      )}
      {longTerm && (
        <span className="flex items-start gap-1.5">
          <span className={slot}>
            <span className={cn('rounded-full', xs ? 'size-2.5' : 'size-2.5', LONG_TERM_DOT[longTerm])} aria-hidden />
          </span>
          <span>
            <span className={label}>{t('Na dłuższą metę:')}</span> {t(LONG_TERM_LABEL[longTerm])}
          </span>
        </span>
      )}
    </span>
  )
}
