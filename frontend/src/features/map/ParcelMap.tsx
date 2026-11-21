import L, { type LeafletMouseEvent, type Map as LeafletMap } from 'leaflet'
import { forwardRef, useEffect, useMemo } from 'react'
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  Popup,
  ScaleControl,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import type { Parcel } from '@/api/types'
import type { Status } from '@/theme/status'
import { parcelBounds, type MapInsets } from './geo'
import { layerByKey, type LayerKey } from './layers'
import { ParcelLabel } from './ParcelLabel'
import { useLang } from '@/lib/i18n'

export type BaseMap = 'orto' | 'osm'

export const POLAND_CENTER: [number, number] = [52.07, 19.48]

// Ortofotomapa Geoportalu – WMTS w siatce EPSG:3857 (kafle z/x/y z cache; szybciej niż WMS).
const ORTO_WMTS =
  'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution' +
  '?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTOFOTOMAPA&STYLE=default' +
  '&FORMAT=image/jpeg&TILEMATRIXSET=EPSG:3857&TILEMATRIX=EPSG:3857:{z}&TILEROW={y}&TILECOL={x}'

function FitTo({
  parcel,
  candidates,
  insets,
  reducedMotion,
}: {
  parcel: Parcel | null
  candidates: Parcel[]
  insets: MapInsets
  reducedMotion: boolean
}) {
  const map = useMap()
  useEffect(() => {
    const opts = {
      paddingTopLeft: [insets.left + 24, insets.top + 24] as L.PointTuple,
      paddingBottomRight: [insets.right + 24, insets.bottom + 24] as L.PointTuple,
    }
    let b: L.LatLngBounds | null = null
    let maxZoom = 18
    if (parcel) b = parcelBounds(parcel)
    else if (candidates.length) {
      b = L.latLngBounds(candidates.map((c) => parcelBounds(c).getCenter()))
      maxZoom = 14
    }
    if (!b) return
    if (reducedMotion) map.fitBounds(b, { ...opts, maxZoom, animate: false })
    else map.flyToBounds(b, { ...opts, maxZoom, duration: 1 })
    // insets celowo poza zależnościami – zmiana szuflady nie powinna przesuwać mapy
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parcel, candidates, map, reducedMotion])
  return null
}

function Events({
  onClick,
  onMoveEnd,
}: {
  onClick: (lon: number, lat: number) => void
  onMoveEnd: (lon: number, lat: number) => void
}) {
  const map = useMapEvents({
    click: (e: LeafletMouseEvent) => onClick(e.latlng.lng, e.latlng.lat),
    moveend: () => {
      const c = map.getCenter()
      onMoveEnd(c.lng, c.lat)
    },
  })
  return null
}

const numberIcon = (n: number) =>
  L.divIcon({
    className: '',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    html: `<div style="width:32px;height:32px;border-radius:9999px;background:#2F6B47;border:2px solid #fff;color:#fff;font:600 14px/28px 'Inter Variable',system-ui,sans-serif;text-align:center;box-shadow:0 2px 8px rgb(30 42 35/.35)">${n}</div>`,
  })

const anchorIcon = L.divIcon({ className: '', iconSize: [0, 0] })

type Props = {
  baseMap: BaseMap
  layer: LayerKey
  analysisDate: string
  parcel: Parcel | null
  parcelStatus: Status
  candidates: Parcel[]
  pendingPoint: [number, number] | null
  userPoint: [number, number] | null
  insidePopup: { lon: number; lat: number; text: string } | null
  insets: MapInsets
  reducedMotion: boolean
  onMapClick: (lon: number, lat: number) => void
  onMoveEnd: (lon: number, lat: number) => void
  onSelectCandidate: (p: Parcel) => void
  onClosePopup: () => void
}

export const ParcelMap = forwardRef<LeafletMap, Props>(function ParcelMap(
  {
    baseMap,
    layer,
    analysisDate,
    parcel,
    parcelStatus,
    candidates,
    pendingPoint,
    userPoint,
    insidePopup,
    insets,
    reducedMotion,
    onMapClick,
    onMoveEnd,
    onSelectCandidate,
    onClosePopup,
  },
  ref,
) {
  const { t } = useLang()
  const ActiveOverlay = layerByKey(layer).Overlay
  const labelPos = useMemo(() => (parcel ? parcelBounds(parcel).getCenter() : null), [parcel])
  return (
    <MapContainer
      ref={ref}
      center={POLAND_CENTER}
      zoom={6}
      minZoom={5}
      maxZoom={20}
      zoomControl={false}
      attributionControl
      className="absolute inset-0 z-0 h-full w-full"
      aria-label="Mapa działek. Kliknij pole, aby je wybrać."
    >
      {baseMap === 'orto' ? (
        <TileLayer
          key="orto"
          url={ORTO_WMTS}
          maxNativeZoom={19}
          maxZoom={20}
          attribution='Ortofotomapa © <a href="https://www.geoportal.gov.pl">GUGiK</a>'
        />
      ) : (
        <TileLayer
          key="osm"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxNativeZoom={19}
          maxZoom={20}
          attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
      )}
      <ScaleControl position="bottomleft" imperial={false} />

      {parcel && (
        <>
          {/* delikatna poświata pod białym obrysem 3 px (SPEC 5.1) */}
          <GeoJSON
            key={`${parcel.id}-halo`}
            data={parcel.geometria}
            interactive={false}
            style={{ color: '#1E2A23', weight: 7, opacity: 0.28, fill: false }}
          />
          <GeoJSON
            key={parcel.id}
            data={parcel.geometria}
            interactive={false}
            style={{ color: '#FFFFFF', weight: 3, opacity: 1, fillColor: '#FFFFFF', fillOpacity: 0.12 }}
          />
          {/* aktywna warstwa danych przycięta do obrysu (features/map/layers/*) */}
          {ActiveOverlay && <ActiveOverlay parcel={parcel} analysisDate={analysisDate} />}
          {labelPos && (
            <Marker position={labelPos} icon={anchorIcon} interactive={false} keyboard={false}>
              <Tooltip permanent direction="center" className="parcel-label" opacity={1}>
                <ParcelLabel number={parcel.numer} status={parcelStatus} />
              </Tooltip>
            </Marker>
          )}
        </>
      )}

      {candidates.map((c, i) => (
        <Marker
          key={c.id}
          position={parcelBounds(c).getCenter()}
          icon={numberIcon(i + 1)}
          title={`${i + 1}. ${t('Działka {numer}', { numer: c.numer })}, ${t('obręb {obreb}, gm. {gmina}', { obreb: c.obreb, gmina: c.gmina })}`}
          eventHandlers={{ click: () => onSelectCandidate(c) }}
        >
          <Tooltip direction="top" offset={[0, -16]}>
            {i + 1}. {t('Działka {numer}', { numer: c.numer })} – {t('obręb {obreb}, gm. {gmina}', { obreb: c.obreb, gmina: c.gmina })}
          </Tooltip>
        </Marker>
      ))}

      {pendingPoint && (
        <CircleMarker
          center={[pendingPoint[1], pendingPoint[0]]}
          radius={8}
          interactive={false}
          pathOptions={{ color: '#FFFFFF', weight: 3, fillColor: '#2F6B47', fillOpacity: 1 }}
        />
      )}
      {userPoint && (
        <CircleMarker
          center={[userPoint[1], userPoint[0]]}
          radius={8}
          interactive={false}
          pathOptions={{ color: '#FFFFFF', weight: 3, fillColor: '#2F80C9', fillOpacity: 1 }}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            {t('Jesteś tutaj')}
          </Tooltip>
        </CircleMarker>
      )}

      {insidePopup && (
        <Popup position={[insidePopup.lat, insidePopup.lon]} eventHandlers={{ remove: onClosePopup }}>
          <span className="text-sm">{insidePopup.text}</span>
        </Popup>
      )}

      <FitTo parcel={parcel} candidates={candidates} insets={insets} reducedMotion={reducedMotion} />
      <Events onClick={onMapClick} onMoveEnd={onMoveEnd} />
    </MapContainer>
  )
})
