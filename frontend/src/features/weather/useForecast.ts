import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { Forecast } from '@/api/types'
import type { ForecastState } from '@/features/parcel-panel/types'

/** Pogoda teraz + prognoza (Open-Meteo) dla punktu [lon, lat]; odczekuje 400 ms po zmianie punktu. */
export function useForecast(target: [number, number]) {
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [state, setState] = useState<ForecastState>('idle')

  useEffect(() => {
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      setState('loading')
      api
        .forecast(target[0], target[1], ctrl.signal)
        .then((f) => {
          setForecast(f)
          setState('ok')
        })
        .catch((e) => {
          if ((e as Error).name === 'AbortError') return
          setForecast(null)
          setState('error')
        })
    }, 400)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [target])

  return { forecast, state }
}
