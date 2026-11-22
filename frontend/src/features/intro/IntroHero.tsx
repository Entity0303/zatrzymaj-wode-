import { Loader2, PenLine, Search } from 'lucide-react'
import type { ReactNode } from 'react'
import { LogoMark } from '@/components/LogoMark'
import type { Example } from '@/features/parcel-panel/examples'
import type { DemoExamples } from './useDemoExamples'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** id formularza wyszukiwarki na karcie – przycisk „Sprawdź” wysyła ten sam formularz (atrybut `form`) */
export const HERO_SEARCH_FORM = 'hero-search'

/**
 * Karta powitalna (F12, F14 – pod jury KOWR: pierwsza sekunda = pole numeru działki i data analizy).
 * Nagłówek: logo + „Wodoskop”, pod spodem podtytuł. Wiersz wyszukiwania jako jedna siatka (gap 12 px, bez
 * nakładania): [pole „Wpisz numer działki lub adres” z lupą i „Moja lokalizacja” w środku] [data analizy]
 * [„Sprawdź”] – wszystkie 48 px, ramka 1 px, bez cieni; przy karcie < 640 px pole na całą szerokość, pod nim
 * data i przycisk. Data – ten sam stan `asOf` co górny pasek (pasek nie jest pokazywany, gdy karta jest widoczna).
 * Pod spodem podpowiedź formatu, „albo kliknij swoje pole na mapie · Narysuj swoje pole” i chipy przykładów
 * (zawijane, maks. 6). Chowa się przy przybliżaniu / przeciąganiu (wtedy wąski pasek z polem).
 */
export function IntroHero({
  search,
  date,
  examples,
  onExample,
  onDraw,
  leaving,
}: {
  /** chowanie (ok. 200 ms): przezroczystość + lekki zjazd w dół, bez klikania */
  leaving?: boolean
  /** SearchBar w wariancie „field” z formularzem `HERO_SEARCH_FORM` i lokalizacją w polu */
  search: ReactNode
  /** pole daty analizy (DateField `field`) */
  date: ReactNode
  examples: DemoExamples
  onExample: (e: Example) => void
  onDraw?: () => void
  isMobile?: boolean
}) {
  const { t } = useLang()
  const tagline = t(BRAND_TAGLINE)
  return (
    <div
      className={cn(
        'pointer-events-none absolute inset-0 z-[1200] flex items-center justify-center p-3 transition-opacity duration-200 md:p-6 motion-reduce:transition-none',
        leaving && 'opacity-0',
      )}
      aria-hidden={leaving || undefined}
      inert={leaving || undefined}
    >
      {/* lekkie przyciemnienie mapy – klik w mapę przechodzi dalej (wybór pola) */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(31,66,48,0.40)_0%,rgba(31,66,48,0.12)_60%,rgba(31,66,48,0.05)_100%)]" aria-hidden />
      <section
        aria-labelledby="hero-title"
        className={cn(
          '@container relative max-h-full w-full max-w-[760px] animate-in overflow-y-auto overscroll-contain rounded-[28px] bg-surface/95 p-5 shadow-float backdrop-blur-md transition-transform duration-200 fade-in slide-in-from-bottom-2 sm:p-7 motion-reduce:animate-none',
          leaving ? 'pointer-events-none translate-y-2' : 'pointer-events-auto',
        )}
      >
        {/* nagłówek: logo + nazwa w jednej linii, podtytuł pod spodem */}
        <div className="flex items-center gap-3">
          <LogoMark className="size-11 shrink-0" />
          <div className="min-w-0">
            <h1 id="hero-title" className="font-display text-[28px] leading-8 font-bold text-brand-dark">
              {BRAND_NAME}
            </h1>
            <p className="text-base leading-6 text-text-muted sm:text-[17px]">{tagline.charAt(0).toUpperCase() + tagline.slice(1)}</p>
          </div>
        </div>

        {/* wiersz wyszukiwania: jedna siatka, bez nakładania */}
        <div className="mt-6 grid grid-cols-2 gap-3 @min-[640px]:grid-cols-[minmax(0,1fr)_200px_auto]">
          <div className="col-span-2 min-w-0 @min-[640px]:col-span-1">{search}</div>
          <div className="min-w-0">{date}</div>
          <button
            type="submit"
            form={HERO_SEARCH_FORM}
            className="flex h-12 items-center justify-center gap-2 rounded-xl border border-brand-dark bg-brand-dark px-5 text-base font-semibold text-white hover:bg-brand"
          >
            <Search className="size-5" aria-hidden /> {t('Sprawdź')}
          </button>
        </div>
        <p className="mt-2 text-sm leading-5 text-text-muted">{t('np. 201305_2.0038.6/1 albo: Kobylin-Borzymy, Wnory-Wandy 6/1')}</p>
        <p className="mt-2 flex flex-wrap items-center gap-x-2 text-sm leading-5">
          <span>{t('albo kliknij swoje pole na mapie')}</span>
          {onDraw && (
            <>
              <span className="text-text-muted" aria-hidden>
                ·
              </span>
              <button type="button" onClick={onDraw} className="inline-flex min-h-10 items-center gap-1.5 font-medium text-brand hover:underline">
                <PenLine className="size-4" aria-hidden /> {t('Narysuj swoje pole')}
              </button>
            </>
          )}
        </p>

        {/* przykłady – chipy zawijane do kolejnej linii, etykieta w linii z pierwszymi chipami */}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t pt-4" aria-label={t('Przykłady')}>
          <span className="text-sm text-text-muted">{t('lub zobacz przykład:')}</span>
          {examples.state === 'loading' ? (
            <span className="flex items-center gap-1.5 text-sm text-text-muted" role="status">
              <Loader2 className="size-4 animate-spin text-brand" aria-hidden /> {t('Wczytuję przykłady…')}
            </span>
          ) : examples.state === 'error' || !examples.examples.length ? (
            <span className="text-sm text-text-muted">{t('chwilowo niedostępne')}</span>
          ) : (
            examples.examples.slice(0, 6).map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => onExample(e)}
                title={t(e.text)}
                className="flex min-h-9 max-w-full items-center gap-1.5 rounded-full border bg-surface px-3 py-1 text-left text-sm font-medium hover:border-brand/50 hover:bg-sage-soft"
              >
                <e.icon className="size-4 shrink-0 text-brand" aria-hidden /> <span className="min-w-0">{t(e.title)}</span>
              </button>
            ))
          )}
        </div>
      </section>
    </div>
  )
}
