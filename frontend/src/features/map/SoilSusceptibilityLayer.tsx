import { WMSTileLayer } from './leaflet'
import { SOIL_COLOR } from '@/theme/soil'

/**
 * Podatność gleb na suszę – mapa IUNG-PIB (`Susza:katgl_landuse2024`, ta sama co do analizy, D3) na mapie startowej.
 * Własny styl SLD w kolorach aplikacji (`theme/soil.ts` – jak warstwa „Gleba”): kat. I–IV i gleby organiczne
 * kolorowe, las / woda / zabudowa / drogi przezroczyste. GeoServer IUNG przyjmuje `SLD_BODY` (sprawdzone 21.11.2026).
 */
const IUNG_WMS = 'https://sgeo.iung.pl/geoserver/Susza/wms'

/** Największe przybliżenie, przy którym warstwa jest rysowana (z bliska piksele 5 m wyglądają topornie). */
export const SOIL_MAX_ZOOM = 11

/**
 * Czy warstwa jest teraz na mapie – ta sama reguła co Leaflet (kafle dla zaokrąglonego przybliżenia ≤ maxZoom),
 * żeby legenda pojawiała się i znikała razem z warstwą.
 */
export const soilLayerVisible = (zoom: number) => Math.round(zoom) <= SOIL_MAX_ZOOM

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

export function SoilSusceptibilityLayer() {
  return (
    <WMSTileLayer
      url={IUNG_WMS}
      params={{
        layers: 'Susza:katgl_landuse2024',
        format: 'image/png',
        transparent: true,
        // parametr spoza typów Leaflet – GeoServer: styl przekazany w zapytaniu
        ...({ sld_body: SLD } as object),
      }}
      opacity={0.55}
      zIndex={5}
      // tylko przy oddaleniu (regiony) – z bliska piksele 5 m wyglądają topornie i zasłaniają pola
      maxZoom={SOIL_MAX_ZOOM}
      attribution='Podatność gleb na suszę: <a href="https://susza.iung.pulawy.pl">IUNG-PIB</a>'
    />
  )
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
