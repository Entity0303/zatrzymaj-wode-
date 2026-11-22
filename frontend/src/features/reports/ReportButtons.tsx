import { BookOpenText, Loader2, type LucideIcon } from 'lucide-react'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { REPORT_KINDS } from './reportKinds'
import type { ReportType } from './useReportDownload'

/** Jeden duży przycisk: ikona po lewej, tytuł pogrubiony, opis mniejszy szary; wysokość ok. 60 px. */
function BigButton({
  icon: Icon,
  title,
  description,
  primary,
  busy,
  disabled,
  onClick,
}: {
  icon: LucideIcon
  title: string
  description: string
  primary?: boolean
  busy?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-busy={busy || undefined}
      className={cn(
        'flex min-h-[60px] w-full items-center gap-3 rounded-lg px-3.5 py-2 text-left transition-colors disabled:opacity-60',
        primary ? 'bg-brand-dark text-white hover:bg-brand' : 'border border-brand/50 bg-surface text-brand-dark hover:bg-sage-soft',
      )}
    >
      {busy ? <Loader2 className="size-6 shrink-0 animate-spin" aria-hidden /> : <Icon className={cn('size-6 shrink-0', !primary && 'text-brand')} aria-hidden />}
      <span className="min-w-0 flex-1">
        <span className="block text-base leading-5 font-semibold">{title}</span>
        <span className={cn('block text-sm leading-5', primary ? 'text-white/85' : 'text-text-muted')}>{description}</span>
      </span>
    </button>
  )
}

/**
 * F25: przyciski raportów – pełnej szerokości, jeden pod drugim: raport skrócony (główny), raport pełny, opcjonalnie
 * „Otwórz paszport wodny”. Stan „Generuję raport…” tylko na klikniętym przycisku; drugi rodzaj czeka (jedno
 * generowanie naraz), paszport zostaje aktywny.
 */
export function ReportButtons({
  onDownload,
  busyType,
  onOpenPassport,
}: {
  onDownload?: (type: ReportType) => void
  busyType?: ReportType | null
  onOpenPassport?: () => void
}) {
  const { t } = useLang()
  return (
    <div className="grid gap-2">
      {onDownload &&
        REPORT_KINDS.map((k) => {
          const busy = busyType === k.type
          return (
            <BigButton
              key={k.type}
              icon={k.icon}
              primary={k.type === 'short'}
              busy={busy}
              disabled={busyType != null}
              title={t(busy ? 'Generuję raport… (do ok. 30 s)' : k.title)}
              description={t(k.description)}
              onClick={() => onDownload(k.type)}
            />
          )
        })}
      {onOpenPassport && (
        <BigButton icon={BookOpenText} title={t('Otwórz paszport wodny')} description={t('Pełna analiza działki na ekranie')} onClick={onOpenPassport} />
      )}
    </div>
  )
}
