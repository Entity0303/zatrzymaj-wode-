import { useEffect, useRef, useState } from 'react'
import type { Forecast } from '@/api/types'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDatePl, formatNum, weekdayShort } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { WeatherIcon } from './WeatherIcon'

/** F26: dzień „suchy i gorący” – bez opadu (< 1 mm) i co najmniej 25°C – wyróżniony w prognozie. */
const HOT_C = 25
const DRY_MM = 1

/**
 * Pogoda teraz (SPEC 4.2, 14): ikona, temperatura, opis – Open-Meteo dla działki lub środka mapy.
 * F26: po najechaniu (komputer) albo kliknięciu (telefon) rozwija się panel „Prognoza na 7 dni” – z tej samej
 * odpowiedzi /api/forecast co „pogoda teraz” (bez nowych zapytań przy najechaniu). Zamyka się po zjechaniu myszą,
 * kliknięciu obok albo Esc.
 */
export function WeatherWidget({
  forecast,
  loading,
  where,
  compact,
  bare,
  historical,
  risk,
}: {
  forecast: Forecast | null
  loading: boolean
  /** błąd pobrania – widżet i tak znika, gdy brak pogody (zostaje w typie dla zgodności wywołań) */
  error?: boolean
  where: string
  compact?: boolean
  /** bez własnego tła i cienia – w grupie górnego paska */
  bare?: boolean
  /** F-MASTER B2: data analizy w przeszłości – pogoda jest dzisiejsza, nie z dnia analizy (szary dopisek) */
  historical?: boolean
  /** F26: zdanie o ryzyku na 7 dni z analizy (już przetłumaczone), np. „Według prognozy wody wystarczy na ok. 7 dni” */
  risk?: string | null
}) {
  const { t } = useLang()
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!open) return
    const outside = (e: PointerEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', esc)
    }
  }, [open])
  useEffect(() => () => void (closeTimer.current && clearTimeout(closeTimer.current)), [])

  const now = forecast?.teraz
  // brak pogody (np. /api/forecast → 502, gdy pogody dla środka mapy nie ma w cache) – element znika bez komunikatu;
  // pokazuje się dopiero, gdy pogoda przyjdzie (bez migania szkieletu przy każdym przesunięciu mapy)
  if (!now) return null
  const label = t('Pogoda teraz {where}: {temp}, {opis}. Źródło: Open-Meteo.', {
    where,
    temp: now.temperatura === null ? t('brak temperatury') : `${Math.round(now.temperatura)}°C`,
    opis: t(now.opis),
  })
  const days = forecast?.dni.slice(0, 7) ?? []
  const hasEvap = days.some((d) => d.parowanie_mm != null)
  const temp = (v: number | null) => (v === null ? '—' : `${Math.round(v)}°`)
  // mysz: otwórz od razu, zamknij z krótkim opóźnieniem (przejście z przycisku na panel); dotyk – tylko kliknięcie
  const enter = (e: React.PointerEvent) => {
    if (e.pointerType !== 'mouse') return
    if (closeTimer.current) clearTimeout(closeTimer.current)
    setOpen(true)
  }
  const leave = (e: React.PointerEvent) => {
    if (e.pointerType !== 'mouse') return
    closeTimer.current = setTimeout(() => setOpen(false), 200)
  }

  return (
    <div ref={box} className="relative shrink-0" onPointerEnter={enter} onPointerLeave={leave}>
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface px-4 shadow-float',
          compact && 'h-11 border px-3 shadow-none',
          bare && 'rounded-none bg-transparent shadow-none',
        )}
      >
        {loading && !now ? (
          <>
            <Skeleton className="size-6 rounded-full bg-surface-2" />
            <Skeleton className="h-4 w-20 bg-surface-2" />
          </>
        ) : (
          <>
            <WeatherIcon icon={now.ikona} night={!now.dzien} className="size-6" />
            <span className="tabular text-base font-semibold">{now.temperatura === null ? '—' : `${Math.round(now.temperatura)}°C`}</span>
            {!compact && !historical && <span className="hidden max-w-36 truncate text-sm text-text-muted xl:inline">{t(now.opis)}</span>}
            {historical && (
              <span className={cn('text-left text-xs leading-4 text-text-muted', compact ? 'hidden' : 'max-w-40')}>{t('pogoda dziś – nie dotyczy daty analizy')}</span>
            )}
          </>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label={t('Prognoza na 7 dni')}
          className="absolute top-full right-0 z-[1300] mt-2 w-[min(23rem,calc(100vw-1.5rem))] rounded-xl border bg-surface p-3 text-left shadow-float"
        >
          <p className="font-display text-base leading-6 font-semibold">{t('Prognoza na 7 dni')}</p>
          <p className="text-sm leading-5 text-text-muted">
            {t(now.opis)} · {where}
          </p>
          {historical && <p className="mt-1.5 rounded-md bg-amber-soft px-2.5 py-1.5 text-sm leading-5">{t('Prognoza dotyczy dziś – nie daty analizy')}</p>}
          {days.length === 0 ? (
            <p className="mt-2 text-sm leading-5 text-text-muted">{t('Brak prognozy dla tego miejsca')}</p>
          ) : (
            <>
              <div className="tabular mt-2 flex items-center gap-2 px-1.5 text-xs leading-4 text-text-muted" aria-hidden>
                <span className="min-w-0 flex-1" />
                <span className="w-[4.5rem] text-right">{t('min / max')}</span>
                <span className="w-14 text-right text-water">{t('opad')}</span>
                {hasEvap && <span className="w-14 text-right text-earth">{t('parowanie')}</span>}
              </div>
              <ul className="mt-0.5">
                {days.map((d) => {
                  const hot = d.temp_max != null && d.temp_max >= HOT_C && (d.opad_mm ?? 0) < DRY_MM
                  return (
                    <li
                      key={d.data}
                      title={hot ? t('Bez opadu i gorąco – gleba szybko traci wodę') : undefined}
                      className={cn('tabular flex min-h-9 items-center gap-2 rounded-md px-1.5 text-sm leading-5', hot && 'bg-amber-soft font-medium')}
                    >
                      <span className="flex min-w-0 flex-1 items-center gap-2">
                        <WeatherIcon icon={d.ikona} className="size-5 shrink-0" />
                        <span className="truncate">
                          <span className="font-semibold capitalize">{weekdayShort(d.data)}</span> {formatDatePl(d.data).slice(0, 5)}
                        </span>
                      </span>
                      <span className="w-[4.5rem] text-right whitespace-nowrap">
                        {temp(d.temp_min)} / <b>{temp(d.temp_max)}</b>
                      </span>
                      <span className="w-14 text-right whitespace-nowrap">{d.opad_mm == null ? '—' : `${formatNum(d.opad_mm, 1)} mm`}</span>
                      {hasEvap && <span className="w-14 text-right whitespace-nowrap">{d.parowanie_mm == null ? '—' : `${formatNum(d.parowanie_mm, 1)} mm`}</span>}
                    </li>
                  )
                })}
              </ul>
              {days.some((d) => d.temp_max != null && d.temp_max >= HOT_C && (d.opad_mm ?? 0) < DRY_MM) && (
                <p className="mt-1 text-xs leading-4 text-text-muted">{t('Wyróżnione: dni bez opadu z temperaturą od 25°C.')}</p>
              )}
            </>
          )}
          {risk && !historical && <p className="mt-2 border-t pt-2 text-sm leading-5">{risk}</p>}
          <p className="mt-1.5 text-xs leading-4 text-text-muted">{t('Źródło: Open-Meteo')}</p>
        </div>
      )}
    </div>
  )
}
