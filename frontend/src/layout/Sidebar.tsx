import { LogoMark } from '@/components/LogoMark'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { goTo, usePage } from '@/lib/router'
import { SECTIONS } from './sections'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { useLang } from '@/lib/i18n'

/** Lewy pasek: 96 px z podpisami (≥ 1280 px), 64 px same ikony (tablet). SPEC 4.1, 12. */
export function Sidebar({ onHome }: { /** logo / „Start” na ekranie Start – powrót do karty powitalnej */ onHome?: () => void } = {}) {
  const { t } = useLang()
  const page = usePage()
  return (
    <nav
      aria-label={t('Nawigacja główna')}
      className="relative z-[1200] hidden h-full w-16 shrink-0 flex-col items-center border-r bg-surface py-4 md:flex xl:w-[104px]"
    >
      <button
        type="button"
        onClick={() => (onHome && page === 'start' ? onHome() : goTo('start'))}
        className="mb-5 flex flex-col items-center gap-1.5 rounded-xl px-1 py-1 text-center hover:bg-surface-2"
        title={`${BRAND_NAME} – ${t(BRAND_TAGLINE)}`}
        aria-label={t('{name} – strona startowa', { name: BRAND_NAME })}
      >
        <LogoMark className="size-10 xl:size-11" />
        <span className="font-display hidden text-base leading-5 font-bold text-brand xl:block">{BRAND_NAME}</span>
      </button>
      <ul className="flex w-full flex-col gap-1.5 px-1.5 xl:px-2">
        {SECTIONS.map((s) => {
          const active = s.key === page
          const Icon = s.icon
          const btn = (
            <button
              type="button"
              aria-current={active ? 'page' : undefined}
              aria-disabled={!s.ready || undefined}
              aria-label={s.ready ? t(s.label) : t('{label} – niedostępne', { label: t(s.label) })}
              onClick={() => (s.key === 'start' && page === 'start' && onHome ? onHome() : goTo(s.key))}
              className={cn(
                'relative flex min-h-14 w-full flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-sm leading-4 font-medium transition-colors',
                active ? 'bg-sage-soft text-brand' : 'text-text-muted hover:bg-surface-2',
                !s.ready && 'cursor-not-allowed opacity-60 hover:bg-transparent',
              )}
            >
              {active && <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-r-full bg-amber" aria-hidden />}
              <Icon className="size-6" aria-hidden />
              <span className="hidden text-center xl:block">{t(s.label)}</span>
            </button>
          )
          return (
            <li key={s.key}>
              <Tooltip>
                <TooltipTrigger asChild>{btn}</TooltipTrigger>
                <TooltipContent side="right">
                  {s.ready ? t(s.label) : t('{label} – niedostępne', { label: t(s.label) })}
                </TooltipContent>
              </Tooltip>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
