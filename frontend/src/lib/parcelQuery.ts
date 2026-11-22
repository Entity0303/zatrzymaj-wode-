/**
 * F12: normalizacja tego, co rolnik / jury wpisze albo wklei w wyszukiwarkę, zanim pójdzie do /api/search.
 * Sprawdzone na żywo (22.11.2026) – backend rozumie: pełny identyfikator (także ze spacjami), „obręb numer”
 * (dowolna wielkość liter), nazwę miejscowości. NIE rozumie (dlatego poprawiamy tutaj): przecinka zamiast kropki
 * w identyfikatorze, myślnika zamiast ukośnika w numerze, „gmina, obręb numer” (zwraca samą gminę).
 *
 * - tabulatory / nowe linie / twarde spacje z wklejki → spacja, spacje zwielokrotnione i na końcach – usunięte;
 * - prefiks „dz.”, „działka”, „nr”, „numer” – usunięty;
 * - identyfikator `TTTTTT_R.OOOO.NUMER`: bez spacji, przecinki → kropki, „-” / „\” w numerze → „/”, litery w numerze
 *   (np. arkusz „AR_1”) wielkie;
 * - „obręb 6 - 1” / „obręb 6\1” → „obręb 6/1”;
 * - „gmina, obręb 6/1” → „obręb 6/1” (backend szuka obrębu po nazwie; gminy jako filtra jeszcze nie przyjmuje).
 */
export function normalizeParcelQuery(raw: string): string {
  let q = raw
    .replace(/[\t\r\n ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  q = q.replace(/^(?:dz\.?|działka|dzialka|działki|nr\.?|numer)(?:\s*nr\.?)?\s*:?\s*/i, '').trim()

  // pełny identyfikator działki (TERYT obrębu + numer)
  const compact = q.replace(/\s+/g, '').replace(/,/g, '.')
  const id = compact.match(/^(\d{6}_\d)\.(\d{4})\.(.+)$/)
  if (id) return `${id[1]}.${id[2]}.${id[3].replace(/[-\\]/g, '/').toUpperCase()}`

  // „obręb numer”: ukośnik ze spacjami / myślnik / odwrotny ukośnik między cyframi na końcu
  q = q.replace(/(\d+)\s*[-\\/]\s*(\d+)\s*$/, '$1/$2')

  // „gmina, obręb numer” → „obręb numer”; „obręb, numer” → „obręb numer”
  if (q.includes(',')) {
    const parts = q.split(',').map((p) => p.trim()).filter(Boolean)
    const last = parts[parts.length - 1] ?? ''
    if (/\D\s+\d[\d/]*\s*$/.test(last)) q = last
    else if (/^\d[\d/]*$/.test(last) && parts.length >= 2) q = `${parts[parts.length - 2]} ${last}`
  }
  return q
}
