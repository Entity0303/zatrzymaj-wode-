import { ChevronDown, Menu, MousePointerClick } from 'lucide-react'
import type { ReactNode } from 'react'
import { LogoMark } from '@/components/LogoMark'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { EXAMPLES, type Example } from '@/features/parcel-panel/examples'
import { BRAND_NAME } from '@/lib/brand'
import { useLang } from '@/lib/i18n'
import { goTo } from '@/lib/router'

/**
 * Tryb przeglądania mapy (jak w mapach internetowych): mały pasek u góry – logo, wyszukiwarka,
 * „Moja lokalizacja”, przykłady i menu – oraz podpowiedź na dole. Reszta interfejsu po kliknięciu pola.
 */
export function ExploreBar({
  isMobile,
  search,
  locate,
  onExample,
}: {
  isMobile: boolean
  search: ReactNode
  locate: ReactNode
  onExample: (e: Example) => void
}) {
  const { t, lang, setLang } = useLang()
  const pill = 'flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface px-4 text-sm font-medium shadow-float hover:bg-sage-soft'
  const menuItem = 'min-h-11 text-sm'

  const examples = (
    <>
      <DropdownMenuLabel className="text-xs tracking-wider text-text-muted uppercase">{t('Zobacz przykład')}</DropdownMenuLabel>
      {EXAMPLES.map((e) => (
        <DropdownMenuItem key={e.id} className={menuItem} onSelect={() => onExample(e)}>
          <span className={`flex size-7 items-center justify-center rounded-full ${e.tone}`}>
            <e.icon className="size-4" />
          </span>
          <span className="min-w-0">
            <span className="block font-medium">{t(e.title)}</span>
            <span className="block text-xs text-text-muted">{t(e.text)}</span>
          </span>
        </DropdownMenuItem>
      ))}
    </>
  )
  const pages = (
    <>
      <DropdownMenuItem className={menuItem} onSelect={() => goTo('parcels')}>
        {t('Moje działki')}
      </DropdownMenuItem>
      <DropdownMenuItem className={menuItem} onSelect={() => goTo('reports')}>
        {t('Raporty')}
      </DropdownMenuItem>
      <DropdownMenuItem className={menuItem} onSelect={() => goTo('settings')}>
        {t('Ustawienia')}
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem className={menuItem} onSelect={() => setLang(lang === 'pl' ? 'en' : 'pl')}>
        {lang === 'pl' ? 'English' : 'Polski'}
      </DropdownMenuItem>
    </>
  )

  return (
    <>
      <div className="pointer-events-none absolute inset-x-3 top-3 z-[1200] flex items-start gap-2 animate-in fade-in duration-500 md:inset-x-4 md:top-4 [&>*]:pointer-events-auto">
        <div className="flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface pr-4 pl-1.5 shadow-float max-md:pr-1.5">
          <LogoMark className="size-9" />
          <span className="font-display text-lg font-bold text-brand max-md:hidden">{BRAND_NAME}</span>
        </div>
        <div className="flex min-w-0 flex-1 items-start gap-2 md:max-w-[560px]">{search}</div>
        {locate}
        {!isMobile && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className={pill}>
                {t('Przykłady')} <ChevronDown className="size-4 text-text-muted" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="z-[1500] w-80 rounded-xl">
              {examples}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" aria-label={t('Menu')} className="flex size-12 shrink-0 items-center justify-center rounded-full bg-surface shadow-float hover:bg-sage-soft">
              <Menu className="size-5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="z-[1500] w-72 rounded-xl">
            {isMobile && (
              <>
                {examples}
                <DropdownMenuSeparator />
              </>
            )}
            {pages}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* podpowiedź: co zrobić na mapie */}
      <div className="pointer-events-none absolute inset-x-3 bottom-6 z-[1100] flex justify-center animate-in fade-in slide-in-from-bottom-3 duration-700">
        <p className="flex items-center gap-2.5 rounded-full bg-text/85 py-2.5 pr-4 pl-3 text-sm text-white shadow-float backdrop-blur">
          <MousePointerClick className="size-4 shrink-0" aria-hidden />
          {t('Przybliż mapę i kliknij swoje pole')}
        </p>
      </div>
    </>
  )
}
