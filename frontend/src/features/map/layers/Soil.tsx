import { Layers } from 'lucide-react'
import { SOIL_COLOR, soilColor } from '@/theme/soil'
import { LayerData, type FeatureStyler } from './LayerData'
import type { MapLayer } from './types'

/**
 * Gleba – kategorie podatności na suszę IUNG (I–IV, organiczne, nie-rolne), przycięte do obrysu (SPEC 5.3).
 */
const soilStyle: FeatureStyler = (p) => {
  const c = p?.color ?? (p?.kind && /^\d+$/.test(p.kind) ? soilColor(Number(p.kind)) : '#B8BDB5')
  return { color: '#FFFFFF', weight: 1, opacity: 0.8, fillColor: c, fillOpacity: 0.6 }
}

const Soil: MapLayer = {
  key: 'gleba',
  label: 'Gleba',
  short: 'Gleba',
  icon: Layers,
  legend: {
    kind: 'classes',
    items: [
      { color: SOIL_COLOR[1], label: 'I – bardzo podatna na suszę' },
      { color: SOIL_COLOR[2], label: 'II – podatna' },
      { color: SOIL_COLOR[3], label: 'III – średnio podatna' },
      { color: SOIL_COLOR[4], label: 'IV – mało podatna' },
      { color: SOIL_COLOR[5], label: 'Gleby organiczne' },
    ],
  },
  // kategorie IUNG: kolor z `color` albo z kodu (`kind` = '1'…'14'), jak w legendzie
  Overlay: (props) => <LayerData {...props} style={soilStyle} />,
}

export default Soil
