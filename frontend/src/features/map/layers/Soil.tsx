import { Layers } from 'lucide-react'
import { SOIL_COLOR } from '@/theme/soil'
import type { MapLayer } from './types'

/**
 * Gleba – kategorie podatności na suszę IUNG (I–IV, organiczne), tylko w obrysie działki (SPEC 5.3, F10).
 * Rysowanie: `SoilParcelOverlay` (features/map/SoilSusceptibilityLayer) – obraz WMS IUNG przycięty do obrysu,
 * bez GET /api/layers/gleba. Legenda z udziałami kategorii na działce – w pages/Start (`analysis.soil.shares`).
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
  // rysowane osobno (ParcelMap → SoilParcelOverlay), nie z /api/layers
  Overlay: null,
}

export default Soil
