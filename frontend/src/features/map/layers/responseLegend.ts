import type { LayerKey, LayerResponse, Satellite } from '@/api/types'
import { formatDatePl, formatNum } from '@/lib/format'
import type { LegendSpec, MapLayer } from './types'
import type { LayerState } from './useLayerData'
import { TERRAIN_NODATA, serverMessage } from '@/lib/terrainState'

const SATELLITE_LAYERS: LayerKey[] = ['kondycja', 'wilgotnosc']

export { TERRAIN_PENDING } from '@/lib/terrainState'

/**
 * Legenda aktywnej warstwy: gdy serwer podał skalę kolorów (A11: `legend`, `legend_left`, `legend_right`) –
 * pasek z tych samych kolorów co obraz warstwy; inaczej legenda zapisana przy warstwie.
 * Tytuł zostaje nasz („Kondycja upraw”) – termin techniczny (NDVI / NDMI) tylko w szczegółach.
 */
export function layerLegend(base: MapLayer, state: LayerState): LegendSpec {
  if (state.phase !== 'ok' || !state.data.legend?.length) return base.legend
  const d = state.data
  // F6: klasy z opisami (np. „woda”: rzeka, ciek, rów, kanał, zbiornik – kolory jak na mapie)
  if (base.legend.kind === 'classes') {
    const items = (d.legend ?? []).filter((s) => s.label).map((s) => ({ color: s.color, label: s.label! }))
    return items.length ? { ...base.legend, items } : base.legend
  }
  if (base.legend.kind !== 'gradient') return base.legend
  const stops = [...(d.legend ?? [])].sort((a, b) => a.value - b.value)
  return {
    ...base.legend,
    colors: stops.map((s) => s.color),
    left: d.legend_left ?? base.legend.left,
    right: d.legend_right ?? base.legend.right,
  }
}

/**
 * F27: linia informacji o danych na dole legendy – gotowe: „Policzono / Zdjęcie z / Dane z dd.mm.rrrr · źródło: …”
 * (z pól, które API zwraca; bez daty – samo źródło), w trakcie: „Liczę…”, błąd: komunikat z serwera albo nasz.
 * Zwraca tekst już przetłumaczony (`t`).
 */
export function layerInfoLine(
  layer: LayerKey,
  state: LayerState,
  t: (key: string, vars?: Record<string, string | number>) => string,
  queue: number | null = null,
): string | null {
  const terrain = layer === 'teren' || layer === 'splyw'
  switch (state.phase) {
    case 'idle':
      return null
    case 'waiting':
    case 'loading':
      return terrain
        ? t('Liczę teren i spływ – zwykle 10–30 s, przy wolnym serwerze do ok. minuty') + (queue != null ? ` · ${t('w kolejce: {n}', { n: queue })}` : '')
        : null
    case 'unavailable':
    case 'error': {
      const m = serverMessage(state.message)
      return m ? t(m) : t('Brak danych – spróbuj za chwilę')
    }
    case 'ok': {
      const d = state.data
      const src = d.source_tag.source?.trim()
      const date = d.scene_date ?? d.source_tag.date
      const sat = SATELLITE_LAYERS.includes(layer)
      const when = date ? t(terrain ? 'Policzono {date}' : sat ? 'Zdjęcie z {date}' : 'Dane z {date}', { date: formatDatePl(date) }) : null
      const from = src ? t('źródło: {src}', { src }) : null
      return [when, from].filter(Boolean).join(' · ') || null
    }
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

/** Ile dni wstecz backend szuka bezchmurnej sceny (satellite.yaml `days_back`) – tylko do tekstu zapasowego. */
const SAT_DAYS_BACK = 60

/**
 * F10: pusta warstwa satelity – „Poza sezonem – rośliny nie rosną” (wilgotność poza sezonem: NDMI oceniamy tylko
 * w sezonie), komunikat z API (404 `detail.message`, zdanie analizy satelity), na końcu tekst zapasowy.
 */
function satelliteEmptyText(layer: LayerKey, apiMessage: string | null | undefined, satellite: Satellite | null): string {
  if (layer === 'wilgotnosc' && satellite?.in_season === false) return 'Poza sezonem – rośliny nie rosną'
  const api = apiMessage ?? (satellite?.status === 'brak_danych' ? (satellite.sentence ?? satellite.warning) : null)
  if (api?.trim()) return api.trim()
  if (satellite?.in_season === false) return 'Poza sezonem – rośliny nie rosną'
  return `Brak bezchmurnego zdjęcia z ostatnich ${SAT_DAYS_BACK} dni`
}

/**
 * Stan danych warstwy jako tekst pod legendą (klucz tłumaczenia; zmienne z `layerStatusVars`).
 * F10: puste warstwy mówią wprost dlaczego (komunikat z API, jeśli jest; inaczej nasz tekst):
 * satelita – brak bezchmurnego zdjęcia / poza sezonem; spływ – „Liczę spływ…” / „Brak danych o terenie”;
 * woda – „Brak rzek i rowów w promieniu 500 m”. Gleba – w pages/Start (obraz IUNG, nie /api/layers).
 */
export function layerStatusText(layer: LayerKey, state: LayerState, satellite: Satellite | null): string {
  const sat = SATELLITE_LAYERS.includes(layer)
  if (sat && satellite?.status === 'brak_danych' && state.phase !== 'ok') return satelliteEmptyText(layer, null, satellite)
  switch (state.phase) {
    case 'idle':
      return 'Wybierz działkę, aby zobaczyć warstwę'
    case 'waiting':
      return state.reason
    case 'loading':
      return 'Wczytuję warstwę…'
    case 'unavailable':
      if (sat) return satelliteEmptyText(layer, state.message, satellite)
      // komunikat z serwera, gdy jest (np. „teren liczy się dłużej niż zwykle – spróbuj za chwilę”)
      if (layer === 'splyw' || layer === 'teren') return serverMessage(state.message) ?? TERRAIN_NODATA
      if (layer === 'woda') return state.message ?? 'Brak rzek i rowów w promieniu 500 m'
      return state.message ?? 'Brak danych dla tej działki'
    case 'error':
      if (layer === 'splyw' || layer === 'teren') return serverMessage(state.message) ?? TERRAIN_NODATA
      if (serverMessage(state.message)) return serverMessage(state.message)!
      return state.message ?? 'Nie udało się pobrać warstwy – mapa działa dalej'
    case 'ok': {
      const d = state.data
      // F23: pusta odpowiedź warstwy terenu / spływu – nigdy pusta mapa bez słowa
      if ((d.layer === 'teren' || d.layer === 'splyw') && !d.raster && !d.features?.features?.length) return TERRAIN_NODATA
      if (d.layer === 'teren' && d.value_range) return 'Wysokość od {a} do {b} m n.p.m.'
      // woda: `note` to atrybucja OSM, nie komunikat – pusta warstwa = nasz tekst
      if (d.layer === 'woda' && !d.features?.features?.length) return 'Brak rzek i rowów w promieniu 500 m'
      if (d.layer === 'woda' && d.note) return d.note
      if (sat && !d.raster && !d.features?.features?.length) return satelliteEmptyText(layer, d.note, satellite)
      if (d.layer === 'wilgotnosc' && satellite?.in_season === false) return 'Poza sezonem – rośliny nie rosną'
      if (sat && (d.scene_date || d.source_tag.date)) return 'Zdjęcie satelitarne z {date}'
      if (d.source_tag.date) return 'Dane z {date}'
      return d.source_tag.source ?? ''
    }
  }
}
