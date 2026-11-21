import { WMSTileLayer } from 'react-leaflet'

/**
 * Pola uprawne podświetlone na mapie: mapa IUNG-PIB „kategorie gleb / użytkowanie” (WMS, ta sama co do analizy, D3)
 * z własnym stylem SLD – kody 1–5 (grunty rolne, gleby organiczne) jako delikatna szałwia, kody 11–14
 * (las, woda, zabudowa, drogi) przezroczyste. Sprawdzone na żywo 21.11.2026 (GeoServer przyjmuje SLD_BODY).
 */
const IUNG_WMS = 'https://sgeo.iung.pl/geoserver/Susza/wms'

const entry = (q: number, opacity: number) => `<ColorMapEntry color="#9DB896" quantity="${q}" opacity="${opacity}"/>`
const clear = (q: number) => `<ColorMapEntry color="#000000" quantity="${q}" opacity="0"/>`

const SLD = [
  '<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc">',
  '<NamedLayer><Name>Susza:katgl_landuse2024</Name><UserStyle><FeatureTypeStyle><Rule><RasterSymbolizer>',
  '<Opacity>1</Opacity><ColorMap type="values">',
  entry(1, 0.6),
  entry(2, 0.6),
  entry(3, 0.6),
  entry(4, 0.6),
  entry(5, 0.45),
  clear(11),
  clear(12),
  clear(13),
  clear(14),
  '</ColorMap></RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>',
].join('')

export function FarmlandLayer() {
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
      opacity={0.8}
      zIndex={5}
      attribution='Pola uprawne: <a href="https://susza.iung.pulawy.pl">IUNG-PIB</a>'
    />
  )
}
