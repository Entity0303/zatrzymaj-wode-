import { Mountain } from 'lucide-react'
import { LayerData, type FeatureStyler } from './LayerData'
import type { MapLayer } from './types'

/**
 * Teren – strefy z NMT: sucha górka / stok / płasko / mokry dołek + cieniowanie rzeźby (SPEC 5.3).
 */
// te same kolory co pasek stref w panelu i paszporcie (kontrakt A6: górka, stok, płasko, dołek)
const ZONE: Record<string, string> = { gorka: '#8B6B4A', stok: '#E8B931', plasko: '#5BB37F', dolek: '#2F80C9' }
const terrainStyle: FeatureStyler = (p) => {
  const c = p?.color ?? (p?.kind ? ZONE[p.kind] : undefined) ?? '#5BB37F'
  return { color: c, weight: 1, opacity: 0.9, fillColor: c, fillOpacity: 0.5 }
}

const Terrain: MapLayer = {
  key: 'teren',
  label: 'Teren',
  short: 'Teren',
  icon: Mountain,
  legend: {
    kind: 'classes',
    items: [
      { color: '#8B6B4A', label: 'Sucha górka' },
      { color: '#E8B931', label: 'Stok' },
      { color: '#5BB37F', label: 'Płasko' },
      { color: '#2F80C9', label: 'Mokry dołek' },
    ],
  },
  // strefy: kolor z `color` albo z `kind` (gorka/stok/plasko/dolek), półprzezroczyste
  Overlay: (props) => <LayerData {...props} style={terrainStyle} />,
}

export default Terrain
