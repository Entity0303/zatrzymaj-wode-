import type { LayerKey, LayerResponse, SatelliteStatus } from '@/api/types'
import { formatDatePl, formatNum } from '@/lib/format'
import type { LegendSpec, MapLayer } from './types'
import type { LayerState } from './useLayerData'

const SATELLITE_LAYERS: LayerKey[] = ['kondycja', 'wilgotnosc']

/**
 * Legenda aktywnej warstwy: gdy serwer podał skalę kolorów (A11: `legend`, `legend_left`, `legend_right`) –
 * pasek z tych samych kolorów co obraz warstwy; inaczej legenda zapisana przy warstwie.
 * Tytuł zostaje nasz („Kondycja upraw”) – termin techniczny (NDVI / NDMI) tylko w szczegółach.
 */
export function layerLegend(base: MapLayer, state: LayerState): LegendSpec {
  if (state.phase !== 'ok' || !state.data.legend?.length || base.legend.kind !== 'gradient') return base.legend
  const d = state.data
  const stops = [...(d.legend ?? [])].sort((a, b) => a.value - b.value)
  return {
    ...base.legend,
    colors: stops.map((s) => s.color),
    left: d.legend_left ?? base.legend.left,
    right: d.legend_right ?? base.legend.right,
  }
}

/** Zmienne do tekstu stanu warstwy (daty, zakres wysokości). */
export function layerStatusVars(d: LayerResponse): Record<string, string> {
  return {
    a: d.value_range ? formatNum(d.value_range[0], 1) : '',
    b: d.value_range ? formatNum(d.value_range[1], 1) : '',
    date: d.scene_date ? formatDatePl(d.scene_date) : d.source_tag.date ? formatDatePl(d.source_tag.date) : '',
  }
}

/**
 * Stan danych warstwy jako tekst pod legendą (klucz tłumaczenia; zmienne z `layerStatusVars`).
 * `satellite = 'brak_danych'` – serwer nie ma zdjęcia: warstwy satelity mówią to wprost.
 */
export function layerStatusText(layer: LayerKey, state: LayerState, satellite: SatelliteStatus | null): string {
  const sat = SATELLITE_LAYERS.includes(layer)
  if (sat && satellite === 'brak_danych' && state.phase !== 'ok') return 'Brak zdjęcia satelitarnego dla tej działki'
  switch (state.phase) {
    case 'idle':
      return 'Wybierz działkę, aby zobaczyć warstwę'
    case 'waiting':
      return state.reason
    case 'loading':
      return 'Wczytuję warstwę…'
    case 'unavailable':
      if (sat) return 'Brak zdjęcia satelitarnego dla tej działki'
      return layer === 'gleba' || layer === 'woda' ? 'Ta warstwa będzie wkrótce' : 'Brak danych dla tej działki'
    case 'error':
      return 'Nie udało się pobrać warstwy – mapa działa dalej'
    case 'ok': {
      const d = state.data
      if (d.layer === 'teren' && d.value_range) return 'Wysokość od {a} do {b} m n.p.m.'
      if (d.layer === 'woda' && !d.features?.features?.length) return 'W pobliżu działki nie ma rzek, rowów ani stawów'
      if (d.layer === 'woda' && d.note) return d.note
      if (sat && (d.scene_date || d.source_tag.date)) return 'Zdjęcie satelitarne z {date}'
      if (d.source_tag.date) return 'Dane z {date}'
      return d.source_tag.source ?? ''
    }
  }
}
