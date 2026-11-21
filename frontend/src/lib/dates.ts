import { locale } from './i18n'

/** Data w strefie lokalnej jako RRRR-MM-DD (toISOString dałby datę UTC). */
export function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export const todayIso = () => isoDate(new Date())

/** Najwcześniejsza data analizy: 10 lat wstecz od dziś. */
export function minAnalysisIso(): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 10)
  return isoDate(d)
}

export function formatDateTimePl(iso: string): string {
  return new Date(iso).toLocaleString(locale(), { dateStyle: 'medium', timeStyle: 'short' })
}
