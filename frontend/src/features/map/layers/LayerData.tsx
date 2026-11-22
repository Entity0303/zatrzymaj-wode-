import L from 'leaflet'
import { useEffect, useState } from 'react'
import { GeoJSON, ImageOverlay } from 'react-leaflet'
import type { RasterOverlay } from '@/api/types'
import type { LayerOverlayProps } from './types'

/** y w rzucie Mercatora – Leaflet rozciąga obraz liniowo w tym układzie, więc maska musi liczyć tak samo. */
const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))

/**
 * Raster warstwy przycięty do obrysu działki (SPEC 5.1: poza obrysem nie malujemy danych pola). Piksele 10 m
 * z satelity wychodzą poza granicę – rysujemy obraz na płótnie powiększonym ok. do 1024 px (bez wygładzania)
 * z maską w kształcie działki. Błąd wczytania = obraz bez przycięcia.
 */
function useClippedImage(r: RasterOverlay | null | undefined, geom: GeoJSON.Polygon | GeoJSON.MultiPolygon): string | null {
  const [out, setOut] = useState<{ src: string; geom: unknown; url: string } | null>(null)
  useEffect(() => {
    if (!r) return
    let cancelled = false
    const img = new Image()
    img.onload = () => {
      const scale = Math.max(1, Math.round(1024 / Math.max(img.width, img.height, 1)))
      const w = img.width * scale
      const h = img.height * scale
      const c = document.createElement('canvas')
      c.width = w
      c.height = h
      const ctx = c.getContext('2d')
      if (!ctx || cancelled) return
      const [x0, y0, x1, y1] = r.bbox
      const top = mercY(y1)
      const span = top - mercY(y0) || 1
      const px = (lon: number) => ((lon - x0) / (x1 - x0 || 1)) * w
      const py = (lat: number) => ((top - mercY(lat)) / span) * h
      ctx.beginPath()
      const polys = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates
      for (const poly of polys)
        for (const ring of poly) {
          ring.forEach(([lon, lat], i) => (i ? ctx.lineTo(px(lon), py(lat)) : ctx.moveTo(px(lon), py(lat))))
          ctx.closePath()
        }
      ctx.clip('evenodd')
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(img, 0, 0, w, h)
      setOut({ src: r.image_url, geom, url: c.toDataURL('image/png') })
    }
    img.onerror = () => !cancelled && setOut({ src: r.image_url, geom, url: r.image_url })
    img.src = r.image_url
    return () => {
      cancelled = true
    }
  }, [r, geom])
  return r && out?.src === r.image_url && out.geom === geom ? out.url : null
}

/** Opcjonalne właściwości obiektów GeoJSON warstwy (propozycja dla osoby A – nie wymagane). */
type FeatureProps = { color?: string; label?: string; name?: string; kind?: string } | null

export type FeatureStyler = (props: FeatureProps, kind: 'line' | 'area') => L.PathOptions

const DEFAULT_STYLE: FeatureStyler = (p, kind) => ({
  color: p?.color ?? '#2F7FC1',
  weight: kind === 'line' ? 3 : 1.5,
  opacity: 0.95,
  fillColor: p?.color ?? '#2F7FC1',
  fillOpacity: 0.45,
})

/**
 * Wspólne rysowanie warstwy z GET /api/layers/{layer}: raster PNG w granicach bbox (przycięty do obrysu
 * działki na płótnie – useClippedImage) + obiekty GeoJSON (strzałki, rowy, strefy) z dymkiem `label` / `name`.
 */
export function LayerData({ data, parcel, style = DEFAULT_STYLE, opacity = 0.85 }: LayerOverlayProps & { style?: FeatureStyler; opacity?: number }) {
  const r = data.raster
  const clipped = useClippedImage(r, parcel.geometria)
  return (
    <>
      {r && clipped && (
        <ImageOverlay
          key={clipped.slice(-64)}
          url={clipped}
          bounds={[
            [r.bbox[1], r.bbox[0]],
            [r.bbox[3], r.bbox[2]],
          ]}
          opacity={opacity}
          interactive={false}
          className="layer-pixelated"
        />
      )}
      {data.features && (
        <GeoJSON
          key={`${data.layer}-${data.analysis_date}-${data.features.features?.length ?? 0}`}
          data={data.features}
          style={(f) => style((f?.properties ?? null) as FeatureProps, f?.geometry.type.includes('Line') ? 'line' : 'area')}
          pointToLayer={(f, latlng) => {
            const s = style((f.properties ?? null) as FeatureProps, 'area')
            return L.circleMarker(latlng, { radius: 7, color: '#FFFFFF', weight: 2, fillColor: s.fillColor ?? s.color, fillOpacity: 1 })
          }}
          onEachFeature={(f, layer) => {
            const p = f.properties as FeatureProps
            const text = p?.label ?? p?.name
            if (text) layer.bindTooltip(String(text), { direction: 'top', sticky: true })
          }}
        />
      )}
    </>
  )
}
