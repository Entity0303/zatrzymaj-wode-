import { Waves } from 'lucide-react'
import { LayerData, type FeatureStyler } from './LayerData'
import type { MapLayer } from './types'

/**
 * Spływ wody – strzałki kierunku spływu, miejsca zbierania wody, odpływ z działki
 * („tu woda ucieka”), rowy/cieki/zbiorniki z BDOT10k, zgłoszenia rolników (SPEC 5.3).
 */
// kontrakt A6: flow (linie spływu), outflow („tu woda ucieka”), retencja (miejsce na oczko),
// pas_buforowy (linia), spot (zagłębienie bez odpływu) – każdy obiekt ma też własne `color` i `label`
const KIND_COLOR: Record<string, string> = {
  flow: '#2F7FC1',
  outflow: '#E5675C',
  retencja: '#2E5B3F',
  pas_buforowy: '#5BB37F',
  spot: '#2F80C9',
}
const flowStyle: FeatureStyler = (p, kind) => {
  const c = p?.color ?? (p?.kind ? KIND_COLOR[p.kind] : undefined) ?? '#2F7FC1'
  const dashed = p?.kind === 'pas_buforowy'
  return {
    color: c,
    weight: kind === 'line' ? (p?.kind === 'flow' ? 2.5 : 4) : 1.5,
    opacity: 0.95,
    dashArray: dashed ? '6 6' : undefined,
    fillColor: c,
    fillOpacity: kind === 'line' ? 0 : 0.4,
  }
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
      { symbol: 'outflow', label: 'Tu woda ucieka' },
      { symbol: 'spot', label: 'Tu zbiera się woda' },
      { symbol: 'pond', label: 'Miejsce na oczko' },
    ],
  },
  // rowy/cieki – niebieskie linie, miejsca zbierania wody – plamy, odpływ – czerwony
  Overlay: (props) => <LayerData {...props} style={flowStyle} opacity={0.9} />,
}

export default WaterFlow
