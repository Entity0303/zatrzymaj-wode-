import CropHealth from './CropHealth'
import PlantMoisture from './PlantMoisture'
import Soil from './Soil'
import Terrain from './Terrain'
import type { LayerKey, MapLayer } from './types'
import WaterFlow from './WaterFlow'

export type { LayerKey, LegendSpec, MapLayer } from './types'

/** Kolejność pigułek (SPEC 4.2): Kondycja, Wilgotność, Teren, Spływ, Gleba. */
export const LAYERS: MapLayer[] = [CropHealth, PlantMoisture, Terrain, WaterFlow, Soil]

export const layerByKey = (k: LayerKey) => LAYERS.find((l) => l.key === k)!
