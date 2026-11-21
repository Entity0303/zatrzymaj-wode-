import type { CropId } from '@/api/types'
import { CROPS } from './crops'
import { minAnalysisIso, todayIso } from './dates'

/**
 * Stan aplikacji w adresie (link do udostępnienia, jury: wszystko 1 klik od wejścia):
 * ?dzialka=<id lub „obręb numer”>&uprawa=<CropId>&data=RRRR-MM-DD&przedplon=<CropId | nie_wiem>&widok=paszport
 * Otwarcie takiego linku od razu wyszukuje działkę i liczy analizę. Inne parametry (np. ?dane=przykladowe)
 * zostają nietknięte.
 */
export type LinkState = {
  dzialka: string | null
  uprawa: CropId | null
  data: string | null
  przedplon: string | null
  /** 'paszport' = po analizie od razu otwórz paszport wodny */
  widok: 'paszport' | null
}

const P = { dzialka: 'dzialka', uprawa: 'uprawa', data: 'data', przedplon: 'przedplon', widok: 'widok' } as const

const isCrop = (v: string | null): v is CropId => !!v && CROPS.some((c) => c.id === v)

/** Data z linku tylko w dozwolonym zakresie (dziś − 10 lat … dziś), inaczej ignorowana. */
function validDate(v: string | null): string | null {
  if (!v || !/^\d{4}-\d{2}-\d{2}$/.test(v) || Number.isNaN(Date.parse(v))) return null
  return v >= minAnalysisIso() && v <= todayIso() ? v : null
}

export function readLink(search = window.location.search): LinkState {
  const q = new URLSearchParams(search)
  const dzialka = q.get(P.dzialka)?.trim() || null
  const uprawa = q.get(P.uprawa)
  return {
    dzialka,
    uprawa: isCrop(uprawa) ? uprawa : null,
    data: validDate(q.get(P.data)),
    przedplon: q.get(P.przedplon)?.trim() || null,
    widok: q.get(P.widok) === 'paszport' ? 'paszport' : null,
  }
}

function withState(base: string, s: Partial<LinkState>): URL {
  const url = new URL(base)
  for (const k of Object.keys(P) as (keyof typeof P)[]) {
    if (!(k in s)) continue
    const v = s[k]
    if (v) url.searchParams.set(P[k], v)
    else url.searchParams.delete(P[k])
  }
  return url
}

/** Aktualizuje adres w pasku bez przeładowania i bez nowego wpisu w historii. */
export function writeLink(s: Partial<LinkState>) {
  const url = withState(window.location.href, s)
  if (url.href !== window.location.href) window.history.replaceState(window.history.state, '', url)
}

/** Pełny link do udostępnienia: bieżący adres + stan działki. */
export const shareLink = (s: Partial<LinkState>) => withState(window.location.href, s).href

/** Link do analizy na Starcie (bez # strony) – np. z ekranu „Raporty”. */
export function startLink(s: Partial<LinkState>) {
  const url = withState(window.location.href, s)
  url.hash = ''
  return url.href.replace(/#$/, '')
}
