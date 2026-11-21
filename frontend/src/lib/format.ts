import { locale } from './i18n'

/** Powierzchnia w ha po polsku: 5,01 / 0,5822. */
export const formatHa = (v: number) =>
  v.toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: v < 1 ? 4 : 2 })

export const formatNum = (v: number, digits = 1) =>
  v.toLocaleString(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits })

/** „+1,2” / „−3,4” – prawdziwy znak minus. */
export const formatSigned = (v: number, digits = 1) =>
  `${v > 0 ? '+' : v < 0 ? '−' : ''}${formatNum(Math.abs(v), digits)}`

/** „powiat warszawski zachodni” -> „pow. warszawski zachodni”. */
export const shortCounty = (s: string) => s.replace(/^powiat\s+/i, 'pow. ')

export const formatDatePl = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { day: '2-digit', month: '2-digit', year: 'numeric' })

export const weekdayShort = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { weekday: 'short' }).replace('.', '')

/** „20.06” – dzień i miesiąc bez roku. */
export const formatDayMonth = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString(locale(), { day: '2-digit', month: '2-digit' })

/** Udział 0–1 jako procent: 0,4 -> „40%”. */
export const formatShare = (v: number) => `${Math.round(v * 100)}%`
