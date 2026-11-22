import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from './leaflet'
import { SOIL_ATTR, removeSoilOverlays } from './soilOverlayDom'
import { SOIL_COLOR } from '@/theme/soil'

/**
 * Gleba (F10) – podatność gleb na suszę IUNG-PIB (`Susza:katgl_landuse2024`, ta sama co do analizy, D3) TYLKO
 * w obrysie wybranej działki (też pola narysowanego i obszaru przybliżonego). Zamiast kafli na całą mapę (F7):
 * JEDNO zapytanie WMS GetMap dla prostokąta działki + 10% marginesu, w EPSG:3857 (ta sama siatka co mapa),
 * rozmiar obrazu jak działka na ekranie przy dopasowaniu widoku (maks. 1024 px). Obraz w SVG przyciętym
 * `clipPath` do obrysu (bez CORS – nie czytamy pikseli) jako L.svgOverlay w stałych współrzędnych: przesuwanie
 * i zoom go nie odświeżają; nowa działka = nowy obraz, stary zdjęty z mapy.
 * Styl SLD w kolorach aplikacji (`theme/soil.ts`), las / woda / zabudowa / drogi przezroczyste. Zapytanie idzie
 * prosto z przeglądarki do sgeo.iung.pl (bez proxy w backendzie).
 */
const IUNG_WMS = 'https://sgeo.iung.pl/geoserver/Susza/wms'

/** Największy bok obrazu, px. */
const MAX_PX = 1024
const MIN_PX = 64

export const SOIL_ATTRIBUTION = 'Podatność gleb na suszę: <a href="https://susza.iung.pulawy.pl">IUNG-PIB</a>'

/** Stan obrazu gleby – tekst pod legendą („Brak danych IUNG dla tej działki” przy błędzie). */
export type SoilImageStatus = 'loading' | 'ok' | 'error'

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

// Web Mercator (EPSG:3857), metry
const R = 6378137
const mercX = (lon: number) => (R * lon * Math.PI) / 180
const mercY = (lat: number) => R * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))

const SVG_NS = 'http://www.w3.org/2000/svg'
let clipSeq = 0

type Geom = GeoJSON.Polygon | GeoJSON.MultiPolygon

/** Wszystkie pierścienie (zewnętrzne i dziury) – clip-rule evenodd. */
const ringsOf = (g: Geom) => (g.type === 'Polygon' ? g.coordinates : g.coordinates.flat())

/**
 * Obraz IUNG przycięty do obrysu `geometry`. Montowany tylko przy włączonej warstwie „Gleba” i wybranej działce;
 * `onStatus` – loading → ok / error (błąd WMS = GeoServer odpowiada XML-em zamiast PNG → `error` obrazu).
 */
export function SoilParcelOverlay({ geometry, onStatus }: { geometry: Geom; onStatus?: (s: SoilImageStatus) => void }) {
  const map = useMap()
  const status = useRef(onStatus)
  status.current = onStatus
  const shape = JSON.stringify(geometry.coordinates)

  useEffect(() => {
    const g = geometry
    const bounds = L.geoJSON(g).getBounds().pad(0.1)
    const [x0, x1] = [mercX(bounds.getWest()), mercX(bounds.getEast())]
    const [y0, y1] = [mercY(bounds.getSouth()), mercY(bounds.getNorth())]
    // rozmiar jak na ekranie przy widoku dopasowanym do działki (albo bliżej, jeśli już przybliżono)
    const z = Math.max(map.getZoom(), map.getBoundsZoom(bounds))
    const a = map.project(bounds.getNorthWest(), z)
    const b = map.project(bounds.getSouthEast(), z)
    const scale = Math.min(1, MAX_PX / Math.max(Math.abs(b.x - a.x), Math.abs(b.y - a.y), 1))
    const w = Math.max(MIN_PX, Math.round(Math.abs(b.x - a.x) * scale))
    const h = Math.max(MIN_PX, Math.round(Math.abs(b.y - a.y) * scale))

    const url =
      `${IUNG_WMS}?` +
      new URLSearchParams({
        SERVICE: 'WMS',
        VERSION: '1.3.0',
        REQUEST: 'GetMap',
        LAYERS: 'Susza:katgl_landuse2024',
        STYLES: '',
        SLD_BODY: SLD,
        CRS: 'EPSG:3857',
        BBOX: `${x0},${y0},${x1},${y1}`,
        WIDTH: String(w),
        HEIGHT: String(h),
        FORMAT: 'image/png',
        TRANSPARENT: 'TRUE',
      }).toString()

    // obrys w układzie obrazu (x w prawo, y w dół)
    const px = (lon: number) => ((mercX(lon) - x0) / (x1 - x0)) * w
    const py = (lat: number) => ((y1 - mercY(lat)) / (y1 - y0)) * h
    const d = ringsOf(g)
      .map((ring) => ring.map(([lon, lat], i) => `${i ? 'L' : 'M'}${px(lon).toFixed(1)} ${py(lat).toFixed(1)}`).join('') + 'Z')
      .join('')

    const id = `soil-clip-${++clipSeq}`
    const svg = document.createElementNS(SVG_NS, 'svg')
    svg.setAttribute(SOIL_ATTR, '')
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`)
    svg.setAttribute('preserveAspectRatio', 'none')
    const defs = document.createElementNS(SVG_NS, 'defs')
    const clip = document.createElementNS(SVG_NS, 'clipPath')
    clip.setAttribute('id', id)
    clip.setAttribute('clipPathUnits', 'userSpaceOnUse')
    const path = document.createElementNS(SVG_NS, 'path')
    path.setAttribute('d', d)
    path.setAttribute('clip-rule', 'evenodd')
    clip.appendChild(path)
    defs.appendChild(clip)
    svg.appendChild(defs)
    const img = document.createElementNS(SVG_NS, 'image')
    img.setAttribute('x', '0')
    img.setAttribute('y', '0')
    img.setAttribute('width', String(w))
    img.setAttribute('height', String(h))
    img.setAttribute('preserveAspectRatio', 'none')
    img.setAttribute('clip-path', `url(#${id})`)
    img.setAttribute('style', 'image-rendering: pixelated')
    // obraz, który przyjdzie po zdjęciu nakładki (zmiana warstwy / działki) – bez zmiany stanu legendy
    let live = true
    img.addEventListener('load', () => live && status.current?.('ok'))
    img.addEventListener('error', () => live && status.current?.('error'))
    img.setAttribute('href', url)
    svg.appendChild(img)

    status.current?.('loading')
    const layer = L.svgOverlay(svg, bounds, { opacity: 0.8, interactive: false, attribution: SOIL_ATTRIBUTION })
    removeSoilOverlays(map) // nigdy dwa obrazy gleby naraz
    map.addLayer(layer)
    return () => {
      live = false
      map.removeLayer(layer)
      // przerwij pobieranie i usuń element razem z <clipPath> (Leaflet zdejmuje tylko z panelu)
      img.removeAttribute('href')
      svg.remove()
    }
    // obraz zależy tylko od kształtu działki (nie od przesunięć i zoomu)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, shape])
  return null
}
