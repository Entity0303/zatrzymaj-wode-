import { useSyncExternalStore } from 'react'
import type { AnalysisQuery } from '@/api/client'

/**
 * „Moje raporty” (F25): raporty PDF wygenerowane w tej przeglądarce – zapamiętujemy tylko PARAMETRY (działka, data,
 * uprawa, okres…), nie plik. „Pobierz ponownie” generuje raport od nowa z aktualnych danych. localStorage, bez kont.
 */
export type MyPdfReport = {
  key: string
  /** parametry zapytania raportu (bez obrysu narysowanego pola – takich raportów nie zapamiętujemy) */
  params: Pick<AnalysisQuery, 'parcelId' | 'crop' | 'date' | 'cropHistory' | 'area' | 'plannedCrops' | 'period' | 'sowingDate'>
  type: 'short' | 'full'
  numer: string
  obreb: string | null
  gmina: string | null
  /** kiedy wygenerowano, ISO */
  generated: string
}

const KEY = 'wodoskop.moje-raporty.v1'
const MAX = 30
const EMPTY: MyPdfReport[] = []
let cache: MyPdfReport[] | null = null
const listeners = new Set<() => void>()

function read(): MyPdfReport[] {
  if (cache) return cache
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    cache = Array.isArray(raw)
      ? (raw as MyPdfReport[]).filter((r) => r && typeof r.key === 'string' && !!r.params?.parcelId && typeof r.params.date === 'string' && typeof r.generated === 'string')
      : EMPTY
  } catch {
    cache = EMPTY
  }
  return cache
}

function write(list: MyPdfReport[]) {
  cache = list
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    // brak dostępu do pamięci przeglądarki – lista działa do zamknięcia karty
  }
  listeners.forEach((l) => l())
}

/** Nowy raport na górę listy; ten sam (działka, data, uprawa, rodzaj, okres, siew) zastępuje starszy wpis. */
export function addMyPdfReport(r: Omit<MyPdfReport, 'key' | 'generated'>) {
  const p = r.params
  const key = [p.parcelId, p.date, p.crop ?? '', r.type, p.period ?? '', p.sowingDate ?? ''].join('|')
  write([{ ...r, key, generated: new Date().toISOString() }, ...read().filter((x) => x.key !== key)].slice(0, MAX))
}

/** Usuwa tylko z listy na tym urządzeniu. */
export function removeMyPdfReport(key: string) {
  write(read().filter((r) => r.key !== key))
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}

/** Lista od najnowszego; odświeża się po dodaniu / usunięciu. */
export function useMyPdfReports(): MyPdfReport[] {
  return useSyncExternalStore(subscribe, read, () => EMPTY)
}
