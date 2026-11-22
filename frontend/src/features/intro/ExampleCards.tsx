import { ChevronRight, Loader2 } from 'lucide-react'
import type { Example } from '@/features/parcel-panel/examples'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import type { DemoExamples } from './useDemoExamples'

/**
 * Karty „Zobacz przykład” z GET /api/demo/examples: ikona, nazwa, jedno zdanie „co pokazuje”.
 * `row` – telefon: jeden przewijany poziomo rząd kart (mniej wysokości), inaczej siatka 2–3 kolumny.
 * Ładowanie i brak odpowiedzi serwera mówione wprost – bez listy zapasowej w kodzie.
 */
export function ExampleCards({
  demo,
  onExample,
  limit = 6,
  row,
  columns = 3,
}: {
  demo: DemoExamples
  onExample: (e: Example) => void
  limit?: number
  row?: boolean
  /** 1 – wąski panel działki */
  columns?: 1 | 2 | 3
}) {
  const { t } = useLang()
  if (demo.state === 'loading')
    return (
      <p className="flex items-center gap-2 text-sm leading-5 text-text-muted" role="status">
        <Loader2 className="size-4 animate-spin text-brand" aria-hidden /> {t('Wczytuję przykłady…')}
      </p>
    )
  if (demo.state === 'error' || !demo.examples.length)
    return <p className="text-sm leading-5 text-text-muted">{t('Przykłady są chwilowo niedostępne – wpisz numer działki albo kliknij pole na mapie.')}</p>
  return (
    <ul
      className={cn(
        row
          ? 'scrollbar-none -mx-5 flex snap-x snap-mandatory gap-2.5 overflow-x-auto px-5 pb-1'
          : cn('grid grid-cols-1 gap-2.5', columns > 1 && 'sm:grid-cols-2', columns === 3 && 'lg:grid-cols-3'),
      )}
    >
      {demo.examples.slice(0, limit).map((e) => (
        <li key={e.id} className={row ? 'w-[230px] shrink-0 snap-start' : undefined}>
          <button
            type="button"
            onClick={() => onExample(e)}
            className="group flex h-full w-full items-start gap-2.5 rounded-xl border bg-surface p-3 text-left transition-colors hover:border-brand/50 hover:bg-sage-soft"
          >
            <span className={`flex size-9 shrink-0 items-center justify-center rounded-full ${e.tone}`}>
              <e.icon className="size-5" aria-hidden />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1 text-base leading-5 font-semibold">
                {t(e.title)}
                <ChevronRight className="size-4 shrink-0 text-text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
              </span>
              <span className="mt-0.5 line-clamp-2 text-sm leading-5 text-text-muted" title={t(e.text)}>{t(e.text)}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
