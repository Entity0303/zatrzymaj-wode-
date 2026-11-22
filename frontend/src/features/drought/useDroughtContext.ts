import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { AnalysisResponse, DroughtContext } from '@/api/types'

/** wynik na (miejsce, data analizy, nasz stopień) – panel i paszport dzielą jedno zapytanie */
const cache = new Map<string, DroughtContext>()

/** Obrys do POST-a: pole narysowane / obszar przybliżony (dla działki z ewidencji wystarcza identyfikator). */
function polygonOf(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): GeoJSON.Polygon {
  return g.type === 'Polygon' ? g : { type: 'Polygon', coordinates: g.coordinates[0] }
}

/**
 * F31: tło suszowe z Europejskiego Obserwatorium Suszy (A26) – pobierane w tle po analizie (jak teren).
 * `null` = jeszcze nie ma albo zapytanie się nie udało (kafel ukryty – nigdy błąd); `unavailable` = usługa nie
 * odpowiedziała (szary kafel z notą).
 */
export function useDroughtContext(analysis: AnalysisResponse): DroughtContext | null {
  const p = analysis.parcel
  const date = analysis.analysis_date
  const level = analysis.status.level === 'no_data' ? null : analysis.status.level
  const drawn = p.source === 'drawn' || p.source === 'approximate'
  const first = p.geometria.type === 'Polygon' ? p.geometria.coordinates[0]?.[0] : p.geometria.coordinates[0]?.[0]?.[0]
  const key = `${p.id}|${drawn && first ? first.join(',') : ''}|${date}|${level ?? ''}`
  const [state, setState] = useState<{ key: string; data: DroughtContext | null } | null>(null)

  useEffect(() => {
    const hit = cache.get(key)
    if (hit) return setState({ key, data: hit })
    const ctrl = new AbortController()
    const query = drawn ? { geometry: polygonOf(p.geometria), date } : { parcelId: p.id, date }
    api.droughtContext(query, level, ctrl.signal).then(
      (data) => {
        if (ctrl.signal.aborted) return
        if (!data.unavailable) cache.set(key, data)
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
