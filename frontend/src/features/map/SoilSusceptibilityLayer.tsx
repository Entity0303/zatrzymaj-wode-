import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from './leaflet'
import { SOIL_COLOR } from '@/theme/soil'
import { useStored } from '@/lib/storage'

/**
 * Podatność gleb na suszę – mapa IUNG-PIB (`Susza:katgl_landuse2024`, ta sama co do analizy, D3).
 * Własny styl SLD w kolorach aplikacji (`theme/soil.ts` – jak warstwa „Gleba”): kat. I–IV i gleby organiczne
 * kolorowe, las / woda / zabudowa / drogi przezroczyste. GeoServer IUNG przyjmuje `SLD_BODY` (sprawdzone 21.11.2026).
 *
 * F7: tylko na żądanie (domyślnie wyłączona, stan w localStorage) i dopiero od przybliżenia gminy.
 * Kafle idą prosto z przeglądarki do sgeo.iung.pl (bez proxy w backendzie) – stały URL, więc przeglądarka
 * bierze je z własnej pamięci przy powrocie w to samo miejsce.
 */
const IUNG_WMS = 'https://sgeo.iung.pl/geoserver/Susza/wms'

/** Od tego przybliżenia warstwa pobiera kafle (skala gminy / kilku wsi). Poniżej – nic nie pobiera. */
export const SOIL_MIN_ZOOM = 12

/** Przybliżenia ponad to – kafle z poziomu 15 powiększane (raster IUNG ma ok. 5 m, ostrzej i tak nie będzie). */
const SOIL_MAX_NATIVE_ZOOM = 15

/** Polska z małym zapasem – Leaflet nie pyta o kafle poza tym prostokątem. */
const POLAND_BOUNDS = L.latLngBounds([48.9, 14.0], [55.0, 24.3])

export const SOIL_ATTRIBUTION = 'Podatność gleb na suszę: <a href="https://susza.iung.pulawy.pl">IUNG-PIB</a>'

/** Czy przy tym przybliżeniu warstwa ma kafle – ta sama reguła co Leaflet (zaokrąglony zoom ≥ minZoom). */
export const soilLayerInRange = (zoom: number) => Math.round(zoom) >= SOIL_MIN_ZOOM

/** Szary tekst przy przełączniku i w legendzie, gdy mapa jest za bardzo oddalona. */
export const SOIL_ZOOM_HINT = 'Przybliż mapę, aby zobaczyć podatność gleb'

/** Włączona / wyłączona – zapamiętane w przeglądarce (readStored / writeStored mają try/catch). */
export const useSoilLayerOn = () => useStored<boolean>('zw.soilLayer', false)

const entry = (q: number, opacity: number) => `<ColorMapEntry color="${SOIL_COLOR[q]}" quantity="${q}" opacity="${opacity}"/>`
const clear = (q: number) => `<ColorMapEntry color="#000000" quantity="${q}" opacity="0"/>`

const SLD = [
  '<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc">',
  '<NamedLayer><Name>Susza:katgl_landuse2024</Name><UserStyle><FeatureTypeStyle><Rule><RasterSymbolizer>',
  '<Opacity>1</Opacity><ColorMap type="values">',
  entry(1, 1),
  entry(2, 1),
  entry(3, 1),
  entry(4, 1),
  entry(5, 1),
  clear(11),
  clear(12),
  clear(13),
  clear(14),
  '</ColorMap></RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>',
].join('')

/** Jedna instancja na całe życie mapy – wszystkie opcje stałe, URL kafla zależy tylko od położenia. */
function createSoilLayer() {
  return L.tileLayer.wms(IUNG_WMS, {
    layers: 'Susza:katgl_landuse2024',
    format: 'image/png',
    transparent: true,
    // parametr spoza typów Leaflet – GeoServer: styl przekazany w zapytaniu
    ...({ sld_body: SLD } as object),
    tileSize: 512,
    opacity: 0.55,
    zIndex: 5,
    minZoom: SOIL_MIN_ZOOM,
    maxNativeZoom: SOIL_MAX_NATIVE_ZOOM,
    maxZoom: 20,
    bounds: POLAND_BOUNDS,
    // kafle dopiero po zatrzymaniu mapy, nie w trakcie przesuwania / animacji przybliżania
    updateWhenIdle: true,
    updateWhenZooming: false,
    keepBuffer: 2,
    attribution: SOIL_ATTRIBUTION,
  })
}

/**
 * Warstwa tworzona RAZ (useRef, przy pierwszym włączeniu); włączanie / wyłączanie = tylko addLayer / removeLayer.
 * Atrybucja IUNG-PIB w stopce mapy pojawia się i znika razem z warstwą (Leaflet dodaje ją przy addLayer).
 */
export function SoilSusceptibilityLayer({ on }: { on: boolean }) {
  const map = useMap()
  const layer = useRef<L.TileLayer.WMS | null>(null)
  useEffect(() => {
    if (!on) return
    layer.current ??= createSoilLayer()
    const l = layer.current
    map.addLayer(l)
    return () => {
      map.removeLayer(l)
    }
  }, [on, map])
  return null
}

/** Legenda warstwy (te same kategorie i kolory co warstwa „Gleba”). */
export const SOIL_SUSCEPTIBILITY_LEGEND = {
  kind: 'classes' as const,
  items: [
    { color: SOIL_COLOR[1], label: 'I – bardzo podatna na suszę' },
    { color: SOIL_COLOR[2], label: 'II – podatna' },
    { color: SOIL_COLOR[3], label: 'III – średnio podatna' },
    { color: SOIL_COLOR[4], label: 'IV – mało podatna' },
    { color: SOIL_COLOR[5], label: 'Gleby organiczne' },
  ],
}
