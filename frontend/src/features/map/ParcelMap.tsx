import L, { type LeafletMouseEvent, type Map as LeafletMap } from 'leaflet'
import { forwardRef, useEffect, useMemo, useRef, type ReactNode } from 'react'
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from './leaflet'
import type { LayerResponse, Parcel, VerdictLevel } from '@/api/types'
import type { Status } from '@/theme/status'
import { parcelBounds, type MapInsets } from './geo'
import { layerByKey, type LayerKey } from './layers'
import { ParcelLabel } from './ParcelLabel'
import { SoilSusceptibilityLayer } from './SoilSusceptibilityLayer'
import { InfraPins } from '@/features/infra-reports/InfraPins'
import { useLang } from '@/lib/i18n'

export type BaseMap = 'orto' | 'osm'

export const POLAND_CENTER: [number, number] = [52.07, 19.48]
/** widok całej Polski (start, powrót karty powitalnej po oddaleniu) */
export const POLAND_ZOOM = 6

// Ortofotomapa Geoportalu – WMTS w siatce EPSG:3857 (kafle z/x/y z cache; szybciej niż WMS).
const ORTO_WMTS =
  'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution' +
  '?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTOFOTOMAPA&STYLE=default' +
  '&FORMAT=image/jpeg&TILEMATRIXSET=EPSG:3857&TILEMATRIX=EPSG:3857:{z}&TILEROW={y}&TILECOL={x}'

/** Start bez działki w adresie: cała Polska (z podatnością gleb na suszę – „susza + gleba” od pierwszego spojrzenia). */

function IntroView({ active }: { active: boolean }) {
  const map = useMap()
  const done = useRef(false)
  useEffect(() => {
    // tylko przy pierwszym wejściu – powrót z działki zostawia mapę tam, gdzie była
    if (!active || done.current) return
    done.current = true
    map.setView(POLAND_CENTER, POLAND_ZOOM, { animate: false })
    // komputer: karta powitalna po lewej – Polska z mapą gleb przesunięta w prawą część ekranu
    const w = map.getSize().x
    if (w >= 1024) map.panBy([-Math.round(w * 0.2), 0], { animate: false })
  }, [active, map])
  return null
}

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
  onDragStart,
}: {
  onClick: (lon: number, lat: number) => void
  onMoveEnd: (lon: number, lat: number, zoom: number) => void
  onDragStart?: () => void
}) {
  const map = useMapEvents({
    click: (e: LeafletMouseEvent) => onClick(e.latlng.lng, e.latlng.lat),
    // tylko przeciągnięcie przez użytkownika (nie flyTo / fitBounds z kodu)
    dragstart: () => onDragStart?.(),
    moveend: () => {
      const c = map.getCenter()
      onMoveEnd(c.lng, c.lat, map.getZoom())
    },
  })
  return null
}

const numberIcon = (n: number) =>
  L.divIcon({
    className: '',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    html: `<div style="width:32px;height:32px;border-radius:9999px;background:#2E5B3F;border:2px solid #fff;color:#fff;font:600 14px/28px 'Inter Variable',system-ui,sans-serif;text-align:center;box-shadow:0 2px 8px rgb(30 42 35/.35)">${n}</div>`,
  })

const anchorIcon = L.divIcon({ className: '', iconSize: [0, 0] })

type Props = {
  baseMap: BaseMap
  layer: LayerKey
  /** dane aktywnej warstwy (null = brak / w budowie) */
  layerData?: LayerResponse | null
  analysisDate: string
  parcel: Parcel | null
  parcelStatus: Status
  /** werdykt działki – „Na dłuższą metę: …” w etykiecie */
  parcelRisk?: VerdictLevel | null
  candidates: Parcel[]
  pendingPoint: [number, number] | null
  userPoint: [number, number] | null
  insidePopup: { lon: number; lat: number; text: string } | null
  insets: MapInsets
  reducedMotion: boolean
  onMapClick: (lon: number, lat: number) => void
  /** użytkownik zaczął przeciągać mapę (chowa kartę powitalną) */
  onDragStart?: () => void
  /** dodatkowe warstwy wewnątrz mapy (np. rysowane pole) */
  children?: ReactNode
  onMoveEnd: (lon: number, lat: number, zoom: number) => void
  onSelectCandidate: (p: Parcel) => void
  onClosePopup: () => void
  /** miejsce rekomendacji („Pokaż na mapie”) */
  highlight?: GeoJSON.Geometry | null
  /** ekran powitalny – widok całej Polski */
  intro?: boolean
  /** podatność gleb na suszę (IUNG) – włączona przełącznikiem w menu podkładu (F7) */
  soil?: boolean
  /** zgłoszenia rowów/zbiorników wokół działki; zmiana `infraRefresh` = ponowne pobranie */
  infraRefresh?: number
}

export const ParcelMap = forwardRef<LeafletMap, Props>(function ParcelMap(
  {
    baseMap,
    layer,
    layerData,
    analysisDate,
    parcel,
    parcelStatus,
    parcelRisk = null,
    candidates,
    pendingPoint,
    userPoint,
    insidePopup,
    insets,
    reducedMotion,
    onMapClick,
    onMoveEnd,
    onDragStart,
    onSelectCandidate,
    onClosePopup,
    highlight,
    intro = false,
    soil = false,
    infraRefresh = 0,
    children,
  },
  ref,
) {
  const { t } = useLang()
  const ActiveOverlay = layerByKey(layer).Overlay
  const labelPos = useMemo(() => (parcel ? parcelBounds(parcel).getCenter() : null), [parcel])
  // obszar zgłoszeń: działka + ok. 1,5 km dookoła
  const infraBox = useMemo<[number, number, number, number] | null>(() => {
    if (!parcel) return null
    const b = parcelBounds(parcel).pad(0)
    const d = 0.015
    return [b.getWest() - d, b.getSouth() - d, b.getEast() + d, b.getNorth() + d]
  }, [parcel])
  return (
    <MapContainer
      ref={ref}
      center={POLAND_CENTER}
      zoom={POLAND_ZOOM}
      minZoom={5}
      maxZoom={20}
      zoomControl={false}
      attributionControl
      className="absolute inset-0 z-0 h-full w-full"
      aria-label="Mapa działek. Kliknij pole, aby je wybrać."
    >
      {/* tło całej Europy pod ortofotomapą (poza Polską zamiast białego pola) */}
      {baseMap === 'orto' && (
        <TileLayer
          key="s2cloudless"
          url="https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg"
          maxNativeZoom={15}
          maxZoom={20}
          zIndex={0}
          attribution='<a href="https://s2maps.eu">Sentinel-2 cloudless 2016</a> © EOX (CC BY 4.0), dane Copernicus'
        />
      )}
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

      {parcel && (
        <>
          {/* aktywna warstwa danych przycięta do obrysu (features/map/layers/*) – pod białym obrysem */}
          {/* pole narysowane: serwer nadaje własny identyfikator (narysowane_…) – dane i tak są z tego obrysu */}
          {ActiveOverlay && layerData && (layerData.parcel_id === parcel.id || parcel.source === 'drawn') && (
            <ActiveOverlay parcel={parcel} analysisDate={analysisDate} data={layerData} />
          )}
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
          {labelPos && (
            <Marker position={labelPos} icon={anchorIcon} interactive={false} keyboard={false}>
              <Tooltip permanent direction="center" className="parcel-label" opacity={1}>
                <ParcelLabel number={parcel.numer} status={parcelStatus} source={parcel.source} longTerm={parcelRisk} />
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
          pathOptions={{ color: '#FFFFFF', weight: 3, fillColor: '#2E5B3F', fillOpacity: 1 }}
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

      {highlight && (
        <GeoJSON
          key={JSON.stringify(highlight).slice(0, 200)}
          data={highlight}
          interactive={false}
          style={{ color: '#E2A23B', weight: 4, opacity: 1, fillColor: '#E2A23B', fillOpacity: 0.35 }}
          pointToLayer={(_, latlng) =>
            L.circleMarker(latlng, { radius: 12, color: '#FFFFFF', weight: 3, fillColor: '#E2A23B', fillOpacity: 1 })
          }
        />
      )}

      <IntroView active={intro} />
      {/* zawsze zamontowana – jedna instancja Leafletu, włączanie = addLayer / removeLayer (F7) */}
      <SoilSusceptibilityLayer on={soil} />
      <InfraPins bbox={infraBox} refresh={infraRefresh} />

      <FitTo parcel={parcel} candidates={candidates} insets={insets} reducedMotion={reducedMotion} />
      {children}
      <Events onClick={onMapClick} onMoveEnd={onMoveEnd} onDragStart={onDragStart} />
    </MapContainer>
  )
})
