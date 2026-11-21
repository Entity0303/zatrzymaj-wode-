import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Parcel } from '@/api/types'
import { SAVED_KEY, useStored } from './storage'

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

export function useSavedParcels() {
  const [stored, persist] = useStored<SavedParcel[]>(SAVED_KEY, [])
  const saved = useMemo(() => (Array.isArray(stored) ? stored : []), [stored])
  const isSaved = useCallback((id: string) => saved.some((p) => p.id === id), [saved])
  const toggle = (p: Parcel) => {
    if (saved.some((s) => s.id === p.id)) persist(saved.filter((s) => s.id !== p.id))
    else
      persist([
        { id: p.id, numer: p.numer, gmina: p.gmina, obreb: p.obreb, powierzchnia_ha: p.powierzchnia_ha, zapisano: new Date().toISOString() },
        ...saved,
      ])
  }
  const remove = (id: string) => persist(saved.filter((s) => s.id !== id))
  return { saved, isSaved, toggle, remove }
}
