import { useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { LayerKey, LayerResponse } from '@/api/types'
import { mockRequested } from '@/mocks/useMockAnalysis'

/** Stan danych aktywnej warstwy: brak działki, czekanie na zdjęcie, ładowanie, gotowe, brak danych, błąd. */
export type LayerState =
  | { phase: 'idle' }
  | { phase: 'waiting' }
  | { phase: 'loading' }
  | { phase: 'ok'; data: LayerResponse }
  | { phase: 'unavailable' }
  | { phase: 'error' }

/** Mock (?dane=przykladowe): warstwy satelitarne z plików przykładowych A11. */
async function mockLayer(layer: LayerKey): Promise<LayerResponse | null> {
  if (layer === 'kondycja') return (await import('@/mocks/layers.kondycja.sample.json')).default as unknown as LayerResponse
  if (layer === 'wilgotnosc') return (await import('@/mocks/layers.wilgotnosc.sample.json')).default as unknown as LayerResponse
  return null
}

/**
 * GET /api/layers/{layer}?parcel_id=&date= dla wybranej działki (SPEC 5.3). Zmiana warstwy, działki,
 * daty albo `refresh` (np. przyszło zdjęcie satelitarne) = nowe zapytanie (poprzednie przerwane).
 * `waiting` – dane warstwy jeszcze się liczą (zdjęcie satelitarne w drodze), nie pytamy serwera.
 * 404/501 = brak danych dla tej działki, nie błąd.
 */
export function useLayerData(layer: LayerKey, parcelId: string | null, date: string, refresh = '', waiting = false): LayerState {
  const key = parcelId && !waiting ? `${layer}|${parcelId}|${date}|${refresh}` : null
  const [result, setResult] = useState<{ key: string; state: LayerState } | null>(null)

  useEffect(() => {
    if (!key || !parcelId) return
    const ctrl = new AbortController()
    const request =
      import.meta.env.DEV && mockRequested() && (layer === 'kondycja' || layer === 'wilgotnosc')
        ? mockLayer(layer).then((d) => d ?? Promise.reject(new ApiError(404, null)))
        : api.layer(layer, parcelId, date, ctrl.signal)
    request.then(
      (data) => !ctrl.signal.aborted && setResult({ key, state: { phase: 'ok', data } }),
      (e) => {
        if (ctrl.signal.aborted) return
        const unavailable = e instanceof ApiError && (e.status === 404 || e.status === 501)
        setResult({ key, state: { phase: unavailable ? 'unavailable' : 'error' } })
      },
    )
    return () => ctrl.abort()
  }, [key, layer, parcelId, date])

  if (!parcelId) return { phase: 'idle' }
  if (waiting) return { phase: 'waiting' }
  return result?.key === key ? result.state : { phase: 'loading' }
}
