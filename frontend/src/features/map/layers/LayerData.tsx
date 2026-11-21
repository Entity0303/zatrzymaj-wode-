import L from 'leaflet'
import { GeoJSON, ImageOverlay } from 'react-leaflet'
import type { LayerOverlayProps } from './types'

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
 * po stronie serwera) + obiekty GeoJSON (strzałki, rowy, strefy) z dymkiem `label` / `name`.
 */
export function LayerData({ data, style = DEFAULT_STYLE, opacity = 0.85 }: LayerOverlayProps & { style?: FeatureStyler; opacity?: number }) {
  const r = data.raster
  return (
    <>
      {r && (
        <ImageOverlay
          key={r.image_url}
          url={r.image_url}
          bounds={[
            [r.bbox[1], r.bbox[0]],
            [r.bbox[3], r.bbox[2]],
          ]}
          opacity={opacity}
          interactive={false}
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
