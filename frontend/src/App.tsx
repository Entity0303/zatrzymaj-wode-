import type { LatLngBoundsExpression, LeafletMouseEvent } from 'leaflet'
import L from 'leaflet'
import { useEffect, useMemo, useState } from 'react'
import {
  GeoJSON,
  LayersControl,
  MapContainer,
  TileLayer,
  WMSTileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import { ApiError, api, type Parcel, type Soil } from './api'

const POLAND_CENTER: [number, number] = [52.07, 19.48]
const todayIso = () => new Date().toISOString().slice(0, 10)
const minDateIso = () => {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 10)
  return d.toISOString().slice(0, 10)
}

const SOIL_COLORS: Record<number, string> = {
  1: 'bg-yellow-300',
  2: 'bg-orange-400',
  3: 'bg-orange-600',
  4: 'bg-red-700',
  5: 'bg-stone-500',
}

function FitToParcel({ parcel }: { parcel: Parcel | null }) {
  const map = useMap()
  useEffect(() => {
    if (!parcel) return
    const bounds = L.geoJSON(parcel.geometry as GeoJSON.GeoJsonObject).getBounds()
    map.fitBounds(bounds as LatLngBoundsExpression, { padding: [60, 60], maxZoom: 17 })
  }, [parcel, map])
  return null
}

function ClickToSelect({ onPick }: { onPick: (lon: number, lat: number) => void }) {
  useMapEvents({ click: (e: LeafletMouseEvent) => onPick(e.latlng.lng, e.latlng.lat) })
  return null
}

export default function App() {
  const [query, setQuery] = useState('')
  const [asOf, setAsOf] = useState(todayIso())
  const [parcel, setParcel] = useState<Parcel | null>(null)
  const [candidates, setCandidates] = useState<Parcel[]>([])
  const [soil, setSoil] = useState<Soil | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function select(p: Parcel) {
    setParcel(p)
    setCandidates([])
    setSoil(null)
    try {
      setSoil(await api.soil(p.id))
    } catch (e) {
      setError(e instanceof Error ? `Gleba: ${e.message}` : 'Błąd danych glebowych')
    }
  }

  async function run(fn: () => Promise<Parcel>) {
    setLoading(true)
    setError(null)
    try {
      await select(await fn())
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const list = (e.detail as { candidates?: Parcel[] })?.candidates ?? []
        setCandidates(list)
        setError('Znaleziono kilka działek – wybierz właściwą z listy.')
      } else {
        setError(e instanceof Error ? e.message : 'Nieznany błąd')
      }
    } finally {
      setLoading(false)
    }
  }

  function locateMe() {
    if (!navigator.geolocation) return setError('Przeglądarka nie udostępnia lokalizacji.')
    navigator.geolocation.getCurrentPosition(
      (pos) => run(() => api.parcelByPoint(pos.coords.longitude, pos.coords.latitude)),
      () => setError('Nie udało się pobrać lokalizacji.'),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const parcelKey = useMemo(() => parcel?.id ?? 'none', [parcel])

  return (
    <div className="flex h-full flex-col bg-stone-50 text-stone-900">
      <header className="flex flex-wrap items-center gap-3 border-b border-stone-200 bg-white px-4 py-3">
        <div className="mr-2 text-lg font-semibold text-emerald-700">💧 Zatrzymaj wodę</div>
        <form
          className="flex min-w-[260px] flex-1 gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (query.trim()) run(() => api.parcelById(query.trim()))
          }}
        >
          <input
            className="flex-1 rounded-lg border border-stone-300 px-3 py-2 focus:border-emerald-600 focus:outline-none"
            placeholder="Numer działki, np. 143203_2.0027.112/11 albo „Szczytno 112/11”"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            className="rounded-lg bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
            disabled={loading}
          >
            Szukaj
          </button>
        </form>
        <button
          className="rounded-lg border border-stone-300 px-3 py-2 hover:bg-stone-100"
          onClick={locateMe}
          title="Znajdź działkę, na której stoisz"
        >
          📍 Jestem na polu
        </button>
        <label className="flex items-center gap-2 text-sm">
          Data analizy
          <input
            type="date"
            className="rounded-lg border border-stone-300 px-2 py-1.5"
            value={asOf}
            min={minDateIso()}
            max={todayIso()}
            onChange={(e) => setAsOf(e.target.value)}
          />
        </label>
      </header>

      <main className="relative flex min-h-0 flex-1 flex-col md:flex-row">
        <div className="relative min-h-[50vh] flex-1">
          <MapContainer center={POLAND_CENTER} zoom={6} className="h-full w-full">
            <LayersControl position="topright">
              <LayersControl.BaseLayer checked name="Ortofotomapa (Geoportal)">
                <WMSTileLayer
                  url="https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution"
                  params={{ layers: 'Raster', format: 'image/jpeg', transparent: false }}
                  attribution="© GUGiK – geoportal.gov.pl"
                  maxZoom={19}
                />
              </LayersControl.BaseLayer>
              <LayersControl.BaseLayer name="Mapa (OpenStreetMap)">
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution="© OpenStreetMap"
                  maxZoom={19}
                />
              </LayersControl.BaseLayer>
              <LayersControl.Overlay name="Gleby – podatność na suszę (IUNG)">
                <WMSTileLayer
                  url="https://sgeo.iung.pl/geoserver/Susza/wms"
                  params={{ layers: 'Susza:katgl_landuse2024', format: 'image/png', transparent: true }}
                  opacity={0.55}
                  attribution="© IUNG-PIB"
                />
              </LayersControl.Overlay>
              <LayersControl.Overlay name="Rowy, cieki, zbiorniki (BDOT10k)">
                <WMSTileLayer
                  url="https://mapy.geoportal.gov.pl/wss/service/pub/guest/kompozycja_BDOT10k_WMS/MapServer/WMSServer"
                  params={{ layers: 'row,rz,kan,WPow', format: 'image/png', transparent: true }}
                  attribution="© GUGiK – BDOT10k"
                />
              </LayersControl.Overlay>
            </LayersControl>
            {parcel && (
              <GeoJSON
                key={parcelKey}
                data={parcel.geometry as GeoJSON.GeoJsonObject}
                style={{ color: '#facc15', weight: 3, fillOpacity: 0.08 }}
              />
            )}
            <FitToParcel parcel={parcel} />
            <ClickToSelect onPick={(lon, lat) => run(() => api.parcelByPoint(lon, lat))} />
          </MapContainer>
          {loading && (
            <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded-full bg-white px-4 py-2 text-sm shadow">
              Szukam działki…
            </div>
          )}
        </div>

        <aside className="w-full overflow-y-auto border-l border-stone-200 bg-white p-4 md:w-96">
          {error && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          {candidates.length > 0 && (
            <ul className="mb-4 space-y-2">
              {candidates.map((c) => (
                <li key={c.id}>
                  <button
                    className="w-full rounded-lg border border-stone-200 p-2 text-left text-sm hover:bg-stone-50"
                    onClick={() => select(c)}
                  >
                    <div className="font-medium">{c.id}</div>
                    <div className="text-stone-500">
                      {c.commune}, obręb {c.region}, {c.county}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {!parcel && candidates.length === 0 && (
            <div className="space-y-2 text-sm text-stone-600">
              <p className="text-base font-medium text-stone-800">Jak zacząć?</p>
              <p>Wpisz numer działki, kliknij swoje pole na mapie albo użyj „📍 Jestem na polu”.</p>
            </div>
          )}

          {parcel && (
            <div className="space-y-4">
              <section>
                <h2 className="text-lg font-semibold">Działka {parcel.number}</h2>
                <p className="text-sm text-stone-600">
                  {parcel.commune}, obręb {parcel.region} · {parcel.county}, woj. {parcel.voivodeship}
                </p>
                <p className="mt-1 text-sm">
                  Powierzchnia: <b>{parcel.area_ha.toFixed(2)} ha</b>
                </p>
                <p className="mt-1 break-all text-xs text-stone-400">{parcel.id}</p>
              </section>

              <section className="rounded-xl border border-stone-200 p-3">
                <h3 className="mb-2 font-medium">Gleba</h3>
                {!soil && <p className="text-sm text-stone-500">Pobieram dane glebowe…</p>}
                {soil && (
                  <>
                    {soil.agricultural_share < 0.5 && (
                      <p className="mb-2 rounded bg-amber-50 p-2 text-sm text-amber-800">
                        Uwaga: większość działki nie jest gruntem rolnym mineralnym ({soil.dominant_label}).
                      </p>
                    )}
                    <ul className="space-y-1 text-sm">
                      {soil.shares.map((s) => (
                        <li key={s.code} className="flex items-center gap-2">
                          <span className={`inline-block h-3 w-3 rounded-sm ${SOIL_COLORS[s.code] ?? 'bg-stone-300'}`} />
                          <span className="flex-1">{s.label}</span>
                          <span className="tabular-nums text-stone-500">{Math.round(s.share * 100)}%</span>
                        </li>
                      ))}
                    </ul>
                    {soil.wod_mm !== null && (
                      <p className="mt-2 text-sm">
                        Woda dostępna dla roślin (WOD): <b>~{Math.round(soil.wod_mm)} mm</b>
                      </p>
                    )}
                    <p className="mt-2 text-xs text-stone-400">Źródło: {soil.source}</p>
                  </>
                )}
              </section>

              <section className="rounded-xl border border-dashed border-stone-300 p-3 text-sm text-stone-500">
                Ocena sytuacji wodnej na dzień <b>{asOf}</b> – w budowie (pogoda, model wody w glebie, teren,
                rekomendacje).
              </section>

              <p className="text-xs text-stone-400">Źródło granic: {parcel.source}</p>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
