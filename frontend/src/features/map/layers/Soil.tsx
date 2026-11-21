import { Layers } from 'lucide-react'
import type { MapLayer } from './types'

/**
 * Gleba – kategorie podatności na suszę IUNG (I–IV, organiczne, nie-rolne), przycięte do obrysu (SPEC 5.3).
 * TODO (osoba B): Overlay z GET /api/layers/gleba.
 */
const Soil: MapLayer = {
  key: 'gleba',
  label: 'Gleba',
  short: 'Gleba',
  icon: Layers,
  legend: {
    kind: 'classes',
    items: [
      { color: '#F2D64B', label: 'I – bardzo podatna na suszę' },
      { color: '#F0A04B', label: 'II – podatna' },
      { color: '#D9722E', label: 'III – średnio podatna' },
      { color: '#9C3D2A', label: 'IV – mało podatna' },
      { color: '#8E918F', label: 'Gleby organiczne' },
    ],
  },
  Overlay: null,
}

export default Soil
