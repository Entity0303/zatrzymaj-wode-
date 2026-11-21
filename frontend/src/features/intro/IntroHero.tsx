import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { LogoMark } from '@/components/LogoMark'
import { EXAMPLES, type Example } from '@/features/parcel-panel/examples'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { useLang } from '@/lib/i18n'
import { goTo } from '@/lib/router'

/**
 * Ekran powitalny (przed wyborem działki): tylko mapa i ta karta – logo, hasło, wyszukiwarka,
 * „Moja lokalizacja”, przykłady jednym klikiem (demo dla jury) i dyskretne linki do stron.
 * Reszta interfejsu pojawia się dopiero po wybraniu działki.
 */
export function IntroHero({ search, locate, onExample }: { search: ReactNode; locate: ReactNode; onExample: (e: Example) => void }) {
  const { t } = useLang()
  return (
    <div className="pointer-events-none absolute inset-0 z-[1200] flex items-center justify-center p-4">
      {/* miękka winieta: mapa widoczna, środek spokojny */}
      <div
        className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(250,246,236,0.55)_0%,rgba(250,246,236,0.15)_45%,rgba(31,66,48,0.35)_100%)]"
        aria-hidden
      />
      <section
        aria-labelledby="intro-title"
        className="pointer-events-auto relative w-full max-w-xl animate-in rounded-[28px] bg-surface/90 px-6 pt-8 pb-6 text-center shadow-float backdrop-blur-md duration-700 fade-in slide-in-from-bottom-6 md:px-10 md:pt-10"
      >
        <LogoMark className="mx-auto size-16 animate-in shadow-card duration-700 zoom-in-75 [border-radius:18px]" />
        <h1 id="intro-title" className="font-display mt-4 text-[40px] leading-[44px] font-semibold text-brand-dark md:text-5xl md:leading-[52px]">
          {BRAND_NAME}
        </h1>
        <p className="mt-2 text-lg leading-7 text-text-muted">{t(BRAND_TAGLINE)}</p>

        <div className="mt-6 flex items-start gap-2 text-left">
          {search}
          {locate}
        </div>
        <p className="mt-2 text-sm leading-5 text-text-muted">{t('albo kliknij swoje pole na mapie')}</p>

        <div className="mt-6">
          <p className="text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Zobacz przykład')}</p>
          <ul className="mt-2.5 flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => onExample(e)}
                  className="group flex h-10 items-center gap-1.5 rounded-full border bg-surface pr-3 pl-1.5 text-sm font-medium transition-colors hover:border-brand/50 hover:bg-sage-soft"
                >
                  <span className={`flex size-7 items-center justify-center rounded-full ${e.tone}`}>
                    <e.icon className="size-4" aria-hidden />
                  </span>
                  {t(e.title)}
                  <ChevronRight className="size-3.5 text-text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        </div>

        <nav aria-label={t('Nawigacja główna')} className="mt-6 flex justify-center gap-1 border-t pt-4 text-sm">
          {(
            [
              ['parcels', 'Moje działki'],
              ['reports', 'Raporty'],
              ['settings', 'Ustawienia'],
            ] as const
          ).map(([k, label]) => (
            <button key={k} type="button" onClick={() => goTo(k)} className="h-9 rounded-full px-3 font-medium text-text-muted hover:bg-surface-2 hover:text-brand">
              {t(label)}
            </button>
          ))}
        </nav>
      </section>
    </div>
  )
}
