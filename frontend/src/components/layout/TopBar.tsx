import { CalendarDays, Loader2, LocateFixed, Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Forecast, Parcel } from '@/api'
import { WeatherIcon } from '@/components/common/Art'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { minAnalysisIso, todayIso } from '@/lib/dates'
import { formatHa } from '@/lib/format'
import { LAYERS, type LayerKey } from '@/lib/layers'
import { cn } from '@/lib/utils'

// ── SearchBar (SPEC 4.2, 14) ─────────────────────────────────────────────────────────────────

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
          aria-label="Numer działki"
          aria-expanded={open}
          aria-controls="parcel-suggestions"
          aria-autocomplete="list"
          aria-invalid={!!error || undefined}
          enterKeyHint="search"
          placeholder="Wpisz numer działki, np. 143203_2.0027.112/11 lub Szczytno 112/11"
          className={cn(
            'h-12 w-full rounded-full border bg-surface pr-12 pl-12 text-base shadow-float outline-none placeholder:text-sm placeholder:text-text-muted/80',
            'focus-visible:border-brand focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand',
            error && 'border-danger/60',
          )}
        />
        <span className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center">
          {loading ? (
            <Loader2 className="m-2.5 size-5 animate-spin text-brand" aria-label="Szukam" />
          ) : q ? (
            <button
              type="button"
              aria-label="Wyczyść"
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
            Znaleziono {total} działek – wybierz swoją
            {total > candidates.length && ` (pokazano ${candidates.length})`}
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
                      Działka {c.numer} <span className="font-normal text-text-muted">· {formatHa(c.powierzchnia_ha)} ha</span>
                    </span>
                    <span className="block truncate text-sm leading-5 text-text-muted">
                      obręb {c.obreb}, gm. {c.gmina}, woj. {c.wojewodztwo}
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

// ── Przycisk „Moja lokalizacja” ───────────────────────────────────────────────────────────────

export function LocateButton({ locating, onClick, iconOnly }: { locating: boolean; onClick: () => void; iconOnly?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={locating}
      aria-label="Moja lokalizacja – znajdź działkę, na której stoisz"
      className={cn(
        'flex h-12 shrink-0 items-center justify-center gap-2 rounded-full border bg-surface font-medium text-text shadow-float hover:bg-ok-soft disabled:opacity-70',
        iconOnly ? 'w-12' : 'px-4 text-base',
      )}
    >
      {locating ? <Loader2 className="size-5 animate-spin text-brand" /> : <LocateFixed className="size-5 text-brand" />}
      {!iconOnly && <span className="whitespace-nowrap">Moja lokalizacja</span>}
    </button>
  )
}

// ── WeatherWidget (SPEC 4.2, 14) ─────────────────────────────────────────────────────────────

export function WeatherWidget({
  forecast,
  loading,
  error,
  where,
  compact,
}: {
  forecast: Forecast | null
  loading: boolean
  error: boolean
  where: string
  compact?: boolean
}) {
  const now = forecast?.teraz
  const label = now
    ? `Pogoda teraz ${where}: ${now.temperatura === null ? 'brak temperatury' : `${Math.round(now.temperatura)}°C`}, ${now.opis}. Źródło: Open-Meteo.`
    : 'Pogoda'
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          tabIndex={0}
          aria-label={label}
          className={cn(
            'flex h-12 shrink-0 items-center gap-2 rounded-full border bg-surface px-4 shadow-float',
            compact && 'h-11 px-3 shadow-none',
          )}
        >
          {loading && !now ? (
            <>
              <Skeleton className="size-6 rounded-full bg-surface-2" />
              <Skeleton className="h-4 w-20 bg-surface-2" />
            </>
          ) : error || !now ? (
            <span className="text-sm text-text-muted">Pogoda niedostępna</span>
          ) : (
            <>
              <WeatherIcon icon={now.ikona} night={!now.dzien} className="size-6" />
              <span className="tabular text-base font-semibold">
                {now.temperatura === null ? '—' : `${Math.round(now.temperatura)}°C`}
              </span>
              {!compact && <span className="hidden max-w-36 truncate text-sm text-text-muted xl:inline">{now.opis}</span>}
            </>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>{now ? `${now.opis} · ${where} · Open-Meteo` : 'Pogoda z Open-Meteo'}</TooltipContent>
    </Tooltip>
  )
}

// ── Data analizy ──────────────────────────────────────────────────────────────────────────────

export function DateField({ value, onChange, compact }: { value: string; onChange: (v: string) => void; compact?: boolean }) {
  return (
    <label
      className={cn(
        'flex h-12 shrink-0 items-center gap-2 rounded-full border bg-surface px-4 shadow-float',
        compact && 'h-11 w-full rounded-md shadow-none',
      )}
    >
      <CalendarDays className="size-5 shrink-0 text-brand" aria-hidden />
      <span className={cn('text-sm whitespace-nowrap text-text-muted', compact ? 'max-[419px]:hidden' : 'hidden xl:inline')}>
        Data analizy
      </span>
      <input
        type="date"
        aria-label="Data analizy"
        value={value}
        min={minAnalysisIso()}
        max={todayIso()}
        onChange={(e) => e.target.value && onChange(e.target.value)}
        className="tabular min-w-0 flex-1 bg-transparent text-base font-semibold outline-none"
      />
    </label>
  )
}

// ── LayerPills + przełącznik 2D | 3D (SPEC 4.2, 5.3) ─────────────────────────────────────────

export function LayerPills({ value, onChange, className }: { value: LayerKey; onChange: (k: LayerKey) => void; className?: string }) {
  return (
    <div role="radiogroup" aria-label="Warstwa mapy" className={cn('scrollbar-none flex gap-2 overflow-x-auto', className)}>
      {LAYERS.map((l) => {
        const active = l.key === value
        const Icon = l.icon
        return (
          <button
            key={l.key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(l.key)}
            className={cn(
              'flex h-10 shrink-0 items-center gap-2 rounded-full border px-3.5 text-sm font-medium whitespace-nowrap shadow-float transition-colors',
              active ? 'border-brand bg-ok-soft text-brand' : 'border-transparent bg-surface text-text hover:bg-surface-2',
            )}
          >
            <Icon className="size-[18px]" aria-hidden />
            {l.label}
          </button>
        )
      })}
    </div>
  )
}

export function ViewToggle() {
  return (
    <div role="radiogroup" aria-label="Widok mapy" className="flex h-10 shrink-0 items-center rounded-full border bg-surface p-1 shadow-float">
      <button type="button" role="radio" aria-checked className="h-8 rounded-full bg-brand px-3.5 text-sm font-semibold text-white">
        2D
      </button>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            role="radio"
            aria-checked={false}
            aria-disabled
            onClick={(e) => e.preventDefault()}
            className="h-8 cursor-not-allowed rounded-full px-3.5 text-sm font-semibold text-text-muted/70"
          >
            3D
          </button>
        </TooltipTrigger>
        <TooltipContent>Wkrótce</TooltipContent>
      </Tooltip>
    </div>
  )
}
