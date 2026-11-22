import type { PeriodPreset } from '@/api/types'
import { formatDatePl } from './format'
import { todayIso } from './dates'

/**
 * Okres analizy (F3, F8) jako krótki znacznik – ten sam w stanie aplikacji i w zapytaniu:
 * `30d` · `od_siewu` · `sezon` · `RRRR-MM-DD_RRRR-MM-DD` (własny zakres od–do).
 * W adresie: gotowy okres `?okres=30d`, własny zakres `?od=RRRR-MM-DD&do=RRRR-MM-DD` (lib/deepLink.ts).
 * Do zapytania: `period=30d|since_sowing|season` albo `date_from=&date_to=` (backend A9b, analysis/period.py).
 * Bez okresu backend nie liczy podsumowania okresu – paszport pokazuje bilans od początku sezonu uprawy.
 */
export type PeriodToken = string

const PRESETS: Record<string, PeriodPreset> = { '30d': '30d', od_siewu: 'since_sowing', sezon: 'season' }

/** Tylko okresy, które backend obsługuje (`period=30d|since_sowing|season`); inne – „Własny zakres”. */
export const PERIOD_OPTIONS: { token: PeriodToken; label: string; hint: string; needsCrop?: boolean }[] = [
  { token: '30d', label: 'Ostatnie 30 dni', hint: 'ile spadło i wyparowało przez ostatni miesiąc' },
  { token: 'od_siewu', label: 'Od siewu', hint: 'od siewu wybranej uprawy do daty analizy', needsCrop: true },
  { token: 'sezon', label: 'Sezon (1.04–30.09)', hint: 'sezon wegetacyjny w roku daty analizy' },
]

const isIso = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v))

/**
 * Najwcześniejszy początek własnego zakresu dla danej daty analizy – backend pobiera pogodę od 1 sierpnia
 * (rok daty analizy − 12) (`history_range`); wcześniej nie ma z czego liczyć.
 */
export const periodMinIso = (asOf: string) => `${Number(asOf.slice(0, 4)) - 12}-08-01`

/** Ostatni dzień, który może zakończyć zakres: data analizy, ale nie później niż dziś. */
export const periodMaxIso = (asOf: string) => (asOf < todayIso() ? asOf : todayIso())

/**
 * Błąd własnego zakresu po polsku (null = poprawny). Zasady backendu: od < do (F8), koniec ≤ data analizy,
 * nie w przyszłość, początek nie wcześniej niż pobrana pogoda.
 */
export function rangeError(from: string, to: string, asOf: string): string | null {
  if (!from || !to) return 'Podaj obie daty: od i do.'
  if (!isIso(from) || !isIso(to)) return 'Nieprawidłowa data – wpisz dzień, miesiąc i rok.'
  if (to > todayIso()) return 'Data „do” nie może być w przyszłości.'
  if (to > asOf) return `Data „do” nie może być późniejsza niż data analizy (${formatDatePl(asOf)}).`
  if (from >= to) return 'Data „od” musi być wcześniejsza niż data „do”.'
  if (from < periodMinIso(asOf)) return `Najwcześniej od ${formatDatePl(periodMinIso(asOf))} – starszej pogody nie pobieramy.`
  return null
}

/** Własny zakres ze znacznika (format i kolejność; granice daty analizy sprawdza `rangeError`). */
export function customRange(token: PeriodToken | null | undefined): { from: string; to: string } | null {
  const m = token?.match(/^(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})$/)
  if (!m || !isIso(m[1]) || !isIso(m[2])) return null
  const [from, to] = [m[1], m[2]]
  return from < to && to <= todayIso() ? { from, to } : null
}

/** Znacznik z adresu albo null, gdy nieznany / błędny. */
export function parsePeriod(v: string | null): PeriodToken | null {
  if (!v) return null
  if (v in PRESETS) return v
  return customRange(v) ? v : null
}

/**
 * Parametry zapytania analizy / raportu dla okresu. Własny zakres kończący się po dacie analizy (np. data analizy
 * zmieniona na wcześniejszą) – koniec przycięty do daty analizy; pusty po przycięciu – bez okresu.
 */
export function periodParams(token: PeriodToken | null | undefined, asOf?: string): Record<string, string> {
  if (!token) return {}
  if (token in PRESETS) return { period: PRESETS[token] }
  const r = customRange(token)
  if (!r) return {}
  const to = asOf && r.to > asOf ? asOf : r.to
  return r.from < to ? { date_from: r.from, date_to: to } : {}
}

/** Krótki opis na przycisku („Ostatnie 30 dni”, „1.05–30.06.2026”). */
export function periodShortLabel(token: PeriodToken): string {
  const opt = PERIOD_OPTIONS.find((o) => o.token === token)
  if (opt) return opt.label
  const r = customRange(token)
  if (!r) return ''
  const d = (iso: string, year: boolean) => {
    const [y, m, dd] = iso.split('-')
    return `${Number(dd)}.${m}${year ? `.${y}` : ''}`
  }
  return `${d(r.from, r.from.slice(0, 4) !== r.to.slice(0, 4))}–${d(r.to, true)}`
}
