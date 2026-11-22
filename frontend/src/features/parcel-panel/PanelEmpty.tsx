import { LocateFixed, MousePointerClick, Search } from 'lucide-react'
import type { Example } from './examples'
import { ExampleCards } from '@/features/intro/ExampleCards'
import type { DemoExamples } from '@/features/intro/useDemoExamples'
import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'
import { useLang } from '@/lib/i18n'

/** Panel bez wybranej działki (SPEC 6, 15.1). */
export function PanelEmpty({
  onFocusSearch,
  onLocate,
  onExample,
  examples,
}: {
  onFocusSearch: () => void
  onLocate: () => void
  /** lista z /api/demo/examples */
  examples?: DemoExamples
  /** „Zobacz przykład” – jeden klik = pełna analiza */
  onExample?: (e: Example) => void
}) {
  const { t } = useLang()
  const ways = [
    { icon: Search, title: 'Wpisz numer działki', text: 'np. Szczytno 112/11', action: onFocusSearch },
    { icon: MousePointerClick, title: 'Kliknij swoje pole na mapie', text: 'przybliż mapę i kliknij w działkę' },
    { icon: LocateFixed, title: 'Moja lokalizacja', text: 'gdy stoisz na polu', action: onLocate },
  ]
  return (
    <div className="space-y-6">
      {onExample && (
        <section aria-labelledby="examples-h" className="space-y-3">
          <h2 id="examples-h" className="font-display text-xl leading-7 font-semibold text-brand-dark">
            {t('Zobacz przykład')}
          </h2>
          <p className="-mt-2 text-sm leading-5 text-text-muted">{t('Jeden klik – pełna analiza prawdziwej działki.')}</p>
          {examples ? <ExampleCards demo={examples} onExample={onExample} columns={1} /> : null}
        </section>
      )}
    <EmptyState
      illustration={<FieldIllustration className="w-40" />}
      title={onExample ? 'Albo znajdź swoją działkę' : 'Znajdź swoją działkę'}
      description="Pokażemy granice pola i jego stan wodny."
    >
      <ul className="space-y-2 text-left">
        {ways.map(({ icon: Icon, title, text, action }) => {
          const inner = (
            <>
              <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-ok-soft text-brand">
                <Icon className="size-5" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block text-base leading-6 font-medium">{t(title)}</span>
                <span className="block text-sm leading-5 text-text-muted">{t(text)}</span>
              </span>
            </>
          )
          return (
            <li key={title}>
              {action ? (
                <button
                  type="button"
                  onClick={action}
                  className="flex min-h-14 w-full items-center gap-3 rounded-xl border bg-surface p-2.5 text-left hover:border-brand/50 hover:bg-ok-soft"
                >
                  {inner}
                </button>
              ) : (
                <div className="flex min-h-14 items-center gap-3 rounded-xl border bg-surface p-2.5">{inner}</div>
              )}
            </li>
          )
        })}
      </ul>
    </EmptyState>
    </div>
  )
}
