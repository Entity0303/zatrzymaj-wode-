import { Droplet } from 'lucide-react'
import { FieldIllustration } from '@/components/FieldIllustration'
import { LogoMark } from '@/components/LogoMark'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { ACTIVE, SECTIONS } from './sections'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { useLang } from '@/lib/i18n'

/** Lewy pasek: 96 px z podpisami (≥ 1280 px), 64 px same ikony (tablet). SPEC 4.1, 12. */
export function Sidebar() {
  const { t } = useLang()
  return (
    <nav
      aria-label={t('Nawigacja główna')}
      className="relative z-[1200] hidden h-full w-16 shrink-0 flex-col items-center border-r bg-surface py-4 md:flex xl:w-24"
    >
      <div
        className="mb-5 flex flex-col items-center gap-1.5 px-1 text-center"
        title={`${BRAND_NAME} – ${t(BRAND_TAGLINE)}`}
        aria-label={`${BRAND_NAME} – ${t(BRAND_TAGLINE)}`}
        role="img"
      >
        <LogoMark className="size-10 xl:size-11" />
        <span className="hidden text-sm leading-4 font-bold tracking-tight text-brand xl:block">{BRAND_NAME}</span>
      </div>
      <ul className="flex w-full flex-col gap-1.5 px-1.5 xl:px-2">
        {SECTIONS.map((s) => {
          const active = s.key === ACTIVE
          const Icon = s.icon
          const btn = (
            <button
              type="button"
              aria-current={active ? 'page' : undefined}
              aria-disabled={!s.ready || undefined}
              aria-label={s.ready ? t(s.label) : t('{label} – wkrótce', { label: t(s.label) })}
              onClick={(e) => !s.ready && e.preventDefault()}
              className={cn(
                'relative flex min-h-14 w-full flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-sm leading-4 font-medium transition-colors',
                active ? 'bg-ok-soft text-brand' : 'text-text-muted hover:bg-surface-2',
                !s.ready && 'cursor-not-allowed opacity-60 hover:bg-transparent',
              )}
            >
              {active && <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-r-full bg-brand" aria-hidden />}
              <Icon className="size-6" aria-hidden />
              <span className="hidden text-center xl:block">{t(s.label)}</span>
            </button>
          )
          return (
            <li key={s.key}>
              <Tooltip>
                <TooltipTrigger asChild>{btn}</TooltipTrigger>
                <TooltipContent side="right">
                  {s.ready ? t(s.label) : t('{label} – wkrótce', { label: t(s.label) })}
                </TooltipContent>
              </Tooltip>
            </li>
          )
        })}
      </ul>
      <div className="mt-auto hidden w-full px-2 xl:block">
        {/* karta z hasłem: kropla, hasło, pod spodem ilustracja pola (ref-desktop) */}
        <div className="overflow-hidden rounded-xl bg-ok-soft text-center">
          <Droplet className="mx-auto mt-3 size-5 fill-water/20 text-water" aria-hidden />
          <p className="mt-1 px-1.5 text-sm leading-[18px] font-semibold text-brand-dark">{t('Oszczędzaj wodę. Chroń plony.')}</p>
          <FieldIllustration className="mt-2 w-full" />
        </div>
      </div>
    </nav>
  )
}
