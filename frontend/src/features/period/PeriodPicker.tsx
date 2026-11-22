import { CalendarRange, Check, ChevronDown, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { minAnalysisIso, todayIso } from '@/lib/dates'
import { useLang } from '@/lib/i18n'
import { customRange, PERIOD_OPTIONS, periodShortLabel, type PeriodToken } from '@/lib/period'
import { cn } from '@/lib/utils'

/**
 * „Okres” (F3) przy dacie analizy: gotowe okresy (ostatnie 30 dni, od siewu – tylko z uprawą, sezon)
 * albo własny zakres od–do (natywne pola daty, bez nowej biblioteki). Wybór trafia do zapytania analizy
 * (`period=` / `date_from` + `date_to`) i do adresu (`?okres=`). Wynik pokazuje karta „Okres”.
 */
export function PeriodPicker({
  value,
  onChange,
  hasCrop,
  asOf,
  bare,
  align = 'right',
}: {
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
  const [to, setTo] = useState(range?.to ?? asOf)

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
  const customOk = !!customRange(from && to ? `${from}_${to}` : null)
  const label = value ? periodShortLabel(value) : t('Okres')

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
        title={t('Podsumowanie wybranego okresu: ile spadło, ile wyparowało')}
        className={cn(
          'flex h-11 max-w-[220px] items-center gap-1.5 rounded-full px-3 text-sm font-medium',
          bare ? 'hover:bg-surface-2' : 'border bg-surface shadow-card hover:bg-surface-2',
          value && 'text-brand',
        )}
      >
        <CalendarRange className="size-4 shrink-0 text-brand" aria-hidden />
        <span className="truncate">{value ? t(label) : label}</span>
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
                  min={minAnalysisIso()}
                  max={to || todayIso()}
                  onChange={(e) => setFrom(e.target.value)}
                  className="mt-0.5 h-11 w-full rounded-md border bg-surface-2 px-2 text-sm text-text"
                />
              </label>
              <label className="text-xs leading-4 text-text-muted">
                {t('do')}
                <input
                  type="date"
                  value={to}
                  min={from || minAnalysisIso()}
                  max={todayIso()}
                  onChange={(e) => setTo(e.target.value)}
                  className="mt-0.5 h-11 w-full rounded-md border bg-surface-2 px-2 text-sm text-text"
                />
              </label>
            </div>
            <button
              type="button"
              disabled={!customOk}
              onClick={() => pick(`${from}_${to}`)}
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
              <X className="size-4" aria-hidden /> {t('Bez okresu')}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
