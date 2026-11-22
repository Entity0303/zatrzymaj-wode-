import maplibregl, { type Map as MlMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Compass, Info, Map as MapIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { LayerResponse, Parcel } from '@/api/types'
import { parcelBounds } from '@/features/map/geo'
import { useLang } from '@/lib/i18n'

/**
 * Widok 3D (SPEC 8): teren działki i okolicy z ortofotomapą GUGiK, przewyższenie ×4, obrys działki
 * i aktywna warstwa (strefy terenu / spływ) z /api/layers. Obracanie: prawy przycisk / Ctrl + przeciągnij,
 * „Widok z góry”. Rzeźba: publiczne kafle wysokości AWS Terrain Tiles (Terrarium, ~30 m) – poglądowo;
 * analiza korzysta z NMT GUGiK 1 m (backend).
 */
const ORTO =
  'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution' +
  '?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTOFOTOMAPA&STYLE=default' +
  '&FORMAT=image/jpeg&TILEMATRIXSET=EPSG:3857&TILEMATRIX=EPSG:3857:{z}&TILEROW={y}&TILECOL={x}'
const DEM = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
const EXAGGERATION = 4

const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

/** WebGL dostępny? (bez niego – komunikat i powrót do 2D) */
function hasWebGL() {
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') ?? c.getContext('webgl'))
  } catch {
    return false
  }
}

export default function Terrain3D({
  parcel,
  layerData,
  reducedMotion,
  onClose,
}: {
  parcel: Parcel
  layerData: LayerResponse | null
  reducedMotion: boolean
  onClose: () => void
}) {
  const { t } = useLang()
  const box = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MlMap | null>(null)
  const [ready, setReady] = useState(false)
  const [failed] = useState(() => !hasWebGL())

  // mapa 3D – raz na działkę
  useEffect(() => {
    if (!box.current || failed) return
    const map: MlMap = new maplibregl.Map({
        container: box.current,
        style: {
          version: 8,
          sources: {
            orto: { type: 'raster', tiles: [ORTO], tileSize: 256, maxzoom: 19, attribution: 'Ortofotomapa © GUGiK' },
            dem: { type: 'raster-dem', tiles: [DEM], encoding: 'terrarium', tileSize: 256, maxzoom: 15, attribution: 'Rzeźba: AWS Terrain Tiles' },
            demShade: { type: 'raster-dem', tiles: [DEM], encoding: 'terrarium', tileSize: 256, maxzoom: 15 },
          },
          layers: [
            { id: 'bg', type: 'background', paint: { 'background-color': '#e4eadb' } },
            { id: 'orto', type: 'raster', source: 'orto' },
            { id: 'shade', type: 'hillshade', source: 'demShade', paint: { 'hillshade-exaggeration': 0.35, 'hillshade-shadow-color': '#1f4230' } },
          ],
          terrain: { source: 'dem', exaggeration: EXAGGERATION },
        },
        maxPitch: 80,
        attributionControl: { compact: true },
      })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right')

    const b = parcelBounds(parcel)
    map.fitBounds(
      [
        [b.getWest(), b.getSouth()],
        [b.getEast(), b.getNorth()],
      ],
      { padding: 120, maxZoom: 17, pitch: 62, bearing: -25, duration: 0 },
    )

    map.on('load', () => {
      map.addSource('parcel', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: parcel.geometria } })
      map.addSource('layer', { type: 'geojson', data: EMPTY })
      map.addLayer({
        id: 'layer-fill',
        type: 'fill',
        source: 'layer',
        filter: ['==', ['geometry-type'], 'Polygon'],
        paint: { 'fill-color': ['coalesce', ['get', 'color'], '#2F7FC1'], 'fill-opacity': 0.55 },
      })
      map.addLayer({
        id: 'layer-line',
        type: 'line',
        source: 'layer',
        filter: ['==', ['geometry-type'], 'LineString'],
        paint: { 'line-color': ['coalesce', ['get', 'color'], '#2F7FC1'], 'line-width': 3 },
      })
      map.addLayer({
        id: 'layer-point',
        type: 'circle',
        source: 'layer',
        filter: ['==', ['geometry-type'], 'Point'],
        paint: {
          'circle-color': ['coalesce', ['get', 'color'], '#E5675C'],
          'circle-radius': 8,
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 2,
        },
      })
      map.addLayer({ id: 'parcel-line', type: 'line', source: 'parcel', paint: { 'line-color': '#ffffff', 'line-width': 3.5 } })
      setReady(true)
      // delikatny obrót na start – pokazuje rzeźbę (bez, gdy ograniczony ruch)
      if (!reducedMotion) map.easeTo({ bearing: 20, duration: 6000 })
    })
    map.on('error', () => undefined) // pojedyncze kafle bez połączenia – mapa działa dalej
    return () => {
      map.remove()
      mapRef.current = null
      setReady(false)
    }
  }, [parcel, reducedMotion, failed])

  // aktywna warstwa (strefy terenu / spływ) na terenie 3D
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const src = map.getSource('layer') as maplibregl.GeoJSONSource | undefined
    src?.setData(layerData?.parcel_id === parcel.id && layerData.features ? layerData.features : EMPTY)
  }, [layerData, parcel.id, ready])

  const topView = () => mapRef.current?.easeTo({ pitch: 0, bearing: 0, duration: reducedMotion ? 0 : 800 })
  const tilt = () => mapRef.current?.easeTo({ pitch: 62, bearing: -25, duration: reducedMotion ? 0 : 800 })

  if (failed)
    return (
      <div className="absolute inset-0 z-[500] flex items-center justify-center bg-bg/90 p-6 text-center">
        <div className="max-w-sm space-y-3">
          <p className="font-display text-xl font-semibold">{t('Ta przeglądarka nie obsługuje widoku 3D')}</p>
          <button type="button" onClick={onClose} className="h-11 rounded-md bg-brand-dark px-4 text-sm font-semibold text-white">
            {t('Wróć do mapy 2D')}
          </button>
        </div>
      </div>
    )

  return (
    <div className="absolute inset-0 z-[500] animate-in fade-in duration-500">
      <div ref={box} className="h-full w-full" aria-label={t('Teren działki w 3D. Przeciągnij prawym przyciskiem, aby obrócić.')} />
      <div className="pointer-events-none absolute bottom-[76px] left-4 z-10 flex max-md:top-[124px] max-md:bottom-auto max-md:left-3 max-w-[min(420px,calc(100%-32px))] flex-col items-start gap-2 [&>*]:pointer-events-auto">
        <div className="flex gap-2">
          <button type="button" onClick={topView} className="flex h-11 items-center gap-2 rounded-full bg-surface px-4 text-sm font-semibold shadow-float hover:bg-sage-soft">
            <MapIcon className="size-4 text-brand" aria-hidden /> {t('Widok z góry')}
          </button>
          <button type="button" onClick={tilt} className="flex h-11 items-center gap-2 rounded-full bg-surface px-4 text-sm font-semibold shadow-float hover:bg-sage-soft">
            <Compass className="size-4 text-brand" aria-hidden /> {t('Widok z boku')}
          </button>
        </div>
        <p className="flex gap-2 rounded-xl bg-text/80 px-3 py-2 text-xs leading-4 text-white backdrop-blur">
          <Info className="mt-px size-3.5 shrink-0" aria-hidden />
          {t('3D poglądowo: rzeźba z publicznego modelu terenu (~30 m), wysokości ×{x}. Prawy przycisk / Ctrl + przeciągnij = obrót. Analiza korzysta z dokładnego modelu terenu GUGiK.', { x: EXAGGERATION })}
        </p>
      </div>
    </div>
  )
}
