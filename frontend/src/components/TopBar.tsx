import { CalendarDays, Droplets, Loader2, LocateFixed, Search, X } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { minAnalysisIso, todayIso } from '@/lib/dates'

type Props = {
  loading: boolean
  locating: boolean
  asOf: string
  onAsOfChange: (v: string) => void
  onSearch: (query: string) => void
  onLocate: () => void
}

/** Pływający pasek u góry: wyszukiwarka działki, lokalizacja, data analizy. */
export function TopBar({ loading, locating, asOf, onAsOfChange, onSearch, onLocate }: Props) {
  const [query, setQuery] = useState('')

  return (
    <div className="pointer-events-none absolute inset-x-2 top-2 z-[1050] md:right-4 md:left-[104px] md:top-4">
      <div className="pointer-events-auto flex flex-col gap-2 rounded-2xl border bg-card/95 p-2 shadow-lg md:flex-row md:items-center md:gap-3 md:p-2.5">
        <form
          className="flex min-w-0 flex-1 items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (query.trim()) onSearch(query.trim())
          }}
        >
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground md:hidden">
            <Droplets className="size-5" />
          </div>
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label="Numer działki"
              className="h-11 rounded-xl bg-background pr-9 pl-9 text-base md:text-sm"
              placeholder="Wpisz numer działki, np. 143203_2.0027.112/11 lub Szczytno 112/11"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              enterKeyHint="search"
            />
            {query && (
              <button
                type="button"
                aria-label="Wyczyść"
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-muted"
                onClick={() => setQuery('')}
              >
                <X className="size-4" />
              </button>
            )}
          </div>
          <Button type="submit" className="h-11 rounded-xl px-4" disabled={loading || !query.trim()}>
            {loading ? <Loader2 className="animate-spin" /> : <Search className="md:hidden" />}
            <span className="hidden md:inline">Szukaj</span>
          </Button>
        </form>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="h-10 flex-1 rounded-xl md:h-11 md:flex-none"
            onClick={onLocate}
            disabled={locating}
            title="Znajdź działkę, na której teraz stoisz"
          >
            {locating ? <Loader2 className="animate-spin" /> : <LocateFixed className="text-primary" />}
            Moja lokalizacja
          </Button>
          <label className="flex h-10 flex-1 items-center gap-2 rounded-xl border bg-background px-3 text-sm md:h-11 md:flex-none">
            <CalendarDays className="size-4 shrink-0 text-primary" />
            <span className="hidden whitespace-nowrap text-muted-foreground lg:inline">Data analizy</span>
            <input
              type="date"
              aria-label="Data analizy"
              className="min-w-0 flex-1 bg-transparent font-medium outline-none"
              value={asOf}
              min={minAnalysisIso()}
              max={todayIso()}
              onChange={(e) => e.target.value && onAsOfChange(e.target.value)}
            />
          </label>
        </div>
      </div>
    </div>
  )
}
