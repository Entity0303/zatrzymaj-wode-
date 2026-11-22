import { House, Loader2, MapPin, Search, SquareDashed, TriangleAlert, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '@/api/client'
import type { Parcel, SearchResponse, SearchResult } from '@/api/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatHa, plForm } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'
import { mockSearchAddress, mockVariant } from '@/mocks/useMockAnalysis'

/**
 * Wyszukiwarka (SPEC 4.2, 14; A5c): jedno pole – identyfikator, „obręb numer” albo nazwa miejscowości.
 * Podpowiedzi z GET /api/search po ~300 ms przerwy (min. 2 znaki, poprzednie zapytanie anulowane), w grupach
 * „Działki”, „Adresy” (F3: adres → działka spod punktu) i „Miejscowości”; „Szukam…”, podpowiedź przy braku wyników, ostrzeżenia źródeł w dymku, atrybucja.
 * Lista kandydatów z mapy (kilka działek o tym numerze) – jak dotąd.
 */
export function SearchBar({
  loading,
  error,
  candidates = [],
  total = 0,
  onSearch,
  onPick,
  onPickResult,
  onDismiss,
  selected,
  placeholder,
  trailing,
  className,
}: {
  /** przycisk w prawej części pola (np. „Moja lokalizacja”) */
  trailing?: ReactNode
  /** trwa wczytywanie działki (po wyborze) */
  loading: boolean
  error: string | null
  candidates?: Parcel[]
  total?: number
  /** Enter bez podpowiedzi – stare wyszukiwanie numeru */
  onSearch: (q: string) => void
  onPick: (p: Parcel) => void
  /** wybór z podpowiedzi /api/search: działka albo miejscowość */
  onPickResult: (r: SearchResult) => void
  onDismiss: () => void
  /** wybrana działka jako tekst („Szczytno 112/11”) – wpisywany przy każdej zmianie działki */
  selected?: string | null
  placeholder?: string
  className?: string
}) {
  const { t } = useLang()
  const [q, setQ] = useState('')
  const [resp, setResp] = useState<SearchResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const typed = useRef(false)

  // nowa działka (z linku, przykładu, kliknięcia na mapie) = jej nazwa w polu
  const [shown, setShown] = useState<string | null>(null)
  if (selected && selected !== shown) {
    setShown(selected)
    setQ(selected)
    setOpen(false)
  }

  // podpowiedzi: debounce 300 ms, tylko po wpisywaniu (nie po podstawieniu nazwy wybranej działki)
  useEffect(() => {
    const query = q.trim()
    if (!typed.current || query.length < 2) {
      setResp(null)
      setBusy(false)
      return
    }
    const ctrl = new AbortController()
    setBusy(true)
    const id = window.setTimeout(() => {
      // mock F3 (?dane=przykladowe&wariant=adres): działka + adresy z search.address.sample.json
      const request = import.meta.env.DEV && mockVariant('adres') ? mockSearchAddress() : api.search(query, ctrl.signal)
      request.then(
        (r) => {
          setResp(r)
          setActive(-1)
          setOpen(true)
          setBusy(false)
        },
        (e) => {
          if ((e as Error).name !== 'AbortError') setBusy(false)
        },
      )
    }, 300)
    return () => {
      window.clearTimeout(id)
      ctrl.abort()
    }
  }, [q])

  // Start: kursor w wyszukiwarce (SPEC 13) – tylko na komputerze
  useEffect(() => {
    if (window.matchMedia('(min-width: 768px)').matches) inputRef.current?.focus()
  }, [])

  const results = resp?.results ?? []
  const parcels = results.filter((r) => r.kind === 'parcel')
  const addresses = results.filter((r) => r.kind === 'address')
  const places = results.filter((r) => r.kind === 'place')
  const flat = [...parcels, ...addresses, ...places]
  const showCandidates = candidates.length > 0 && !open
  const showList = open && !!resp && q.trim().length >= 2

  const pick = (r: SearchResult) => {
    setOpen(false)
    typed.current = false
    onPickResult(r)
  }

  const row = (r: SearchResult, i: number) => (
    <li key={r.id} role="option" aria-selected={i === active}>
      <button
        type="button"
        onMouseEnter={() => setActive(i)}
        onClick={() => pick(r)}
        className={cn('flex min-h-11 w-full items-center gap-3 px-4 py-2 text-left', i === active && 'bg-ok-soft')}
      >
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-sage-soft text-brand">
          {r.kind === 'parcel' ? (
            <SquareDashed className="size-4" aria-hidden />
          ) : r.kind === 'address' ? (
            <House className="size-4" aria-hidden />
          ) : (
            <MapPin className="size-4" aria-hidden />
          )}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm leading-5">{r.label}</span>
        {r.kind === 'parcel' && r.area_ha != null && <span className="tabular shrink-0 text-sm text-text-muted">{formatHa(r.area_ha)} ha</span>}
        {r.kind === 'place' && r.type_label && (
          <span className="shrink-0 rounded-full bg-surface-2 px-2 py-0.5 text-xs text-text-muted">{r.type_label}</span>
        )}
      </button>
    </li>
  )

  return (
    <div className={cn('relative', className)}>
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          if (showList && active >= 0) return pick(flat[active])
          if (showList && flat.length === 1) return pick(flat[0])
          if (!q.trim()) return
          setOpen(false)
          onSearch(q.trim())
        }}
        className="relative"
      >
        <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-text-muted" aria-hidden />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => {
            typed.current = true
            setQ(e.target.value)
          }}
          onFocus={() => resp && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setOpen(false)
              onDismiss()
            }
            if (!showList || !flat.length) return
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setActive((a) => Math.min(a + 1, flat.length - 1))
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActive((a) => Math.max(a - 1, 0))
            }
          }}
          data-parcel-search
          aria-label={t('Numer działki albo nazwa miejscowości')}
          aria-expanded={showList}
          aria-autocomplete="list"
          aria-invalid={!!error || undefined}
          enterKeyHint="search"
          autoComplete="off"
          placeholder={placeholder ?? t('Numer działki albo miejscowość, np. Szczytno 112/11 lub Tczów')}
          className={cn(
            'h-12 w-full rounded-full border border-transparent bg-surface pl-12 text-base shadow-float outline-none placeholder:text-sm placeholder:text-text-muted/80',
            trailing ? 'pr-[5.5rem]' : 'pr-12',
            'focus-visible:border-brand focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand',
            error && 'border-danger/60',
          )}
        />
        <span className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center">
          {loading || busy ? (
            <Loader2 className="m-2.5 size-5 animate-spin text-brand" aria-label={t('Szukam')} />
          ) : q ? (
            <button
              type="button"
              aria-label={t('Wyczyść')}
              onClick={() => {
                setQ('')
                setResp(null)
                inputRef.current?.focus()
              }}
              className="flex size-9 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
            >
              <X className="size-5" />
            </button>
          ) : null}
          {trailing}
        </span>
      </form>

      {busy && !showList && q.trim().length >= 2 && (
        <p className="absolute top-full left-4 z-10 mt-1.5 rounded-full bg-surface px-3 py-1 text-sm text-text-muted shadow-card">{t('Szukam…')}</p>
      )}

      {error && !showList && !showCandidates && !busy && (
        <p className="absolute top-full left-4 z-10 mt-1.5 max-w-[calc(100vw-48px)] rounded-xl bg-surface px-3 py-1 text-sm text-danger shadow-card md:whitespace-nowrap" role="alert">
          {error}
        </p>
      )}

      {showList && (
        <div className="absolute inset-x-0 top-full z-10 mt-2 overflow-hidden rounded-xl bg-surface shadow-float">
          <div className="max-h-[55vh] overflow-y-auto py-1" role="listbox" aria-label={t('Podpowiedzi')}>
            {parcels.length > 0 && (
              <>
                <p className="px-4 pt-2 pb-1 text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Działki')}</p>
                <ul>{parcels.map((r, i) => row(r, i))}</ul>
              </>
            )}
            {addresses.length > 0 && (
              <>
                <p className="px-4 pt-2 pb-1 text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Adresy')}</p>
                <ul>{addresses.map((r, i) => row(r, parcels.length + i))}</ul>
              </>
            )}
            {places.length > 0 && (
              <>
                <p className="px-4 pt-2 pb-1 text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Miejscowości')}</p>
                <ul>{places.map((r, i) => row(r, parcels.length + addresses.length + i))}</ul>
              </>
            )}
            {!results.length && <p className="px-4 py-3 text-sm text-text-muted">{resp?.hint ? t(resp.hint) : t('Nic nie znaleziono')}</p>}
          </div>
          {(resp?.truncated || resp?.notices?.length || resp?.attribution) && (
            <div className="flex items-start gap-2 border-t px-4 py-2 text-xs leading-4 text-text-muted">
              {resp?.notices?.length ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span tabIndex={0} className="flex items-center gap-1 text-amber">
                      <TriangleAlert className="size-3.5" aria-hidden /> {t('Nie wszystko sprawdzone')}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-72">{resp.notices.map((n) => t(n)).join(' ')}</TooltipContent>
                </Tooltip>
              ) : null}
              <span className="min-w-0 flex-1">{resp?.truncated && resp.hint ? t(resp.hint) : ''}</span>
              {resp?.attribution && <span className="shrink-0">{resp.attribution}</span>}
            </div>
          )}
        </div>
      )}

      {showCandidates && (
        <div className="absolute inset-x-0 top-full z-10 mt-2 overflow-hidden rounded-xl bg-surface shadow-float">
          <p className="border-b px-4 py-2 text-sm text-text-muted">
            {t(plForm(total, 'Znaleziono {n} działkę – wybierz ją', 'Znaleziono {n} działki – wybierz swoją', 'Znaleziono {n} działek – wybierz swoją'), { n: total })}
            {total > candidates.length && ` ${t('(pokazano {n})', { n: candidates.length })}`}
          </p>
          <ul role="listbox" className="max-h-[50vh] overflow-y-auto py-1">
            {candidates.map((c, i) => (
              <li key={c.id} role="option" aria-selected={false}>
                <button type="button" onClick={() => onPick(c)} className="flex min-h-11 w-full items-center gap-3 px-4 py-2 text-left hover:bg-ok-soft">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-semibold text-white">{i + 1}</span>
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
