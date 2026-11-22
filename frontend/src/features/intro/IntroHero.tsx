import { FileDown, PenLine, ScanSearch, Search } from 'lucide-react'
import type { ReactNode } from 'react'
import { LogoMark } from '@/components/LogoMark'
import type { Example } from '@/features/parcel-panel/examples'
import { ExampleCards } from './ExampleCards'
import type { DemoExamples } from './useDemoExamples'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { useLang } from '@/lib/i18n'

const STEPS = [
  { icon: Search, label: 'Znajdź działkę' },
  { icon: ScanSearch, label: 'Zobacz werdykt' },
  { icon: FileDown, label: 'Pobierz raport' },
] as const

/**
 * Karta powitalna (B0 – pierwsze 10 sekund dla jury): co to jest, co zrobić, duża wyszukiwarka,
 * do 6 przykładów jednym klikiem z /api/demo/examples (nazwa + „co pokazuje”), „narysuj swoje pole” i 3 kroki. Mapa pod spodem przyciemniona. Znika po pierwszym
 * wyszukaniu / kliknięciu w mapę / lokalizacji / przykładzie.
 */
export function IntroHero({
  search,
  locate,
  examples,
  onExample,
  onDraw,
  isMobile,
}: {
  search: ReactNode
  locate: ReactNode
  examples: DemoExamples
  onExample: (e: Example) => void
  onDraw?: () => void
  isMobile?: boolean
}) {
  const { t } = useLang()
  return (
    <div className="pointer-events-none absolute inset-0 z-[1200] flex items-center justify-center p-3 md:p-6 lg:justify-start lg:pl-10">
      {/* przyciemnienie mapy – klik w mapę przechodzi dalej (wybór pola) */}
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(31,66,48,0.45)_0%,rgba(31,66,48,0.15)_55%,rgba(31,66,48,0.05)_100%)]" aria-hidden />
      <section
        aria-labelledby="hero-title"
        className="pointer-events-auto relative max-h-full w-full max-w-3xl animate-in overflow-y-auto overscroll-contain rounded-[28px] bg-surface/95 px-5 pt-6 pb-5 shadow-float backdrop-blur-md duration-500 fade-in slide-in-from-bottom-4 md:px-9 md:pt-8"
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

        {onDraw && (
          <button
            type="button"
            onClick={onDraw}
            className="mt-1 inline-flex min-h-10 items-center gap-1.5 pl-1 text-sm font-medium text-brand hover:underline"
          >
            <PenLine className="size-4" aria-hidden /> {t('Działka nie pasuje do pola? Narysuj swoje pole')}
          </button>
        )}

        <section aria-labelledby="hero-examples" className="mt-4 space-y-2.5">
          <h2 id="hero-examples" className="text-sm font-semibold tracking-wider text-text-muted uppercase">
            {t('Zobacz przykład – jeden klik, pełna analiza')}
          </h2>
          <ExampleCards demo={examples} onExample={onExample} row={isMobile} columns={3} />
        </section>

        {/* 3 kroki */}
        <ol className="mt-5 grid grid-cols-3 gap-2 border-t pt-4 max-md:hidden [@media(max-height:760px)]:hidden" aria-label={t('Jak to działa')}>
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
