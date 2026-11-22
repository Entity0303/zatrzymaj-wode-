/**
 * Stany terenu i spływu liczonych w tle (F23 + dopisek po A23). Pola kolejki (`queue_position`) i komunikat błędu
 * z serwera są opcjonalne – gdy backend ich nie poda, zostają nasze teksty.
 */
export const TERRAIN_PENDING = 'Liczę teren i spływ… (do ok. minuty)'
export const TERRAIN_NODATA = 'Brak danych o terenie – spróbuj za chwilę'

/** Pozycja w kolejce zadań w tle z odpowiedzi „pending” (1 = następne); brak pola = null. */
export function queuePosition(x: unknown): number | null {
  const n = x && typeof x === 'object' ? (x as { queue_position?: unknown }).queue_position : null
  return typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.round(n) : null
}

/**
 * Komunikat błędu z serwera (detail.message) – gdy jest i nie jest techniczny (kod HTTP, nazwa wyjątku), pokazujemy
 * go zamiast własnego zdania; wielka litera na początku.
 */
export function serverMessage(m: string | null | undefined): string | null {
  const s = m?.trim()
  if (!s || /HTTP|\b[45]\d{2}\b|Error|Exception|Traceback/i.test(s)) return null
  return s.charAt(0).toUpperCase() + s.slice(1)
}
