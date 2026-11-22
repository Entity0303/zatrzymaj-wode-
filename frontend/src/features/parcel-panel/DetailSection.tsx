import { ChevronDown, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * Zwijana sekcja szczegółów analizy w panelu działki (F-MASTER A4): przyczyny, gleba, teren, ranking, działania,
 * źródła. Stan rozwinięcia lokalny – przeliczanie (F13) nie odmontowuje sekcji, więc zostaje.
 */
export function DetailSection({
  title,
  hint,
  icon: Icon,
  defaultOpen = false,
  children,
}: {
  title: string
  /** jedno zdanie pod tytułem (co jest w środku) */
  hint?: string
  icon: LucideIcon
  defaultOpen?: boolean
  children: ReactNode
}) {
  const { t } = useLang()
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="rounded-xl border bg-surface">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="flex min-h-12 w-full items-center gap-2.5 px-4 py-2.5 text-left">
        <Icon className="size-5 shrink-0 text-brand" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block text-base leading-6 font-semibold">{t(title)}</span>
          {hint && !open && <span className="block truncate text-sm leading-5 text-text-muted">{t(hint)}</span>}
        </span>
        <ChevronDown className={cn('size-5 shrink-0 text-text-muted transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open && <div className="space-y-3 border-t p-3">{children}</div>}
    </section>
  )
}
