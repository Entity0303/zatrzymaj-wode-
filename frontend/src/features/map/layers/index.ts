import CropHealth from './CropHealth'
import PlantMoisture from './PlantMoisture'
import Soil from './Soil'
import Terrain from './Terrain'
import type { LayerKey, MapLayer } from './types'
import WaterFlow from './WaterFlow'
import WaterNearby from './WaterNearby'

export type { LayerKey, LegendSpec, MapLayer } from './types'

/** Kolejność pigułek (SPEC 4.2): Kondycja, Wilgotność, Teren, Spływ, Woda w okolicy (F3), Gleba. */
export const LAYERS: MapLayer[] = [CropHealth, PlantMoisture, Terrain, WaterFlow, WaterNearby, Soil]

export const layerByKey = (k: LayerKey) => LAYERS.find((l) => l.key === k)!
