import { Droplets } from 'lucide-react'
import { LayerData, type FeatureStyler } from './LayerData'
import type { MapLayer } from './types'

/**
 * Woda w okolicy (F3/F6) – rzeki, cieki, rowy, kanały i zbiorniki wokół działki z GET /api/layers/woda
 * (GeoJSON: LineString / Polygon, properties kind / color / label / toward_outflow – kolor z odpowiedzi, dymek z `label`).
 * Legenda – klasy z odpowiedzi (`legend`), zapasowo poniższe.
 */
const KIND_COLOR: Record<string, string> = {
  rzeka: '#1D5D96',
  ciek: '#2F80C9',
  row: '#4FA3EC',
  kanal: '#3B6FB6',
  zbiornik: '#2F80C9',
}
const waterStyle: FeatureStyler = (p, kind) => {
  const c = p?.color ?? (p?.kind ? KIND_COLOR[p.kind] : undefined) ?? '#2F80C9'
  // w stronę odpływu wody z działki – grubsza linia (tam warto szukać miejsca na zastawkę)
  const out = (p as { toward_outflow?: boolean } | null)?.toward_outflow ? 2 : 0
  return {
    color: c,
    weight: (kind === 'line' ? (p?.kind === 'rzeka' ? 5 : p?.kind === 'row' ? 3 : 4) : 1.5) + out,
    opacity: 0.95,
    dashArray: p?.kind === 'row' ? '6 4' : undefined,
    fillColor: c,
    fillOpacity: kind === 'line' ? 0 : 0.45,
  }
}

const WaterNearby: MapLayer = {
  key: 'woda',
  label: 'Woda w okolicy',
  short: 'Woda',
  icon: Droplets,
  legend: {
    kind: 'classes',
    items: [
      { color: KIND_COLOR.rzeka, label: 'Rzeka' },
      { color: KIND_COLOR.ciek, label: 'Strumień, ciek' },
      { color: KIND_COLOR.row, label: 'Rów melioracyjny (przerywana)' },
      { color: KIND_COLOR.kanal, label: 'Kanał' },
      { color: KIND_COLOR.zbiornik, label: 'Staw, zbiornik' },
    ],
  },
  // licencja ODbL: atrybucja w stopce mapy, gdy warstwa jest widoczna (legenda pokazuje `note` z serwera)
  Overlay: (props) => <LayerData {...props} style={waterStyle} opacity={0.95} attribution="Woda w okolicy: © autorzy OpenStreetMap (ODbL)" />,
}

export default WaterNearby
