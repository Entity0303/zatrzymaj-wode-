import { useSyncExternalStore } from 'react'
import type { InfraProblem, WaterObjectType } from '@/api/types'

/**
 * „Moje zgłoszenia” (F22): zgłoszenia wysłane w tej przeglądarce, zapamiętane w localStorage – bez kont i bez
 * danych osobowych. To tylko lista na urządzeniu: usunięcie z listy nie usuwa zgłoszenia z serwera.
 */
export type MyReport = {
  /** id z odpowiedzi serwera (gdy było) – po nim wyróżniamy pinezkę na mapie */
  id: string | null
  /** klucz pozycji na liście (id albo czas zapisu) */
  key: string
  object_type: WaterObjectType
  problem: InfraProblem
  description: string | null
  lon: number
  lat: number
  /** data wysłania, ISO */
  created: string
}

const KEY = 'wodoskop.moje-zgloszenia.v1'
const EMPTY: MyReport[] = []
let cache: MyReport[] | null = null
const listeners = new Set<() => void>()

function read(): MyReport[] {
  if (cache) return cache
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    cache = Array.isArray(raw)
      ? (raw as MyReport[]).filter((r) => r && typeof r.key === 'string' && Number.isFinite(r.lon) && Number.isFinite(r.lat) && typeof r.created === 'string')
      : EMPTY
  } catch {
    cache = EMPTY
  }
  return cache
}

function write(list: MyReport[]) {
  cache = list
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    // brak dostępu do pamięci przeglądarki – lista działa do zamknięcia karty
  }
  listeners.forEach((l) => l())
}

/** Nowe zgłoszenie na górę listy. */
export function addMyReport(r: Omit<MyReport, 'key'>) {
  write([{ ...r, key: r.id ?? 'local-' + Date.now() }, ...read().filter((x) => !r.id || x.id !== r.id)])
}

/** Usuwa tylko z listy na tym urządzeniu. */
export function removeMyReport(key: string) {
  write(read().filter((r) => r.key !== key))
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}

/** Lista od najnowszego; odświeża się po dodaniu / usunięciu. */
export function useMyReports(): MyReport[] {
  return useSyncExternalStore(subscribe, read, () => EMPTY)
}
