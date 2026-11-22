import { Loader2, PenLine } from 'lucide-react'
import type { ReactNode } from 'react'
import { LogoMark } from '@/components/LogoMark'
import type { Example } from '@/features/parcel-panel/examples'
import type { DemoExamples } from './useDemoExamples'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * Karta powitalna (F12 – pod jury KOWR: pierwsza sekunda = pole numeru działki i data analizy). Na środku duże pole
 * „Wpisz numer działki lub adres” z podpowiedzią formatu, obok data analizy (ta sama co w górnym pasku – jeden stan
 * `asOf`), pod spodem „albo kliknij swoje pole na mapie” i jedna linijka małych chipów z przykładami
 * (/api/demo/examples). Enter = szukaj. Chowa się przy przybliżaniu / przeciąganiu (wtedy wąski pasek z polem).
 */
export function IntroHero({
  search,
  locate,
  date,
  examples,
  onExample,
  onDraw,
  leaving,
}: {
  /** chowanie (ok. 200 ms): przezroczystość + lekki zjazd w dół, bez klikania */
  leaving?: boolean
  search: ReactNode
  locate: ReactNode
  /** pole daty analizy (DateField – ten sam stan co w górnym pasku) */
  date: ReactNode
  examples: DemoExamples
  onExample: (e: Example) => void
  onDraw?: () => void
  isMobile?: boolean
}) {
  const { t } = useLang()
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
          'relative max-h-full w-full max-w-2xl animate-in overflow-y-auto overscroll-contain rounded-[28px] bg-surface/95 px-5 pt-5 pb-4 shadow-float backdrop-blur-md transition-transform duration-200 fade-in slide-in-from-bottom-2 motion-reduce:animate-none md:px-8 md:pt-7 md:pb-6',
          leaving ? 'pointer-events-none translate-y-2' : 'pointer-events-auto',
        )}
      >
        <div className="flex items-center gap-3">
          <LogoMark className="size-10 shrink-0 md:size-12" />
          <h1 id="hero-title" className="font-display text-xl leading-7 font-bold text-brand-dark md:text-[28px] md:leading-9">
            {BRAND_NAME} <span className="font-normal text-text-muted">– {t(BRAND_TAGLINE)}</span>
          </h1>
        </div>

        {/* pole numeru działki + data analizy */}
        <div className="mt-5 flex flex-col gap-2 md:flex-row md:items-start">
          <div className="flex min-w-0 flex-1 items-start gap-2 [&_input]:h-14 [&_input]:text-lg">
            {search}
            {locate}
          </div>
          <div className="shrink-0 [&_label]:h-14">{date}</div>
        </div>
        <p className="mt-2 pl-1 text-sm leading-5 text-text-muted">{t('np. 201305_2.0038.6/1 albo: Kobylin-Borzymy, Wnory-Wandy 6/1')}</p>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 pl-1 text-sm leading-5">
          <span>{t('albo kliknij swoje pole na mapie')}</span>
          {onDraw && (
            <button type="button" onClick={onDraw} className="inline-flex min-h-10 items-center gap-1.5 font-medium text-brand hover:underline">
              <PenLine className="size-4" aria-hidden /> {t('Narysuj swoje pole')}
            </button>
          )}
        </p>

        {/* przykłady – jedna linijka małych chipów */}
        <div className="mt-3 flex items-center gap-2 border-t pt-3">
          <span className="shrink-0 text-sm text-text-muted">{t('lub zobacz przykład:')}</span>
          {examples.state === 'loading' ? (
            <span className="flex items-center gap-1.5 text-sm text-text-muted" role="status">
              <Loader2 className="size-4 animate-spin text-brand" aria-hidden /> {t('Wczytuję przykłady…')}
            </span>
          ) : examples.state === 'error' || !examples.examples.length ? (
            <span className="text-sm text-text-muted">{t('chwilowo niedostępne')}</span>
          ) : (
            <ul className="scrollbar-none flex min-w-0 flex-1 gap-1.5 overflow-x-auto" aria-label={t('Przykłady')}>
              {examples.examples.slice(0, 6).map((e) => (
                <li key={e.id} className="shrink-0">
                  <button
                    type="button"
                    onClick={() => onExample(e)}
                    title={t(e.text)}
                    className="flex h-9 items-center gap-1.5 rounded-full border bg-surface px-3 text-sm font-medium whitespace-nowrap hover:border-brand/50 hover:bg-sage-soft"
                  >
                    <e.icon className="size-4 text-brand" aria-hidden /> {t(e.title)}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}
