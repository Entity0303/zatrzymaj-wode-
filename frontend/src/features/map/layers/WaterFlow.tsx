import { Waves } from 'lucide-react'
import { LayerData, type FeatureStyler } from './LayerData'
import type { MapLayer } from './types'

/**
 * Spływ wody – strzałki kierunku spływu, miejsca zbierania wody, odpływ z działki
 * („tu woda ucieka”), rowy/cieki/zbiorniki z BDOT10k, zgłoszenia rolników (SPEC 5.3).
 */
const flowStyle: FeatureStyler = (p, kind) => {
  const c = p?.color ?? (p?.kind === 'outflow' ? '#E5675C' : p?.kind === 'pin' ? '#E2A23B' : '#2F7FC1')
  return { color: c, weight: kind === 'line' ? 3 : 1.5, opacity: 0.95, fillColor: c, fillOpacity: kind === 'line' ? 0 : 0.45 }
}

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
  // rowy/cieki – niebieskie linie, miejsca zbierania wody – plamy, odpływ – czerwony
  Overlay: (props) => <LayerData {...props} style={flowStyle} opacity={0.9} />,
}

export default WaterFlow
