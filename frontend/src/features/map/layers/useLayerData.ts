import { useEffect, useState } from 'react'
import { ApiError, api } from '@/api/client'
import type { LayerKey, LayerResponse } from '@/api/types'
import { queuePosition } from '@/lib/terrainState'
import { mockRequested, mockWaterLayer } from '@/mocks/useMockAnalysis'

/** Stan danych aktywnej warstwy: brak działki, czekanie na zdjęcie, ładowanie, gotowe, brak danych, błąd. */
export type LayerState =
  | { phase: 'idle' }
  /** dane warstwy jeszcze się liczą (zdjęcie satelitarne, teren, woda w okolicy) – `reason` = tekst pod legendą */
  | { phase: 'waiting'; reason: string; /** pozycja w kolejce zadań w tle, gdy serwer ją poda */ queue?: number | null }
  | { phase: 'loading' }
  | { phase: 'ok'; data: LayerResponse }
  /** F10: `message` – komunikat z API (detail.message), np. „Brak bezchmurnego zdjęcia … z ostatnich 60 dni” */
  | { phase: 'unavailable'; message?: string | null }
  | { phase: 'error'; message?: string | null }

/** F23: teren „pending” – co ile i ile razy pytamy ponownie; limit czasu jednego zapytania o teren */
const PENDING_WAIT_MS = 3000
const PENDING_TRIES = 20
const TERRAIN_TIMEOUT_MS = 45_000

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
  /** F29: obszar przybliżony – punkt [lon, lat]; warstwy POST-em jak analiza */
  point: [number, number] | null = null,
): LayerState {
  const key = parcelId && !waiting ? `${layer}|${parcelId}|${date}|${refresh}` : null
  const [result, setResult] = useState<{ key: string; state: LayerState } | null>(null)

  useEffect(() => {
    if (!key || !parcelId) return
    const ctrl = new AbortController()
    const request =
      import.meta.env.DEV && mockRequested() && (layer === 'kondycja' || layer === 'wilgotnosc' || layer === 'woda')
        ? mockLayer(layer).then((d) => d ?? Promise.reject(new ApiError(404, null)))
        : api.layer(layer, parcelId, date, ctrl.signal, geometry, point)
    const terrain = layer === 'teren' || layer === 'splyw'
    // F23: teren / spływ – odpowiedź „pending” (serwer jeszcze liczy) = „Liczę…” i ponowne zapytanie co 3 s, najwyżej
    // 20 razy; brak odpowiedzi w 45 s = „brak danych” (nigdy wieczne „Wczytuję…”). Zmiana warstwy / działki / daty przerywa.
    let tries = 0
    let timedOut = false
    const limit = terrain
      ? setTimeout(() => {
          timedOut = true
          setResult({ key, state: { phase: 'error', message: null } })
          ctrl.abort()
        }, TERRAIN_TIMEOUT_MS)
      : null
    const done = () => {
      if (limit) clearTimeout(limit)
    }
    const onData = (data: LayerResponse) => {
      if (ctrl.signal.aborted) return
      if (terrain && (data as LayerResponse & { status?: string }).status === 'pending') {
        if (++tries >= PENDING_TRIES) {
          done()
          return setResult({ key, state: { phase: 'error', message: null } })
        }
        if (limit) clearTimeout(limit)
        setResult({ key, state: { phase: 'waiting', reason: 'Liczę teren i spływ… (do ok. minuty)', queue: queuePosition(data) } })
        again = setTimeout(() => api.layer(layer, parcelId, date, ctrl.signal, geometry, point).then(onData, onError), PENDING_WAIT_MS)
        return
      }
      done()
      setResult({ key, state: { phase: 'ok', data } })
    }
    let again: ReturnType<typeof setTimeout> | null = null
    const onError = (e: unknown) => {
        done()
        if (ctrl.signal.aborted || timedOut) return
        const unavailable = e instanceof ApiError && (e.status === 404 || e.status === 501)
        const detail = e instanceof ApiError ? (e.detail as { message?: unknown } | null) : null
        // F29: pole narysowane – bez technicznych komunikatów; prosto, co zrobić
        const message = geometry && !unavailable
          ? 'Nie udało się policzyć warstwy dla narysowanego pola – spróbuj narysować je jeszcze raz.'
          : typeof detail?.message === 'string' && detail.message.trim()
            ? detail.message.trim()
            : null
        setResult({ key, state: { phase: unavailable ? 'unavailable' : 'error', message } })
    }
    request.then(onData, onError)
    return () => {
      done()
      if (again) clearTimeout(again)
      ctrl.abort()
    }
    // geometria należy do działki (parcelId w kluczu)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, layer, parcelId, date])

  if (!parcelId) return { phase: 'idle' }
  if (waiting) return { phase: 'waiting', reason: waiting }
  if (result?.key === key) return result.state
  // F23: teren / spływ liczone na żywo przez serwer (do ok. 30 s) – mówimy to wprost zamiast „Wczytuję…”
  return layer === 'teren' || layer === 'splyw' ? { phase: 'waiting', reason: 'Liczę teren i spływ… (do ok. minuty)' } : { phase: 'loading' }
}
