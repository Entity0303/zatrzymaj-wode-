import { Waves } from 'lucide-react'
import type { MapLayer } from './types'

/**
 * Spływ wody – strzałki kierunku spływu, miejsca zbierania wody, odpływ z działki
 * („tu woda ucieka”), rowy/cieki/zbiorniki z BDOT10k, zgłoszenia rolników (SPEC 5.3).
 * TODO (osoba B): Overlay z GET /api/layers/splyw (GeoJSON), dymek „Rów melioracyjny · 40 m od działki”.
 */
const WaterFlow: MapLayer = {
  key: 'splyw',
  label: 'Spływ wody',
  short: 'Spływ',
  icon: Waves,
  legend: {
    kind: 'symbols',
    items: [
      { symbol: 'arrow', label: 'Kierunek spływu' },
      { symbol: 'spot', label: 'Tu zbiera się woda' },
      { symbol: 'outflow', label: 'Tu woda ucieka' },
      { symbol: 'line', label: 'Rowy, cieki, zbiorniki' },
      { symbol: 'pin', label: 'Zgłoszenia rolników' },
    ],
  },
  Overlay: null,
}

export default WaterFlow
