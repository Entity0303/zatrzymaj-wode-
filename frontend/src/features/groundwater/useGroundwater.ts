import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { AnalysisResponse, GroundwaterContext } from '@/api/types'

/** wynik na (miejsce, data analizy) – panel i paszport dzielą jedno zapytanie */
const cache = new Map<string, GroundwaterContext>()

/** Obrys do POST-a: pole narysowane / obszar przybliżony (dla działki z ewidencji wystarcza identyfikator). */
function polygonOf(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): GeoJSON.Polygon {
  return g.type === 'Polygon' ? g : { type: 'Polygon', coordinates: g.coordinates[0] }
}

/**
 * A27: „Wody gruntowe i zapas z opadów” – pobierane w tle po analizie (jak tło suszowe EDO). `null` = jeszcze nie ma albo
 * zapytanie się nie udało (kafel ukryty – nigdy błąd); `unavailable` = nie udało się nic policzyć (szary kafel z notą).
 * Teren liczy się w tle – dopóki go nie ma, wynik jest bez spadku i obniżeń; nie zapamiętujemy go wtedy na stałe.
 */
export function useGroundwater(analysis: AnalysisResponse): GroundwaterContext | null {
  const p = analysis.parcel
  const date = analysis.analysis_date
  const drawn = p.source === 'drawn' || p.source === 'approximate'
  const first = p.geometria.type === 'Polygon' ? p.geometria.coordinates[0]?.[0] : p.geometria.coordinates[0]?.[0]?.[0]
  // teren gotowy = osobny klucz, żeby po policzeniu terenu pobrać wynik ze spadkiem i obniżeniami
  const terrainReady = !!analysis.terrain && !('status' in analysis.terrain && analysis.terrain.status === 'pending')
  const key = `${p.id}|${drawn && first ? first.join(',') : ''}|${date}|${terrainReady ? 't' : ''}`
  const [state, setState] = useState<{ key: string; data: GroundwaterContext | null } | null>(null)

  useEffect(() => {
    const hit = cache.get(key)
    if (hit) return setState({ key, data: hit })
    const ctrl = new AbortController()
    const query = drawn ? { geometry: polygonOf(p.geometria), date } : { parcelId: p.id, date }
    api.groundwater(query, ctrl.signal).then(
      (data) => {
        if (ctrl.signal.aborted) return
        if (!data.unavailable && !data.source_pig.unavailable) cache.set(key, data)
        setState({ key, data })
      },
      () => {
        if (!ctrl.signal.aborted) setState({ key, data: null })
      },
    )
    return () => ctrl.abort()
    // obrys i identyfikator są częścią klucza
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return state && state.key === key ? state.data : null
}
