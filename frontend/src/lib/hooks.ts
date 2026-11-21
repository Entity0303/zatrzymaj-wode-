import { useCallback, useEffect, useState } from 'react'
import type { Parcel } from '@/api/types'

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const on = () => setMatches(mq.matches)
    mq.addEventListener('change', on)
    on()
    return () => mq.removeEventListener('change', on)
  }, [query])
  return matches
}

export const usePrefersReducedMotion = () => useMediaQuery('(prefers-reduced-motion: reduce)')

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  return online
}

/** Zapisana działka – tylko w pamięci przeglądarki (bez kont, bez danych osobowych). */
export type SavedParcel = Pick<Parcel, 'id' | 'numer' | 'gmina' | 'obreb' | 'powierzchnia_ha'> & { zapisano: string }

const KEY = 'zw.saved-parcels.v1'

function load(): SavedParcel[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

export function useSavedParcels() {
  const [saved, setSaved] = useState<SavedParcel[]>(load)
  const persist = (next: SavedParcel[]) => {
    setSaved(next)
    try {
      localStorage.setItem(KEY, JSON.stringify(next))
    } catch {
      /* tryb prywatny / pełna pamięć – trzymamy tylko w stanie */
    }
  }
  const isSaved = useCallback((id: string) => saved.some((p) => p.id === id), [saved])
  const toggle = (p: Parcel) => {
    if (saved.some((s) => s.id === p.id)) persist(saved.filter((s) => s.id !== p.id))
    else
      persist([
        { id: p.id, numer: p.numer, gmina: p.gmina, obreb: p.obreb, powierzchnia_ha: p.powierzchnia_ha, zapisano: new Date().toISOString() },
        ...saved,
      ])
  }
  return { saved, isSaved, toggle }
}
