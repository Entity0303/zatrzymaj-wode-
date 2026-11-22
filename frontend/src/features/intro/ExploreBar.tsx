import { ChevronDown, FileText, Loader2, Map as MapIcon, Menu as MenuIcon, MousePointerClick, PenLine, Settings, Sparkles, X, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { LogoMark } from '@/components/LogoMark'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { Example } from '@/features/parcel-panel/examples'
import type { DemoExamples } from './useDemoExamples'
import { BRAND_NAME } from '@/lib/brand'
import { useLang } from '@/lib/i18n'
import { goTo, type PageKey } from '@/lib/router'

/** Przycisk w lewej kolumnie: ikona + podpis pod spodem (bez rozwijanego menu), dymek z opisem. */
function RailButton({ icon: Icon, label, hint, onClick }: { icon: LucideIcon; label: string; hint: string; onClick: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          className="flex w-[72px] flex-col items-center gap-0.5 rounded-xl bg-surface/95 px-1 py-2 text-xs leading-4 font-medium shadow-float hover:bg-sage-soft md:w-20"
        >
          <Icon className="size-5 text-brand" aria-hidden />
          {label}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">{hint}</TooltipContent>
    </Tooltip>
  )
}

/**
 * Tryb przeglądania mapy (jak w mapach internetowych): u góry logo, wyszukiwarka, „Moja lokalizacja”, „Przykłady”;
 * po lewej kolumna z podpisanymi przyciskami stron i języka (zamiast ☰); na dole podpowiedź.
 * Reszta interfejsu pojawia się po kliknięciu pola.
 */
export function ExploreBar({
  isMobile,
  search,
  locate,
  onExample,
  examples,
  onDraw,
  onHome,
}: {
  /** klik w logo – wraca karta powitalna */
  onHome?: () => void
  isMobile: boolean
  search: ReactNode
  locate: ReactNode
  onExample: (e: Example) => void
  /** lista z /api/demo/examples */
  examples: DemoExamples
  /** „Narysuj swoje pole” – przycisk drugorzędny */
  onDraw?: () => void
}) {
  const { t } = useLang()
  const [menu, setMenu] = useState(false)

  const pages: { key: PageKey; icon: LucideIcon; label: string; hint: string }[] = [
    { key: 'parcels', icon: MapIcon, label: 'Moje działki', hint: 'Działki zapisane gwiazdką' },
    { key: 'reports', icon: FileText, label: 'Raporty', hint: 'Poprzednie paszporty wodne' },
    { key: 'settings', icon: Settings, label: 'Ustawienia', hint: 'Mapa, tryb, język, zapisane dane' },
  ]

  return (
    <>
      <div className="pointer-events-none absolute inset-x-3 top-3 z-[1200] flex items-start gap-2 animate-in fade-in duration-500 md:inset-x-4 md:top-4 [&>*]:pointer-events-auto">
        <button
          type="button"
          onClick={onHome}
          aria-label={t('{name} – pokaż kartę powitalną', { name: BRAND_NAME })}
          className="flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface pr-4 pl-1.5 shadow-float hover:bg-sage-soft max-md:pr-1.5"
        >
          <LogoMark className="size-9" />
          <span className="font-display text-lg font-bold text-brand max-md:hidden">{BRAND_NAME}</span>
        </button>
        <div className="flex min-w-0 flex-1 items-start gap-2 md:max-w-[560px]">{search}</div>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="shrink-0">{locate}</span>
          </TooltipTrigger>
          <TooltipContent>{t('Moja lokalizacja – znajdź działkę, na której stoisz')}</TooltipContent>
        </Tooltip>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={t('Przykłady')}
              className="flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface px-4 text-sm font-medium shadow-float hover:bg-sage-soft max-md:w-12 max-md:justify-center max-md:px-0"
            >
              <Sparkles className="size-4 text-amber md:hidden" aria-hidden />
              <span className="max-md:hidden">{t('Przykłady')}</span>
              <ChevronDown className="size-4 text-text-muted max-md:hidden" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="z-[1500] w-80 rounded-xl">
            <DropdownMenuLabel className="text-xs tracking-wider text-text-muted uppercase">{t('Zobacz przykład')}</DropdownMenuLabel>
            {examples.state === 'loading' && (
              <p className="flex items-center gap-2 px-2 py-2 text-sm text-text-muted">
                <Loader2 className="size-4 animate-spin" aria-hidden /> {t('Wczytuję przykłady…')}
              </p>
            )}
            {examples.state === 'error' && <p className="px-2 py-2 text-sm text-text-muted">{t('Przykłady są chwilowo niedostępne.')}</p>}
            {examples.examples.map((e) => (
              <DropdownMenuItem key={e.id} className="min-h-11 text-sm" onSelect={() => onExample(e)}>
                <span className={`flex size-7 items-center justify-center rounded-full ${e.tone}`}>
                  <e.icon className="size-4" />
                </span>
                <span className="min-w-0">
                  <span className="block font-medium">{t(e.title)}</span>
                  <span className="line-clamp-2 text-xs text-text-muted">{t(e.text)}</span>
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        {onDraw && !isMobile && (
          <button
            type="button"
            onClick={onDraw}
            className="flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface px-4 text-sm font-medium text-text-muted shadow-float hover:bg-sage-soft hover:text-text"
          >
            <PenLine className="size-4" aria-hidden /> {t('Narysuj swoje pole')}
          </button>
        )}
      </div>
      {/* telefon: w górnym rzędzie brak miejsca – mała pigułka pod nim, po prawej */}
      {onDraw && isMobile && (
        <button
          type="button"
          onClick={onDraw}
          className="absolute top-[68px] right-3 z-[1200] flex h-10 items-center gap-1.5 rounded-full bg-surface px-3.5 text-sm font-medium text-text-muted shadow-float"
        >
          <PenLine className="size-4" aria-hidden /> {t('Narysuj pole')}
        </button>
      )}

      {/* lewa kolumna (zamiast ☰): strony i język – zawsze widoczne, z podpisami */}
      <nav aria-label={t('Nawigacja główna')} className="pointer-events-auto absolute top-[72px] left-3 z-[1100] flex flex-col items-start gap-2 md:top-[76px] md:left-4">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => setMenu((o) => !o)}
              aria-expanded={menu}
              aria-label={t(menu ? 'Zwiń menu' : 'Menu')}
              className="flex size-10 items-center justify-center rounded-full bg-surface/95 text-text shadow-float hover:bg-sage-soft"
            >
              {menu ? <X className="size-4" aria-hidden /> : <MenuIcon className="size-4" aria-hidden />}
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">{t('Moje działki, raporty, ustawienia, język')}</TooltipContent>
        </Tooltip>
        {menu && (
          <div className="flex flex-col gap-2 animate-in fade-in slide-in-from-top-2 duration-200">
            {pages.map((p) => (
              <RailButton key={p.key} icon={p.icon} label={t(p.label)} hint={t(p.hint)} onClick={() => goTo(p.key)} />
            ))}
          </div>
        )}
      </nav>

      {/* podpowiedź: co zrobić na mapie */}
      <div className="pointer-events-none absolute inset-x-3 bottom-6 z-[1100] flex justify-center animate-in fade-in slide-in-from-bottom-3 duration-700">
        <p className="flex items-center gap-2.5 rounded-full bg-text/85 py-2.5 pr-4 pl-3 text-sm text-white shadow-float backdrop-blur">
          <MousePointerClick className="size-4 shrink-0" aria-hidden />
          {t(isMobile ? 'Kliknij swoje pole na mapie' : 'Przybliż mapę i kliknij swoje pole')}
        </p>
      </div>
    </>
  )
}
