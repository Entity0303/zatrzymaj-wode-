import { cn } from '@/lib/utils'
import { goTo, usePage } from '@/lib/router'
import { SECTIONS } from './sections'
import { useLang } from '@/lib/i18n'

/** Dolny pasek zakładek na telefonie (SPEC 12). */
export function BottomTabs() {
  const { t } = useLang()
  const page = usePage()
  return (
    <nav aria-label={t('Nawigacja główna')} className="relative z-[1300] flex h-16 shrink-0 border-t bg-surface md:hidden">
      {SECTIONS.map((s) => {
        const active = s.key === page
        const Icon = s.icon
        return (
          <button
            key={s.key}
            type="button"
            aria-current={active ? 'page' : undefined}
            onClick={() => goTo(s.key)}
            aria-disabled={!s.ready || undefined}
            aria-label={s.ready ? t(s.short) : t('{label} – wkrótce', { label: t(s.label) })}
            className={cn(
              'flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 text-xs font-medium',
              active ? 'text-brand' : 'text-text-muted',
              !s.ready && 'opacity-60',
            )}
          >
            <span className={cn('flex h-7 w-12 items-center justify-center rounded-full', active && 'bg-ok-soft')}>
              <Icon className="size-6" aria-hidden />
            </span>
            {t(s.short)}
          </button>
        )
      })}
    </nav>
  )
}
