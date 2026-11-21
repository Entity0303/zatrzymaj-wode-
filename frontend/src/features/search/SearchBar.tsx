import { Loader2, Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Parcel } from '@/api/types'
import { formatHa } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** Wyszukiwarka działki (SPEC 4.2, 14): pigułka z lupą, podpowiedzi, ładowanie, błąd pod spodem. */
export function SearchBar({
  loading,
  error,
  candidates,
  total,
  onSearch,
  onPick,
  onDismiss,
  className,
}: {
  loading: boolean
  error: string | null
  candidates: Parcel[]
  total: number
  onSearch: (q: string) => void
  onPick: (p: Parcel) => void
  onDismiss: () => void
  className?: string
}) {
  const { t } = useLang()
  const [q, setQ] = useState('')
  // podświetlona podpowiedź; resetuje się sama przy nowej liście kandydatów
  const [hl, setHl] = useState<{ list: Parcel[]; i: number }>({ list: candidates, i: -1 })
  const active = hl.list === candidates ? hl.i : -1
  const setActive = (f: (a: number) => number) => setHl({ list: candidates, i: f(active) })
  const inputRef = useRef<HTMLInputElement>(null)
  const open = candidates.length > 0

  // Start: kursor w wyszukiwarce (SPEC 13) – tylko na komputerze, na telefonie klawiatura zasłoniłaby mapę
  useEffect(() => {
    if (window.matchMedia('(min-width: 768px)').matches) inputRef.current?.focus()
  }, [])

  return (
    <div className={cn('relative', className)}>
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          if (open && active >= 0) onPick(candidates[active])
          else if (q.trim()) onSearch(q.trim())
        }}
        className="relative"
      >
        <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-text-muted" aria-hidden />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onDismiss()
            if (!open) return
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setActive((a) => Math.min(a + 1, candidates.length - 1))
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActive((a) => Math.max(a - 1, 0))
            }
          }}
          data-parcel-search
          aria-label={t('Numer działki')}
          aria-expanded={open}
          aria-controls="parcel-suggestions"
          aria-autocomplete="list"
          aria-invalid={!!error || undefined}
          enterKeyHint="search"
          placeholder={t('Wpisz numer działki, np. 143203_2.0027.112/11 lub Szczytno 112/11')}
          className={cn(
            'h-12 w-full rounded-full border bg-surface pr-12 pl-12 text-base shadow-float outline-none placeholder:text-sm placeholder:text-text-muted/80',
            'focus-visible:border-brand focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand',
            error && 'border-danger/60',
          )}
        />
        <span className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center">
          {loading ? (
            <Loader2 className="m-2.5 size-5 animate-spin text-brand" aria-label={t('Szukam')} />
          ) : q ? (
            <button
              type="button"
              aria-label={t('Wyczyść')}
              onClick={() => {
                setQ('')
                inputRef.current?.focus()
              }}
              className="flex size-9 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
            >
              <X className="size-5" />
            </button>
          ) : null}
        </span>
      </form>

      {error && !open && (
        <p className="absolute top-full left-4 z-10 mt-1.5 rounded-full bg-surface px-3 py-1 text-sm whitespace-nowrap text-danger shadow-card" role="alert">
          {error}
        </p>
      )}

      {open && (
        <div className="absolute inset-x-0 top-full z-10 mt-2 overflow-hidden rounded-xl border bg-surface shadow-float">
          <p className="border-b px-4 py-2 text-sm text-text-muted">
            {t('Znaleziono {n} działek – wybierz swoją', { n: total })}
            {total > candidates.length && ` ${t('(pokazano {n})', { n: candidates.length })}`}
          </p>
          <ul id="parcel-suggestions" role="listbox" className="max-h-[50vh] overflow-y-auto py-1">
            {candidates.map((c, i) => (
              <li key={c.id} role="option" aria-selected={i === active}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(() => i)}
                  onClick={() => onPick(c)}
                  className={cn('flex min-h-11 w-full items-center gap-3 px-4 py-2 text-left', i === active && 'bg-ok-soft')}
                >
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-semibold text-white">
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-base leading-6 font-medium">
                      {t('Działka {numer}', { numer: c.numer })} <span className="font-normal text-text-muted">· {formatHa(c.powierzchnia_ha)} ha</span>
                    </span>
                    <span className="block truncate text-sm leading-5 text-text-muted">
                      {t('obręb {obreb}, gm. {gmina}, woj. {woj}', { obreb: c.obreb, gmina: c.gmina, woj: c.wojewodztwo })}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
