import type { Map as LeafletMap } from 'leaflet'
import { FileDown, Leaf } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ApiError, api, describeError, type Candidates, type Forecast, type Parcel } from '@/api'
import { OfflineBanner } from '@/components/common/Feedback'
import { StatusBadge } from '@/components/common/StatusBadge'
import { AlertsCard, BalanceCard, BottomCards, FarmCard, ForecastCard, TimelineCard } from '@/components/layout/BottomCards'
import { BottomSheet, snapHeights, type Snap } from '@/components/layout/BottomSheet'
import { BottomTabs, SideNav } from '@/components/layout/Navigation'
import { DateField, LayerPills, LocateButton, SearchBar, ViewToggle, WeatherWidget } from '@/components/layout/TopBar'
import { LegendCard, MapControls } from '@/components/map/MapOverlays'
import { POLAND_CENTER, ParcelMap, parcelBounds, parcelContains, type BaseMap, type MapInsets } from '@/components/map/ParcelMap'
import { ParcelActions, ParcelPanelBody, type ForecastState, type SearchPhase } from '@/components/panel/ParcelPanel'
import type { CropId } from '@/lib/crops'
import { todayIso } from '@/lib/dates'
import { formatHa, shortCounty } from '@/lib/format'
import { useMediaQuery, useOnline, usePrefersReducedMotion, useSavedParcels } from '@/lib/hooks'
import { layerByKey, type LayerKey } from '@/lib/layers'

const GEO_ERRORS: Record<number, string> = {
  1: 'Brak zgody na lokalizację. Zezwól na nią w ustawieniach przeglądarki.',
  2: 'Nie udało się ustalić położenia. Wyjdź na otwartą przestrzeń albo wpisz numer działki.',
  3: 'Ustalanie położenia trwa zbyt długo. Spróbuj ponownie.',
}

// Telefon: wysokość zwiniętej szuflady (uchwyt + nazwa działki + status + „Raport”)
const SHEET_COLLAPSED = 156
const SHEET_TOP = 116 // pod wyszukiwarką i pigułkami warstw
// Komputer/tablet: dolny pasek kart i odstępy 16 px (SPEC 2.4, 4.5)
const CARDS_H = 166
const MAP_BOTTOM_DESKTOP = 16 + CARDS_H + 2 // skala i atrybucje – w szczelinie nad kartami
const FLOAT_BOTTOM = 16 + CARDS_H + 24 // dół panelu, kontrolek i legendy

const round1 = (v: number) => Math.round(v * 10) / 10

export default function App() {
  const isMobile = useMediaQuery('(max-width: 767px)')
  const isDesktop = useMediaQuery('(min-width: 1280px)')
  const reducedMotion = usePrefersReducedMotion()
  const online = useOnline()
  const { saved, isSaved, toggle: toggleSave } = useSavedParcels()

  const [search, setSearch] = useState<SearchPhase>({ phase: 'idle' })
  const [candidates, setCandidates] = useState<Parcel[]>([])
  const [crops, setCrops] = useState<Record<string, CropId>>({})
  const [asOf, setAsOf] = useState(todayIso())
  const [layer, setLayer] = useState<LayerKey>('kondycja')
  const [baseMap, setBaseMap] = useState<BaseMap>('orto')
  const [pendingPoint, setPendingPoint] = useState<[number, number] | null>(null)
  const [userPoint, setUserPoint] = useState<[number, number] | null>(null)
  const [locating, setLocating] = useState(false)
  const [snap, setSnap] = useState<Snap>('collapsed')
  const [insidePopup, setInsidePopup] = useState<{ lon: number; lat: number; text: string } | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mapCenter, setMapCenter] = useState<[number, number]>([round1(POLAND_CENTER[1]), round1(POLAND_CENTER[0])])
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [forecastState, setForecastState] = useState<ForecastState>('idle')
  const [areaH, setAreaH] = useState(600)

  const mapRef = useRef<LeafletMap>(null)
  const mainRef = useRef<HTMLElement>(null)
  const reqId = useRef(0)
  const lastRequest = useRef<{ fn: () => Promise<Parcel>; kind: 'number' | 'point' } | null>(null)

  const parcel = search.phase === 'parcel' ? search.parcel : null
  const crop = parcel ? (crops[parcel.id] ?? null) : null

  // wysokość obszaru mapy – do położeń szuflady
  useLayoutEffect(() => {
    const el = mainRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setAreaH(el.clientHeight))
    ro.observe(el)
    setAreaH(el.clientHeight)
    return () => ro.disconnect()
  }, [])

  const sheetVisible = snapHeights(areaH, SHEET_COLLAPSED, SHEET_TOP)[snap]
  const insets: MapInsets = isMobile
    ? { top: 120, right: 64, bottom: SHEET_COLLAPSED + 130, left: 8 }
    : { top: 128, right: (isDesktop ? 380 : 340) + 16, bottom: FLOAT_BOTTOM, left: 76 }

  // ── wyszukiwanie działki ──────────────────────────────────────────────────────────────────
  async function find(fn: () => Promise<Parcel>, kind: 'number' | 'point') {
    const id = ++reqId.current
    lastRequest.current = { fn, kind }
    setInsidePopup(null)
    setSearch({ phase: 'loading', kind })
    setCandidates([])
    try {
      const p = await fn()
      if (id !== reqId.current) return
      setSearch({ phase: 'parcel', parcel: p })
      if (isMobile) setSnap('collapsed')
    } catch (e) {
      if (id !== reqId.current) return
      if (e instanceof ApiError && e.status === 409) {
        const d = e.detail as Candidates
        setCandidates(d.candidates ?? [])
        setSearch({ phase: 'candidates', total: d.total ?? d.candidates?.length ?? 0 })
        if (isMobile) setSnap('collapsed')
      } else {
        // błąd: poprzednia działka znika z panelu; mówimy, co nie zadziałało i co działa dalej
        setSearch({ phase: 'error', error: describeError(e, kind) })
        if (isMobile) setSnap('half')
      }
    } finally {
      if (id === reqId.current) setPendingPoint(null)
    }
  }

  const searchByNumber = (q: string) => find(() => api.parcelById(q), 'number')
  const searchByPoint = (lon: number, lat: number) => {
    setPendingPoint([lon, lat])
    find(() => api.parcelByPoint(lon, lat), 'point')
  }
  const retry = () => {
    if (lastRequest.current) find(lastRequest.current.fn, lastRequest.current.kind)
  }

  function pickCandidate(p: Parcel) {
    reqId.current++
    setCandidates([])
    setSearch({ phase: 'parcel', parcel: p })
    if (isMobile) setSnap('collapsed')
  }

  function onMapClick(lon: number, lat: number) {
    if (parcel && parcelContains(parcel, lon, lat)) {
      // SPEC 5.4: klik wewnątrz działki = wartość aktywnej warstwy w punkcie (warstwy jeszcze nie liczymy)
      setInsidePopup({ lon, lat, text: `${layerByKey(layer).label}: brak danych w tym punkcie – warstwa w budowie.` })
      return
    }
    searchByPoint(lon, lat)
  }

  function locate() {
    const fail = (message: string) => {
      setSearch({
        phase: 'error',
        error: {
          title: 'Nie znamy Twojej lokalizacji',
          message,
          stillWorks: 'Możesz wpisać numer działki albo kliknąć pole na mapie.',
          retryable: false,
        },
      })
      if (isMobile) setSnap('half')
    }
    if (!navigator.geolocation) return fail('Ta przeglądarka nie udostępnia lokalizacji.')
    if (!window.isSecureContext)
      return fail('Lokalizacja działa tylko przez bezpieczne połączenie (https) albo na tym komputerze.')
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        const { longitude, latitude } = pos.coords
        setUserPoint([longitude, latitude])
        searchByPoint(longitude, latitude)
      },
      (err) => {
        setLocating(false)
        fail(GEO_ERRORS[err.code] ?? 'Nie udało się pobrać lokalizacji.')
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 },
    )
  }

  function backToParcel() {
    const map = mapRef.current
    if (!parcel || !map) return
    const opts = {
      paddingTopLeft: [insets.left + 24, insets.top + 24] as [number, number],
      paddingBottomRight: [insets.right + 24, insets.bottom + 24] as [number, number],
      maxZoom: 18,
    }
    if (reducedMotion) map.fitBounds(parcelBounds(parcel), { ...opts, animate: false })
    else map.flyToBounds(parcelBounds(parcel), { ...opts, duration: 1 })
  }

  const focusSearch = () => {
    if (isMobile) setSnap('collapsed')
    document.querySelector<HTMLInputElement>('input[aria-label="Numer działki"]')?.focus()
  }

  // ── pogoda (Open-Meteo): środek działki albo środek mapy ─────────────────────────────────
  const weatherTarget = useMemo<[number, number]>(() => {
    if (parcel) {
      const c = parcelBounds(parcel).getCenter()
      return [c.lng, c.lat]
    }
    return mapCenter
  }, [parcel, mapCenter])

  useEffect(() => {
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      setForecastState('loading')
      api
        .forecast(weatherTarget[0], weatherTarget[1], ctrl.signal)
        .then((f) => {
          setForecast(f)
          setForecastState('ok')
        })
        .catch((e) => {
          if ((e as Error).name === 'AbortError') return
          setForecast(null)
          setForecastState('error')
        })
    }, 400)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [weatherTarget])

  const onMoveEnd = useCallback((lon: number, lat: number) => {
    setMapCenter((prev) => {
      const next: [number, number] = [round1(lon), round1(lat)]
      return prev[0] === next[0] && prev[1] === next[1] ? prev : next
    })
  }, [])

  const where = parcel ? `dla działki ${parcel.numer}` : 'dla środka mapy'
  const historical = asOf !== todayIso()
  const updated = forecast?.teraz.czas
    ? new Date(forecast.teraz.czas).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' })
    : null

  function showToast(t: string) {
    setToast(t)
    setTimeout(() => setToast(null), 2000)
  }

  const legend = layerByKey(layer)
  const panelProps = {
    state: search,
    crop,
    onCropChange: (c: CropId) => {
      if (parcel) setCrops((m) => ({ ...m, [parcel.id]: c }))
    },
    asOf,
    forecastState,
    saved: parcel ? isSaved(parcel.id) : false,
    onToggleSave: () => {
      if (parcel) toggleSave(parcel)
    },
    onCopied: () => showToast('Skopiowano identyfikator działki'),
    onRetry: retry,
    onFocusSearch: focusSearch,
    onLocate: locate,
  }

  const searchBar = (
    <SearchBar
      loading={search.phase === 'loading'}
      error={search.phase === 'error' ? search.error.title : null}
      candidates={candidates}
      total={search.phase === 'candidates' ? search.total : candidates.length}
      onSearch={searchByNumber}
      onPick={pickCandidate}
      onDismiss={() => {
        if (candidates.length) {
          setCandidates([])
          setSearch({ phase: 'idle' })
        }
      }}
      className={isMobile ? 'min-w-0 flex-1' : 'max-w-[560px] min-w-[300px] flex-1'}
    />
  )

  const weather = (compact?: boolean) => (
    <WeatherWidget
      forecast={forecast}
      loading={forecastState === 'loading'}
      error={forecastState === 'error'}
      where={where}
      compact={compact}
    />
  )

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-bg">
      <div className="flex min-h-0 flex-1">
        <SideNav />
        <main
          ref={mainRef}
          className="relative min-w-0 flex-1 overflow-hidden"
          style={{ ['--map-bottom' as string]: `${isMobile ? sheetVisible + 4 : MAP_BOTTOM_DESKTOP}px` }}
        >
          <ParcelMap
            ref={mapRef}
            baseMap={baseMap}
            parcel={parcel}
            parcelStatus="nodata"
            candidates={candidates}
            pendingPoint={pendingPoint}
            userPoint={userPoint}
            insidePopup={insidePopup}
            insets={insets}
            reducedMotion={reducedMotion}
            onMapClick={onMapClick}
            onMoveEnd={onMoveEnd}
            onSelectCandidate={pickCandidate}
            onClosePopup={() => setInsidePopup(null)}
          />

          {/* ── górny pływający pasek (SPEC 4.2 / 12) ── */}
          {isMobile ? (
            <div className="pointer-events-none absolute inset-x-0 top-0 z-[1200] space-y-2 pt-3">
              <div className="pointer-events-auto flex items-start gap-2 px-3">
                {searchBar}
                <LocateButton locating={locating} onClick={locate} iconOnly />
              </div>
              <LayerPills value={layer} onChange={setLayer} className="pointer-events-auto px-3 pb-2" />
            </div>
          ) : (
            <div className="pointer-events-none absolute inset-x-4 top-4 z-[1200] space-y-3">
              <div className="flex items-start gap-3 [&>*]:pointer-events-auto">
                {searchBar}
                <LocateButton locating={locating} onClick={locate} />
                <div className="ml-auto">{weather()}</div>
                <DateField value={asOf} onChange={setAsOf} />
              </div>
              <div className="flex max-w-full items-center gap-3 [&>*]:pointer-events-auto">
                <LayerPills value={layer} onChange={setLayer} className="min-w-0 py-1" />
                <ViewToggle />
              </div>
            </div>
          )}

          {!online && (
            <div className="pointer-events-none absolute inset-x-0 top-[124px] z-[1250] flex justify-center px-3 md:top-[132px]">
              <OfflineBanner />
            </div>
          )}

          {/* ── kontrolki mapy: komputer – lewy dolny róg; telefon – po prawej (SPEC 5.2, 12) ── */}
          <MapControls
            className={isMobile ? 'absolute top-[120px] right-3 z-[1000]' : 'absolute left-4 z-[1000]'}
            style={isMobile ? undefined : { bottom: FLOAT_BOTTOM }}
            onZoomIn={() => mapRef.current?.zoomIn()}
            onZoomOut={() => mapRef.current?.zoomOut()}
            onBackToParcel={backToParcel}
            onLocate={locate}
            canGoBack={!!parcel}
            baseMap={baseMap}
            onBaseMapChange={setBaseMap}
          />

          {/* ── legenda aktywnej warstwy (SPEC 5.3) ── */}
          {(!isMobile || snap !== 'full') && (
            <LegendCard
              title={legend.label}
              legend={legend.legend}
              status={isMobile ? 'Brak danych – w budowie' : 'Brak danych dla działki – warstwa w budowie'}
              compact={isMobile}
              className={isMobile ? 'absolute left-3 z-[1000] w-48' : 'absolute right-[372px] z-[1000] xl:right-[412px]'}
              style={{ bottom: isMobile ? sheetVisible + 32 : FLOAT_BOTTOM }}
            />
          )}

          {/* ── prawy panel działki: 380 px komputer, 340 px tablet (SPEC 4.4, 12) ── */}
          {!isMobile && (
            <aside
              aria-label="Panel działki"
              className="absolute top-[128px] right-4 z-[1100] flex w-[340px] flex-col overflow-hidden rounded-xl border bg-surface shadow-float xl:w-[380px]"
              style={{ bottom: FLOAT_BOTTOM }}
            >
              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                <ParcelPanelBody {...panelProps} />
              </div>
            </aside>
          )}

          {/* ── dolny pasek 5 kart (SPEC 4.5) ── */}
          {!isMobile && (
            <div className="absolute inset-x-4 bottom-4 z-[1000]" style={{ height: CARDS_H }}>
              <BottomCards
                savedCount={saved.length}
                forecast={forecast}
                forecastLoading={forecastState === 'loading'}
                forecastError={forecastState === 'error'}
                where={where}
                historical={historical}
                updated={updated}
              />
            </div>
          )}

          {/* ── szuflada od dołu (telefon) ── */}
          {isMobile && (
            <BottomSheet
              areaHeight={areaH}
              collapsedHeight={SHEET_COLLAPSED}
              topReserved={SHEET_TOP}
              snap={snap}
              onSnapChange={setSnap}
              header={
                <SheetHeader
                  search={search}
                  parcel={parcel}
                  saved={parcel ? isSaved(parcel.id) : false}
                  onToggleSave={panelProps.onToggleSave}
                  onCopied={panelProps.onCopied}
                />
              }
            >
              <div className="space-y-5">
                <div className="flex gap-2 [&>label]:min-w-0 [&>label]:flex-1">
                  <DateField value={asOf} onChange={setAsOf} compact />
                  {weather(true)}
                </div>
                <ParcelPanelBody {...panelProps} hideHeader />
                <section className="space-y-3 border-t pt-5">
                  <h3 className="text-lg leading-6 font-semibold">Gospodarstwo i pogoda</h3>
                  <div className="h-[224px]">
                    <ForecastCard
                      forecast={forecast}
                      loading={forecastState === 'loading'}
                      error={forecastState === 'error'}
                      where={where}
                      historical={historical}
                    />
                  </div>
                  <div className="h-[140px]">
                    <FarmCard savedCount={saved.length} />
                  </div>
                  <div className="h-[140px]">
                    <BalanceCard />
                  </div>
                  <div className="h-[140px]">
                    <AlertsCard />
                  </div>
                  <div className="h-[156px]">
                    <TimelineCard updated={updated} />
                  </div>
                </section>
              </div>
            </BottomSheet>
          )}

          {toast && (
            <div
              role="status"
              className="absolute bottom-6 left-1/2 z-[1400] -translate-x-1/2 rounded-full bg-text px-4 py-2 text-sm text-white shadow-float"
            >
              {toast}
            </div>
          )}
        </main>
      </div>
      <BottomTabs />
    </div>
  )
}

/** Zwinięta część szuflady: nazwa działki + status + „Raport” (SPEC 12). */
function SheetHeader({
  search,
  parcel,
  saved,
  onToggleSave,
  onCopied,
}: {
  search: SearchPhase
  parcel: Parcel | null
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
}) {
  if (parcel)
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
            <Leaf className="size-5" aria-hidden />
          </span>
          <h2 className="min-w-0 flex-1 truncate text-[22px] leading-7 font-semibold">Działka {parcel.numer}</h2>
          <span className="tabular shrink-0 text-lg font-semibold" title="Pomiar – z granic działki w ewidencji (ULDK GUGiK)">
            {formatHa(parcel.powierzchnia_ha)} ha
          </span>
        </div>
        <p className="truncate pl-[46px] text-sm leading-5 text-text-muted">
          gm. {parcel.gmina}, obręb {parcel.obreb} · {shortCounty(parcel.powiat)}
        </p>
        <div className="flex items-center gap-1 pl-[46px]">
          <StatusBadge status="nodata" size="sm" />
          <span className="flex-1" />
          <ParcelActions parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />
          <button
            type="button"
            disabled
            title="Raport PDF – w budowie"
            className="ml-1 flex h-11 items-center gap-1.5 rounded-md bg-brand-dark px-3 text-sm font-semibold text-white opacity-60"
          >
            <FileDown className="size-4" aria-hidden /> Raport
          </button>
        </div>
      </div>
    )
  const title =
    search.phase === 'loading'
      ? 'Szukam działki…'
      : search.phase === 'error'
        ? search.error.title
        : search.phase === 'candidates'
          ? `Znaleziono ${search.total} działek`
          : 'Znajdź swoją działkę'
  const sub =
    search.phase === 'candidates'
      ? 'Wybierz z listy pod wyszukiwarką lub kliknij numer na mapie'
      : search.phase === 'idle'
        ? 'Wpisz numer, kliknij pole albo użyj lokalizacji'
        : search.phase === 'error'
          ? 'Przesuń w górę, aby zobaczyć szczegóły'
          : 'Pobieram dane z ewidencji (ULDK GUGiK)'
  return (
    <div className="min-h-12">
      <h2 className="text-lg leading-6 font-semibold">{title}</h2>
      <p className="text-sm leading-5 text-text-muted">{sub}</p>
    </div>
  )
}
