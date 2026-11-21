import { Droplet } from 'lucide-react'
import { LayerData } from './LayerData'
import type { MapLayer } from './types'

/**
 * Wilgotność roślin – NDMI (Sentinel-2), piksele 10 m, przycięte do obrysu (SPEC 5.3).
 */
const PlantMoisture: MapLayer = {
  key: 'wilgotnosc',
  label: 'Wilgotność roślin',
  short: 'Wilgotność',
  icon: Droplet,
  legend: { kind: 'gradient', colors: ['#8B6B4A', '#E9DCC3', '#2F80C9'], left: 'Sucho', right: 'Wilgotno' },
  Overlay: (props) => <LayerData {...props} />,
}

export default PlantMoisture
