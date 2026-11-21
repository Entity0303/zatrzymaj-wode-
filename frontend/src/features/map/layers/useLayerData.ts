import { useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { LayerKey, LayerResponse } from '@/api/types'

/** Stan danych aktywnej warstwy: brak działki, ładowanie, gotowe, warstwa jeszcze niepoliczona, błąd. */
export type LayerState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'ok'; data: LayerResponse }
  | { phase: 'unavailable' }
  | { phase: 'error' }

/**
 * GET /api/layers/{layer}?parcel_id=&date= dla wybranej działki (SPEC 5.3). Zmiana warstwy, działki
 * albo daty = nowe zapytanie (poprzednie przerwane). 404/501 = „warstwa w budowie”, nie błąd.
 */
export function useLayerData(layer: LayerKey, parcelId: string | null, date: string): LayerState {
  const key = parcelId ? `${layer}|${parcelId}|${date}` : null
  const [result, setResult] = useState<{ key: string; state: LayerState } | null>(null)

  useEffect(() => {
    if (!key || !parcelId) return
    const ctrl = new AbortController()
    api.layer(layer, parcelId, date, ctrl.signal).then(
      (data) => !ctrl.signal.aborted && setResult({ key, state: { phase: 'ok', data } }),
      (e) => {
        if (ctrl.signal.aborted) return
        const unavailable = e instanceof ApiError && (e.status === 404 || e.status === 501)
        setResult({ key, state: { phase: unavailable ? 'unavailable' : 'error' } })
      },
    )
    return () => ctrl.abort()
  }, [key, layer, parcelId, date])

  if (!key) return { phase: 'idle' }
  return result?.key === key ? result.state : { phase: 'loading' }
}
