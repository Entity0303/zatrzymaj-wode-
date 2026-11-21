import L, { type LeafletMouseEvent, type PointExpression } from 'leaflet'
import { useEffect } from 'react'
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import type { Parcel } from '@/api'

export type BaseMap = 'orto' | 'osm'

const POLAND_CENTER: [number, number] = [52.07, 19.48]

// Ortofotomapa Geoportalu – WMTS w siatce EPSG:3857 (standardowe kafle z/x/y, szybsze niż WMS,
// bo serwowane z cache). Sprawdzone: GetTile z TILEMATRIXSET=EPSG:3857 zwraca image/jpeg.
const ORTO_WMTS =
  'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution' +
  '?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTOFOTOMAPA&STYLE=default' +
  '&FORMAT=image/jpeg&TILEMATRIXSET=EPSG:3857&TILEMATRIX=EPSG:3857:{z}&TILEROW={y}&TILECOL={x}'

function isMobile() {
  return window.matchMedia('(max-width: 767px)').matches
}

/** Marginesy przy przybliżaniu – żeby działka nie chowała się pod paskami i panelem. */
function fitPadding(): { paddingTopLeft: PointExpression; paddingBottomRight: PointExpression } {
  if (isMobile()) {
    return { paddingTopLeft: [24, 150], paddingBottomRight: [24, window.innerHeight * 0.48] }
  }
  return { paddingTopLeft: [140, 120], paddingBottomRight: [440, 60] }
}

function FitTo({ parcel, candidates }: { parcel: Parcel | null; candidates: Parcel[] }) {
  const map = useMap()
  useEffect(() => {
    if (parcel) {
      const b = L.geoJSON(parcel.geometria).getBounds()
      map.flyToBounds(b, { ...fitPadding(), maxZoom: 18, duration: 0.8 })
    } else if (candidates.length > 0) {
      const b = L.geoJSON({
        type: 'FeatureCollection',
        features: candidates.map((c) => ({ type: 'Feature', properties: {}, geometry: c.geometria })),
      } as GeoJSON.FeatureCollection).getBounds()
      map.flyToBounds(b, { ...fitPadding(), maxZoom: 15, duration: 0.8 })
    }
  }, [parcel, candidates, map])
  return null
}

function FlyToPoint({ point }: { point: [number, number] | null }) {
  const map = useMap()
  useEffect(() => {
    if (point) map.flyTo([point[1], point[0]], Math.max(map.getZoom(), 16), { duration: 0.8 })
  }, [point, map])
  return null
}

function ClickHandler({ onPick }: { onPick: (lon: number, lat: number) => void }) {
  useMapEvents({ click: (e: LeafletMouseEvent) => onPick(e.latlng.lng, e.latlng.lat) })
  return null
}

/** Numerowany znacznik kandydata (numer taki sam jak na liście w panelu). */
function numberIcon(n: number) {
  return L.divIcon({
    className: '',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    html: `<div style="width:28px;height:28px;border-radius:9999px;background:#15803d;border:2px solid #fff;color:#fff;font:600 13px/24px system-ui,sans-serif;text-align:center;box-shadow:0 2px 8px rgb(0 0 0/.35)">${n}</div>`,
  })
}

function centroid(p: Parcel): [number, number] {
  const c = L.geoJSON(p.geometria).getBounds().getCenter()
  return [c.lat, c.lng]
}

type Props = {
  baseMap: BaseMap
  parcel: Parcel | null
  candidates: Parcel[]
  pendingPoint: [number, number] | null
  userPoint: [number, number] | null
  onPick: (lon: number, lat: number) => void
  onSelectCandidate: (p: Parcel) => void
}

export function ParcelMap({
  baseMap,
  parcel,
  candidates,
  pendingPoint,
  userPoint,
  onPick,
  onSelectCandidate,
}: Props) {
  return (
    <MapContainer
      center={POLAND_CENTER}
      zoom={6}
      minZoom={5}
      maxZoom={20}
      zoomControl={false}
      className="picking absolute inset-0 z-0 h-full w-full"
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
      <ZoomControl position="bottomright" zoomInTitle="Przybliż" zoomOutTitle="Oddal" />

      {parcel && (
        <>
          {/* ciemna „poświata” pod białym obrysem – obrys widoczny na jasnym i ciemnym podkładzie */}
          <GeoJSON
            key={`${parcel.id}-halo`}
            data={parcel.geometria}
            interactive={false}
            style={{ color: '#0b2614', weight: 6, opacity: 0.35, fill: false }}
          />
          <GeoJSON
            key={parcel.id}
            data={parcel.geometria}
            interactive={false}
            style={{ color: '#ffffff', weight: 3, fillColor: '#ffffff', fillOpacity: 0.16 }}
          />
        </>
      )}

      {candidates.map((c, i) => (
        <Marker
          key={c.id}
          position={centroid(c)}
          icon={numberIcon(i + 1)}
          eventHandlers={{ click: () => onSelectCandidate(c) }}
        >
          <Tooltip direction="top" offset={[0, -14]}>
            {i + 1}. Działka {c.numer} – obręb {c.obreb}, gm. {c.gmina}
          </Tooltip>
        </Marker>
      ))}

      {pendingPoint && (
        <CircleMarker
          center={[pendingPoint[1], pendingPoint[0]]}
          radius={8}
          interactive={false}
          pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#16a34a', fillOpacity: 1 }}
        />
      )}
      {userPoint && (
        <CircleMarker
          center={[userPoint[1], userPoint[0]]}
          radius={8}
          interactive={false}
          pathOptions={{ color: '#ffffff', weight: 3, fillColor: '#2563eb', fillOpacity: 1 }}
        >
          <Tooltip permanent direction="top" offset={[0, -8]}>
            Jesteś tutaj
          </Tooltip>
        </CircleMarker>
      )}

      <FitTo parcel={parcel} candidates={candidates} />
      <FlyToPoint point={userPoint && !parcel ? userPoint : null} />
      <ClickHandler onPick={onPick} />
    </MapContainer>
  )
}
