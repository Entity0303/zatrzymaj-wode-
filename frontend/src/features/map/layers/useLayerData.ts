import { useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { LayerKey, LayerResponse } from '@/api/types'
import { mockRequested, mockWaterLayer } from '@/mocks/useMockAnalysis'

/** Stan danych aktywnej warstwy: brak działki, czekanie na zdjęcie, ładowanie, gotowe, brak danych, błąd. */
export type LayerState =
  | { phase: 'idle' }
  /** dane warstwy jeszcze się liczą (zdjęcie satelitarne, teren, woda w okolicy) – `reason` = tekst pod legendą */
  | { phase: 'waiting'; reason: string }
  | { phase: 'loading' }
  | { phase: 'ok'; data: LayerResponse }
  /** F10: `message` – komunikat z API (detail.message), np. „Brak bezchmurnego zdjęcia … z ostatnich 60 dni” */
  | { phase: 'unavailable'; message?: string | null }
  | { phase: 'error'; message?: string | null }

/** Mock (?dane=przykladowe): warstwy satelitarne z plików przykładowych A11. */
async function mockLayer(layer: LayerKey): Promise<LayerResponse | null> {
  if (layer === 'kondycja') return (await import('@/mocks/layers.kondycja.sample.json')).default as unknown as LayerResponse
  if (layer === 'wilgotnosc') return (await import('@/mocks/layers.wilgotnosc.sample.json')).default as unknown as LayerResponse
  if (layer === 'woda') return mockWaterLayer()
  return null
}

/**
 * GET /api/layers/{layer}?parcel_id=&date= dla wybranej działki (SPEC 5.3). Zmiana warstwy, działki,
 * daty albo `refresh` (np. przyszło zdjęcie satelitarne) = nowe zapytanie (poprzednie przerwane).
 * `waiting` – dane warstwy jeszcze się liczą (zdjęcie satelitarne w drodze), nie pytamy serwera.
 * 404/501 = brak danych dla tej działki, nie błąd.
 */
export function useLayerData(
  layer: LayerKey,
  parcelId: string | null,
  date: string,
  refresh = '',
  /** tekst „Pobieram…/Liczę…”, gdy dane warstwy jeszcze się liczą – wtedy nie pytamy serwera */
  waiting: string | null = null,
  /** F3: pole narysowane – warstwy satelity POST-em z obrysem */
  geometry: GeoJSON.Polygon | null = null,
): LayerState {
  const key = parcelId && !waiting ? `${layer}|${parcelId}|${date}|${refresh}` : null
  const [result, setResult] = useState<{ key: string; state: LayerState } | null>(null)

  useEffect(() => {
    if (!key || !parcelId) return
    const ctrl = new AbortController()
    const request =
      import.meta.env.DEV && mockRequested() && (layer === 'kondycja' || layer === 'wilgotnosc' || layer === 'woda')
        ? mockLayer(layer).then((d) => d ?? Promise.reject(new ApiError(404, null)))
        : api.layer(layer, parcelId, date, ctrl.signal, geometry)
    request.then(
      (data) => !ctrl.signal.aborted && setResult({ key, state: { phase: 'ok', data } }),
      (e) => {
        if (ctrl.signal.aborted) return
        const unavailable = e instanceof ApiError && (e.status === 404 || e.status === 501)
        const detail = e instanceof ApiError ? (e.detail as { message?: unknown } | null) : null
        const message = typeof detail?.message === 'string' && detail.message.trim() ? detail.message.trim() : null
        setResult({ key, state: { phase: unavailable ? 'unavailable' : 'error', message } })
      },
    )
    return () => ctrl.abort()
    // geometria należy do działki (parcelId w kluczu)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, layer, parcelId, date])

  if (!parcelId) return { phase: 'idle' }
  if (waiting) return { phase: 'waiting', reason: waiting }
  return result?.key === key ? result.state : { phase: 'loading' }
}
