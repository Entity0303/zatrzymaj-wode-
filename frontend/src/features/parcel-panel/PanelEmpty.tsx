import { LocateFixed, MousePointerClick, Search } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'

/** Panel bez wybranej działki (SPEC 6, 15.1). */
export function PanelEmpty({ onFocusSearch, onLocate }: { onFocusSearch: () => void; onLocate: () => void }) {
  const ways = [
    { icon: Search, title: 'Wpisz numer działki', text: 'np. Szczytno 112/11', action: onFocusSearch },
    { icon: MousePointerClick, title: 'Kliknij swoje pole na mapie', text: 'przybliż mapę i kliknij w działkę' },
    { icon: LocateFixed, title: 'Moja lokalizacja', text: 'gdy stoisz na polu', action: onLocate },
  ]
  return (
    <EmptyState
      illustration={<FieldIllustration className="w-40" />}
      title="Znajdź swoją działkę"
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
                <span className="block text-base leading-6 font-medium">{title}</span>
                <span className="block text-sm leading-5 text-text-muted">{text}</span>
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
  )
}
