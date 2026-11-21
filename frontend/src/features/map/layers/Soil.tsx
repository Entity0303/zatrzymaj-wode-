import { Layers } from 'lucide-react'
import { SOIL_COLOR } from '@/theme/soil'
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
      { color: SOIL_COLOR[1], label: 'I – bardzo podatna na suszę' },
      { color: SOIL_COLOR[2], label: 'II – podatna' },
      { color: SOIL_COLOR[3], label: 'III – średnio podatna' },
      { color: SOIL_COLOR[4], label: 'IV – mało podatna' },
      { color: SOIL_COLOR[5], label: 'Gleby organiczne' },
    ],
  },
  Overlay: null,
}

export default Soil
