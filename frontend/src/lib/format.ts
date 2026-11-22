import { locale } from './i18n'

/** Powierzchnia w ha po polsku, 2 miejsca po przecinku: 5,01 / 0,58 (pole do wpisania, liczba bez jednostki). */
export const formatHa = (v: number) => v.toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/**
 * F12/F13: powierzchnia z jednostką – JEDNA funkcja dla całego UI: od 0,1 ha „0,58 ha” (2 miejsca po przecinku),
 * poniżej 0,1 ha w m² zaokrąglonych do 10 („850 m²”).
 */
export function formatArea(ha: number): string {
  if (!Number.isFinite(ha)) return ''
  if (ha < 0.1) return `${(Math.round((ha * 10_000) / 10) * 10).toLocaleString(locale())} m²`
  return `${formatHa(ha)} ha`
}

export const formatNum = (v: number, digits = 1) =>
  v.toLocaleString(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits })

/** „+1,2” / „−3,4” – prawdziwy znak minus. */
/** Polska odmiana po liczbie: 1 działka · 2–4 działki · 5+ działek (12–14 → działek). */
export function plForm(n: number, one: string, few: string, many: string): string {
  const a = Math.abs(n)
  if (a === 1) return one
  const d = a % 10
  const h = a % 100
  return d >= 2 && d <= 4 && (h < 12 || h > 14) ? few : many
}

export const formatSigned = (v: number, digits = 1) =>
  `${v > 0 ? '+' : v < 0 ? '−' : ''}${formatNum(Math.abs(v), digits)}`

/**
 * F12: bilans wody (opad minus parowanie) słowami – ujemny = „zabrakło 120 mm”, dodatni = „+35 mm”, nigdy
 * „zostało −120 mm”. Zwraca klucz tłumaczenia i zmienne (`t(...balanceText(mm))`).
 */
export function balanceText(mm: number): [string, Record<string, string>] {
  const n = formatNum(Math.abs(mm), 0)
  if (Math.round(mm) < 0) return ['zabrakło {n} mm', { n }]
  if (Math.round(mm) > 0) return ['+{n} mm', { n }]
  return ['0 mm', {}]
}

/** „powiat warszawski zachodni” -> „pow. warszawski zachodni”. */
export const shortCounty = (s: string) => s.replace(/^powiat\s+/i, 'pow. ')

export const formatDatePl = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { day: '2-digit', month: '2-digit', year: 'numeric' })

export const weekdayShort = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { weekday: 'short' }).replace('.', '')

/** „20.06” – dzień i miesiąc bez roku. */
export const formatDayMonth = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { day: '2-digit', month: '2-digit' })

/** Dzień i miesiąc słownie: „1 marca” (pl) / „1 March” (en). */
export const formatDayLong = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { day: 'numeric', month: 'long' })

/** Udział 0–1 jako procent: 0,4 -> „40%”. */
export const formatShare = (v: number) => `${Math.round(v * 100)}%`

/**
 * Kwota po polsku, zaokrąglona do 100 zł: „7 900 zł”, „12 400 zł” – spacja (twarda) także w liczbach 4-cyfrowych
 * (Intl dla pl-PL grupuje dopiero od 10 000).
 */
export function formatZl(v: number, step = 100): string {
  const r = Math.round(v / step) * step
  const sign = r < 0 ? '−' : ''
  return `${sign}${String(Math.abs(r)).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0')}\u00a0zł`
}
