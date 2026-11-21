import { ChevronRight, FileDown, ScanSearch, Search } from 'lucide-react'
import type { ReactNode } from 'react'
import { LogoMark } from '@/components/LogoMark'
import type { Example } from '@/features/parcel-panel/examples'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { useLang } from '@/lib/i18n'

const STEPS = [
  { icon: Search, label: 'Znajdź działkę' },
  { icon: ScanSearch, label: 'Zobacz werdykt' },
  { icon: FileDown, label: 'Pobierz raport' },
] as const

/**
 * Karta powitalna (B0 – pierwsze 10 sekund dla jury): co to jest, co zrobić, duża wyszukiwarka,
 * 2 przykłady jednym klikiem i 3 kroki. Mapa pod spodem przyciemniona. Znika po pierwszym
 * wyszukaniu / kliknięciu w mapę / lokalizacji / przykładzie.
 */
export function IntroHero({
  search,
  locate,
  examples,
  onExample,
}: {
  search: ReactNode
  locate: ReactNode
  examples: Example[]
  onExample: (e: Example) => void
}) {
  const { t } = useLang()
  return (
    <div className="pointer-events-none absolute inset-0 z-[1200] flex items-center justify-center p-3 md:p-6 lg:justify-start lg:pl-10">
      {/* przyciemnienie mapy – klik w mapę przechodzi dalej (wybór pola) */}
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(31,66,48,0.45)_0%,rgba(31,66,48,0.15)_55%,rgba(31,66,48,0.05)_100%)]" aria-hidden />
      <section
        aria-labelledby="hero-title"
        className="pointer-events-auto relative w-full max-w-2xl animate-in rounded-[28px] bg-surface/95 px-5 pt-7 pb-6 shadow-float backdrop-blur-md duration-500 fade-in slide-in-from-bottom-4 md:px-10 md:pt-9"
      >
        <div className="flex items-center gap-3">
          <LogoMark className="size-12 shrink-0 md:size-14" />
          <h1 id="hero-title" className="font-display text-2xl leading-8 font-semibold text-brand-dark md:text-[34px] md:leading-[40px]">
            {BRAND_NAME} <span className="font-normal text-text-muted">– {t(BRAND_TAGLINE)}</span>
          </h1>
        </div>
        <p className="mt-3 text-base leading-6 md:text-lg md:leading-7">
          {t('Sprawdź, ile wody trzyma Twoja ziemia, co tu posiać i jak zatrzymać wodę na polu.')}
        </p>

        {/* duża wyszukiwarka */}
        <div className="mt-5 flex items-start gap-2 [&_input]:h-14 [&_input]:text-lg">
          {search}
          {locate}
        </div>
        <p className="mt-2 pl-1 text-sm leading-5 text-text-muted">{t('Numer działki albo nazwa miejscowości – albo kliknij pole na mapie.')}</p>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-text-muted">{t('Zobacz przykład:')}</span>
          {examples.slice(0, 2).map((e) => (
            <button
              key={e.id}
              type="button"
              onClick={() => onExample(e)}
              title={t(e.text)}
              className="group flex h-11 items-center gap-2 rounded-full border bg-surface pr-3.5 pl-1.5 text-sm font-semibold transition-colors hover:border-brand/50 hover:bg-sage-soft"
            >
              <span className={`flex size-8 items-center justify-center rounded-full ${e.tone}`}>
                <e.icon className="size-4" aria-hidden />
              </span>
              {t(e.title)}
              <ChevronRight className="size-4 text-text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
            </button>
          ))}
        </div>

        {/* 3 kroki */}
        <ol className="mt-6 grid grid-cols-3 gap-2 border-t pt-5" aria-label={t('Jak to działa')}>
          {STEPS.map((s, i) => (
            <li key={s.label} className="flex flex-col items-center gap-1.5 text-center">
              <span className="relative flex size-10 items-center justify-center rounded-full bg-sage-soft text-brand">
                <s.icon className="size-5" aria-hidden />
                <span className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-brand text-xs font-bold text-white">
                  {i + 1}
                </span>
              </span>
              <span className="text-sm leading-5 font-medium">{t(s.label)}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
