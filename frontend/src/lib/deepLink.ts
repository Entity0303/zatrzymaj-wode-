import type { CropId } from '@/api/types'
import { CROPS, HISTORY_UNKNOWN, isHistoryCrop } from './crops'
import { minAnalysisIso, todayIso } from './dates'
import { parsePeriod } from './period'

/**
 * Stan aplikacji w adresie (link do udostępnienia, jury: wszystko 1 klik od wejścia):
 * ?dzialka=<id lub „obręb numer”>&uprawa=<CropId>&data=RRRR-MM-DD&historia=<1–3 uprawy po przecinku, pierwsza = rok temu>&widok=paszport&okres=30d
 * (stary ?przedplon= czytany jako „rok temu”)
 * Otwarcie takiego linku od razu wyszukuje działkę i liczy analizę. Inne parametry (np. ?dane=przykladowe)
 * zostają nietknięte.
 */
export type LinkState = {
  dzialka: string | null
  uprawa: CropId | null
  data: string | null
  /** historia pola: indeks 0 = rok temu, 'nie_wiem' albo crop_id */
  historia: string[]
  /** A5e: plan upraw (do 3 crop_id lub grup) */
  plan: string[]
  /** 'paszport' = po analizie od razu otwórz paszport wodny */
  widok: 'paszport' | null
  /** F3: okres analizy – `30d` · `od_siewu` · `sezon` · `RRRR-MM-DD_RRRR-MM-DD` */
  okres: string | null
}

const P = { dzialka: 'dzialka', uprawa: 'uprawa', data: 'data', historia: 'historia', plan: 'plan', widok: 'widok', okres: 'okres' } as const

const isCrop = (v: string | null): v is CropId => !!v && CROPS.some((c) => c.id === v)

/** Data z linku tylko w dozwolonym zakresie (dziś − 10 lat … dziś), inaczej ignorowana. */
function validDate(v: string | null): string | null {
  if (!v || !/^\d{4}-\d{2}-\d{2}$/.test(v) || Number.isNaN(Date.parse(v))) return null
  return v >= minAnalysisIso() && v <= todayIso() ? v : null
}

/** „zyto,nie_wiem,rzepak” → lista 1–3 znanych upraw; nieznane = „nie wiem”, bez końcowych „nie wiem”. */
function parseHistory(v: string | null): string[] {
  if (!v) return []
  const h = v.split(',').slice(0, 3).map((x) => (isHistoryCrop(x.trim()) ? x.trim() : HISTORY_UNKNOWN))
  while (h.length && h[h.length - 1] === HISTORY_UNKNOWN) h.pop()
  return h
}

export function readLink(search = window.location.search): LinkState {
  const q = new URLSearchParams(search)
  const dzialka = q.get(P.dzialka)?.trim() || null
  const uprawa = q.get(P.uprawa)
  return {
    dzialka,
    uprawa: isCrop(uprawa) ? uprawa : null,
    data: validDate(q.get(P.data)),
    historia: parseHistory(q.get(P.historia) ?? q.get('przedplon')),
    plan: (q.get(P.plan) ?? '')
      .split(',')
      .map((x) => x.trim())
      .filter((x) => /^[a-z_]{2,40}$/.test(x))
      .slice(0, 3),
    widok: q.get(P.widok) === 'paszport' ? 'paszport' : null,
    okres: parsePeriod(q.get(P.okres)),
  }
}

function withState(base: string, s: Partial<LinkState>): URL {
  const url = new URL(base)
  for (const k of Object.keys(P) as (keyof typeof P)[]) {
    if (!(k in s)) continue
    const raw = s[k]
    const v = Array.isArray(raw) ? raw.join(',') : raw
    if (v) url.searchParams.set(P[k], v)
    else url.searchParams.delete(P[k])
    if (k === 'historia') url.searchParams.delete('przedplon')
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
