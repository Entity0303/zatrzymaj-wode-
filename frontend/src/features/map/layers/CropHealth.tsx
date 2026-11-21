import { Leaf } from 'lucide-react'
import { LayerData } from './LayerData'
import type { MapLayer } from './types'

/**
 * Kondycja upraw – NDVI z najbliższego bezchmurnego zdjęcia Sentinel-2 przed datą analizy,
 * piksele 10 m, przycięte do obrysu (SPEC 5.3).
 */
const CropHealth: MapLayer = {
  key: 'kondycja',
  label: 'Kondycja upraw',
  short: 'Kondycja',
  icon: Leaf,
  legend: {
    kind: 'gradient',
    colors: ['#C0473C', '#E2A23B', '#5F9F63', '#1F4230'],
    left: 'Słaba roślinność',
    right: 'Bujna',
    extra: { color: '#FFFFFF', label: 'Chmury' },
    note: 'Białe = chmury lub brak zdjęcia',
  },
  Overlay: (props) => <LayerData {...props} />,
}

export default CropHealth
