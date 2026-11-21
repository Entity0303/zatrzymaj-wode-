import { Mountain } from 'lucide-react'
import type { MapLayer } from './types'

/**
 * Teren – strefy z NMT: sucha górka / stok / płasko / mokry dołek + cieniowanie rzeźby (SPEC 5.3).
 * TODO (osoba B): Overlay z GET /api/layers/teren; w legendzie zakres wysokości („od … do … m n.p.m.”).
 */
const Terrain: MapLayer = {
  key: 'teren',
  label: 'Teren',
  short: 'Teren',
  icon: Mountain,
  legend: {
    kind: 'classes',
    items: [
      { color: '#8B6B4A', label: 'Sucha górka' },
      { color: '#E9DCC3', label: 'Stok' },
      { color: '#9DB5A0', label: 'Płasko' },
      { color: '#2F80C9', label: 'Mokry dołek' },
    ],
  },
  Overlay: null,
}

export default Terrain
