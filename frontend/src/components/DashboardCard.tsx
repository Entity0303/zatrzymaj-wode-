import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** Karta dolnego paska (SPEC 4.5): ikona, tytuł, treść. */
export function DashboardCard({
  icon: Icon,
  title,
  children,
  className,
  aside,
}: {
  icon: LucideIcon
  title: string
  children: ReactNode
  className?: string
  aside?: ReactNode
}) {
  const { t } = useLang()
  return (
    <section
      aria-label={t(title)}
      className={cn('flex h-full min-w-0 flex-col rounded-xl border bg-surface px-4 py-3 shadow-card', className)}
    >
      <header className="mb-1.5 flex items-center gap-2">
        <Icon className="size-5 text-brand" aria-hidden />
        <h3 className="text-sm leading-5 font-semibold">{t(title)}</h3>
        {aside && <span className="ml-auto">{aside}</span>}
      </header>
      {children}
    </section>
  )
}
