import type { HydroFeature } from '@/api/types'
import { formatNum } from './format'

/** Nazwa rodzaju wody w okolicy (F3, hydro.features[].kind). */
export const HYDRO_KIND: Record<HydroFeature['kind'], string> = {
  rzeka: 'Rzeka',
  ciek: 'Strumień',
  row: 'Rów melioracyjny',
  kanal: 'Kanał',
  zbiornik: 'Staw / zbiornik',
}

/** „40 m” / „2,3 km” */
export const formatDistance = (m: number) => (m < 1000 ? `${formatNum(m, 0)} m` : `${formatNum(m / 1000, 1)} km`)
