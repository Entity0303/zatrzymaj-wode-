import { CalendarRange, Check, ChevronDown, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useLang } from '@/lib/i18n'
import { customRange, PERIOD_OPTIONS, periodMaxIso, periodMinIso, periodShortLabel, rangeError, type PeriodToken } from '@/lib/period'
import { cn } from '@/lib/utils'

/**
 * „Okres” (F3) przy dacie analizy: gotowe okresy (ostatnie 30 dni, od siewu – tylko z uprawą, sezon)
 * albo własny zakres od–do (natywne pola daty, bez nowej biblioteki). Wybór trafia do zapytania analizy
 * (`period=` / `date_from` + `date_to`) i do adresu (`?okres=` / `?od=&do=`). Wynik pokazuje karta „Okres”.
 * F8: walidacja własnego zakresu (od < do, koniec ≤ data analizy i nie w przyszłość, początek ≥ pobrana pogoda) –
 * błąd po polsku pod polami; w paszporcie przycisk „Okres: …” (`prefix`, `emptyLabel` – co widać bez okresu).
 */
export function PeriodPicker({
  value,
  onChange,
  hasCrop,
  asOf,
  bare,
  align = 'right',
  prefix,
  emptyLabel,
  disabled,
  wide,
}: {
  /** F-MASTER A2: pole formularza na całą szerokość (karta „Twoja działka”) */
  wide?: boolean
  /** F8: „Okres:” przed opisem (pasek paszportu) */
  prefix?: string
  /** F8: opis, gdy okres nie jest wybrany (np. „od 1.11.2025 – sezon uprawy”) */
  emptyLabel?: string
  /** trwa przeliczanie – bez kolejnej zmiany */
  disabled?: boolean
  value: PeriodToken | null
  onChange: (v: PeriodToken | null) => void
  hasCrop: boolean
  /** data analizy – domyślny koniec własnego zakresu */
  asOf: string
  /** bez tła i cienia – w pigułce górnego paska */
  bare?: boolean
  align?: 'left' | 'right'
}) {
  const { t } = useLang()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const range = customRange(value)
  const [from, setFrom] = useState(range?.from ?? '')
  const [to, setTo] = useState(range?.to ?? periodMaxIso(asOf))
  // błąd pokazujemy po pierwszej próbie albo gdy oba pola są wypełnione
  const [tried, setTried] = useState(false)

  /** otwarcie: pola z bieżącego okresu (albo pusty początek i koniec = data analizy) */
  const toggle = () => {
    if (!open) {
      const r = customRange(value)
      setFrom(r?.from ?? '')
      setTo(r?.to ?? periodMaxIso(asOf))
      setTried(false)
    }
    setOpen((o) => !o)
  }

  // zamknięcie: klik poza okienkiem, Esc
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => !root.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', onDown)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  const pick = (v: PeriodToken | null) => {
    onChange(v)
    setOpen(false)
  }
  const error = rangeError(from, to, asOf)
  const showError = !!error && (tried || (!!from && !!to))
  const applyCustom = () => {
    setTried(true)
    if (!error) pick(`${from}_${to}`)
  }
  // emptyLabel przychodzi już przetłumaczony (zawiera datę)
  const desc = value ? t(periodShortLabel(value)) : (emptyLabel ?? null)
  const label = prefix ? `${t(prefix)} ${desc ?? t('domyślny')}` : (desc ?? t('Okres'))

  return (
    <div ref={root} className={cn('relative', wide && 'w-full')}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={disabled}
        onClick={toggle}
        title={t('Podsumowanie wybranego okresu: opad, parowanie i bilans wody')}
        className={cn(
          'flex h-11 items-center gap-1.5 rounded-full px-3 text-sm font-medium disabled:opacity-60',
          wide ? 'w-full rounded-md border bg-surface-2 text-base hover:bg-surface' : prefix ? 'max-w-[min(340px,100%)]' : 'max-w-[220px]',
          !wide && (bare ? 'hover:bg-surface-2' : 'border bg-surface shadow-card hover:bg-surface-2'),
          value && 'text-brand',
        )}
      >
        <CalendarRange className="size-4 shrink-0 text-brand" aria-hidden />
        <span className={cn('truncate', wide && 'flex-1 text-left')}>{label}</span>
        <ChevronDown className="size-4 shrink-0 text-text-muted" aria-hidden />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label={t('Wybierz okres')}
          className={cn(
            'absolute top-full z-[1700] mt-2 w-[min(320px,calc(100vw-24px))] rounded-xl bg-surface p-2 shadow-float',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          <p className="px-2.5 pt-1 pb-1.5 text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Okres')}</p>
          <ul>
            {PERIOD_OPTIONS.map((o) => {
              const off = o.needsCrop && !hasCrop
              const on = value === o.token
              return (
                <li key={o.token}>
                  <button
                    type="button"
                    disabled={off}
                    onClick={() => pick(o.token)}
                    className={cn('flex min-h-12 w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left hover:bg-surface-2 disabled:opacity-50', on && 'bg-sage-soft')}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm leading-5 font-semibold">{t(o.label)}</span>
                      <span className="block text-sm leading-5 text-text-muted">{t(off ? 'najpierw wybierz uprawę' : o.hint)}</span>
                    </span>
                    {on && <Check className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />}
                  </button>
                </li>
              )
            })}
          </ul>
          <div className="mt-1 border-t px-2.5 pt-2.5 pb-1">
            <p className="text-sm leading-5 font-semibold">{t('Własny zakres')}</p>
            <div className="mt-1.5 grid grid-cols-2 gap-2">
              <label className="text-xs leading-4 text-text-muted">
                {t('od')}
                <input
                  type="date"
                  value={from}
                  min={periodMinIso(asOf)}
                  max={to || periodMaxIso(asOf)}
                  aria-invalid={showError}
                  aria-describedby={showError ? 'period-range-error' : undefined}
                  onChange={(e) => setFrom(e.target.value)}
                  className="mt-0.5 h-11 w-full rounded-md border bg-surface-2 px-2 text-sm text-text"
                />
              </label>
              <label className="text-xs leading-4 text-text-muted">
                {t('do')}
                <input
                  type="date"
                  value={to}
                  min={from || periodMinIso(asOf)}
                  max={periodMaxIso(asOf)}
                  aria-invalid={showError}
                  aria-describedby={showError ? 'period-range-error' : undefined}
                  onChange={(e) => setTo(e.target.value)}
                  className="mt-0.5 h-11 w-full rounded-md border bg-surface-2 px-2 text-sm text-text"
                />
              </label>
            </div>
            {showError && (
              <p id="period-range-error" role="alert" className="mt-1.5 text-sm leading-5 text-danger">
                {t(error!)}
              </p>
            )}
            <button
              type="button"
              disabled={showError}
              onClick={applyCustom}
              className="mt-2 h-11 w-full rounded-md bg-brand-dark text-sm font-semibold text-white hover:bg-brand disabled:opacity-40"
            >
              {t('Pokaż ten okres')}
            </button>
          </div>
          {value && (
            <button
              type="button"
              onClick={() => pick(null)}
              className="mt-1 flex min-h-11 w-full items-center justify-center gap-1.5 rounded-lg text-sm font-medium text-text-muted hover:bg-surface-2"
            >
              <X className="size-4" aria-hidden /> {t(emptyLabel ? 'Wróć do domyślnego' : 'Bez okresu')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
