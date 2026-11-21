import { useCallback, useEffect, useState } from 'react'
import type { AnalysisResponse, CropId, StatusLevel } from '@/api/types'

/**
 * Pamięć przeglądarki (localStorage) – bez kont i bez danych osobowych (SPEC 3, 10).
 * Każdy odczyt/zapis w try/catch: tryb prywatny lub pełna pamięć nie psują aplikacji.
 * Zmiana w jednym komponencie odświeża pozostałe (zdarzenie `zw-storage`).
 */
const EVENT = 'zw-storage'

export function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeStored<T>(key: string, value: T) {
  try {
    if (value === undefined) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* tryb prywatny / pełna pamięć – zostaje tylko w stanie */
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: key }))
}

export function useStored<T>(key: string, fallback: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => readStored(key, fallback))
  useEffect(() => {
    const on = (e: Event) => {
      const k = (e as CustomEvent<string>).detail
      if (!k || k === key) setValue(readStored(key, fallback))
    }
    const onOther = (e: StorageEvent) => e.key === key && setValue(readStored(key, fallback))
    window.addEventListener(EVENT, on)
    window.addEventListener('storage', onOther)
    return () => {
      window.removeEventListener(EVENT, on)
      window.removeEventListener('storage', onOther)
    }
    // fallback celowo poza zależnościami (stała wartość domyślna)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  const set = useCallback((v: T) => {
    setValue(v)
    writeStored(key, v)
  }, [key])
  return [value, set]
}

// ── ustawienia ───────────────────────────────────────────────────────────────────────────────
export type Settings = { baseMap: 'orto' | 'osm'; mode: 'rolnik' | 'doradca' }
export const SETTINGS_KEY = 'zw.settings.v1'
export const DEFAULT_SETTINGS: Settings = { baseMap: 'orto', mode: 'rolnik' }
export const useSettings = () => {
  const [s, set] = useStored<Settings>(SETTINGS_KEY, DEFAULT_SETTINGS)
  return [{ ...DEFAULT_SETTINGS, ...s }, set] as const
}

// ── historia analiz (ekran „Raporty”, stan w „Moje działki”) ─────────────────────────────────
export type AnalysisRecord = {
  parcel_id: string
  numer: string
  gmina: string
  obreb: string
  powierzchnia_ha: number
  crop: CropId
  date: string
  level: StatusLevel
  score: number | null
  headline: string
  historical: boolean
  saved_at: string
}
export const HISTORY_KEY = 'zw.analyses.v1'
const HISTORY_MAX = 50

/** Zapamiętuje wynik analizy (ta sama działka + uprawa + data = jeden wpis, najnowszy na górze). */
export function rememberAnalysis(a: AnalysisResponse) {
  const rec: AnalysisRecord = {
    parcel_id: a.parcel.id,
    numer: a.parcel.numer,
    gmina: a.parcel.gmina,
    obreb: a.parcel.obreb,
    powierzchnia_ha: a.parcel.powierzchnia_ha,
    crop: a.crop,
    date: a.analysis_date,
    level: a.status.level,
    score: a.status.score ?? null,
    headline: a.status.headline,
    historical: a.historical,
    saved_at: new Date().toISOString(),
  }
  const list = readStored<AnalysisRecord[]>(HISTORY_KEY, []).filter(
    (r) => !(r.parcel_id === rec.parcel_id && r.crop === rec.crop && r.date === rec.date),
  )
  writeStored(HISTORY_KEY, [rec, ...list].slice(0, HISTORY_MAX))
}

export const useHistory = () => useStored<AnalysisRecord[]>(HISTORY_KEY, [])

export const SAVED_KEY = 'zw.saved-parcels.v1'
