import type { Map as LeafletMap } from 'leaflet'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ApiError, api, describeError } from '@/api/client'
import type { CropId, Parcel, ParcelCandidates } from '@/api/types'
import { OfflineBanner } from '@/components/OfflineBanner'
import { SampleDataBanner } from '@/components/SampleDataBanner'
import { parcelBounds, parcelContains, type MapInsets } from '@/features/map/geo'
import { layerByKey, type LayerKey } from '@/features/map/layers'
import { LegendCard } from '@/features/map/LegendCard'
import { MapControls } from '@/features/map/MapControls'
import { POLAND_CENTER, ParcelMap, type BaseMap } from '@/features/map/ParcelMap'
import { MobileSheetHeader } from '@/features/parcel-panel/MobileSheetHeader'
import { ParcelPanel } from '@/features/parcel-panel/ParcelPanel'
import type { SearchPhase } from '@/features/parcel-panel/types'
import { useAnalysis } from '@/features/parcel-panel/useAnalysis'
import { SearchBar } from '@/features/search/SearchBar'
import { useForecast } from '@/features/weather/useForecast'
import { WeatherWidget } from '@/features/weather/WeatherWidget'
import { DateField } from '@/components/DateField'
import { BottomCards } from '@/layout/BottomCards'
import { BottomCardsStack } from '@/layout/BottomCardsStack'
import { BottomTabs } from '@/layout/BottomTabs'
import { MobileSheet, snapHeights, type Snap } from '@/layout/MobileSheet'
import { Sidebar } from '@/layout/Sidebar'
import { TopBar } from '@/layout/TopBar'
import { todayIso } from '@/lib/dates'
import { readLink, shareLink, writeLink } from '@/lib/deepLink'
import { useReportDownload } from '@/features/reports/useReportDownload'
import { useMediaQuery, useOnline, usePrefersReducedMotion, useSavedParcels } from '@/lib/hooks'
import { mockRequested } from '@/mocks/useMockAnalysis'
import { locale, useLang } from '@/lib/i18n'

/** Ekran Start (SPEC 4, 12): mapa + panel działki + dolny pasek kart / szuflada na telefonie. */

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

export default function Start() {
  const { t } = useLang()
  const isMobile = useMediaQuery('(max-width: 767px)')
  const isDesktop = useMediaQuery('(min-width: 1280px)')
  const reducedMotion = usePrefersReducedMotion()
  const online = useOnline()
  const { saved, isSaved, toggle: toggleSave } = useSavedParcels()

  const [search, setSearch] = useState<SearchPhase>({ phase: 'idle' })
  const [candidates, setCandidates] = useState<Parcel[]>([])
  const [crops, setCrops] = useState<Record<string, CropId>>({})
  // link z adresu (?dzialka=&uprawa=&data=) – czytany raz przy wejściu
  const [link] = useState(readLink)
  const [asOf, setAsOf] = useState(link.data ?? todayIso())
  const [layer, setLayer] = useState<LayerKey>('kondycja')
  const [baseMap, setBaseMap] = useState<BaseMap>('orto')
  const [pendingPoint, setPendingPoint] = useState<[number, number] | null>(null)
  const [userPoint, setUserPoint] = useState<[number, number] | null>(null)
  const [locating, setLocating] = useState(false)
  const [snap, setSnap] = useState<Snap>('collapsed')
  const [insidePopup, setInsidePopup] = useState<{ lon: number; lat: number; text: string } | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mapCenter, setMapCenter] = useState<[number, number]>([round1(POLAND_CENTER[1]), round1(POLAND_CENTER[0])])
  const [areaH, setAreaH] = useState(600)

  const mapRef = useRef<LeafletMap>(null)
  const mainRef = useRef<HTMLElement>(null)
  const reqId = useRef(0)
  // uprawa z linku – przypisywana do działki, gdy wyszukiwanie ją znajdzie
  const pendingCrop = useRef(link.uprawa)
  const lastRequest = useRef<{ fn: () => Promise<Parcel>; kind: 'number' | 'point' } | null>(null)

  const parcel = search.phase === 'parcel' ? search.parcel : null
  const crop = parcel ? (crops[parcel.id] ?? null) : null
  // analiza: startuje po wyborze uprawy, zmiana uprawy/daty przelicza; dopóki backend zwraca 501,
  // w trybie deweloperskim można podejrzeć mock z symulacją ładowania (?dane=przykladowe)
  const mock = mockRequested()
  const { run, retry: retryAnalysis } = useAnalysis(parcel?.id ?? null, crop, asOf)
  const analysis = run.phase === 'done' ? run.analysis : null

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
      applyPendingCrop(p)
      setSearch({ phase: 'parcel', parcel: p })
      if (isMobile) setSnap('collapsed')
    } catch (e) {
      if (id !== reqId.current) return
      if (e instanceof ApiError && e.status === 409) {
        const d = e.detail as ParcelCandidates
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

  function applyPendingCrop(p: Parcel) {
    const c = pendingCrop.current
    if (!c) return
    pendingCrop.current = null
    setCrops((m) => ({ ...m, [p.id]: c }))
  }

  function pickCandidate(p: Parcel) {
    reqId.current++
    applyPendingCrop(p)
    setCandidates([])
    setSearch({ phase: 'parcel', parcel: p })
    if (isMobile) setSnap('collapsed')
  }

  function onMapClick(lon: number, lat: number) {
    if (parcel && parcelContains(parcel, lon, lat)) {
      // SPEC 5.4: klik wewnątrz działki = wartość aktywnej warstwy w punkcie (warstwy jeszcze nie liczymy)
      setInsidePopup({ lon, lat, text: t('{layer}: brak danych w tym punkcie – warstwa w budowie.', { layer: t(layerByKey(layer).label) }) })
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
    document.querySelector<HTMLInputElement>('input[data-parcel-search]')?.focus()
  }

  // ── link: otwarcie adresu z ?dzialka= od razu wyszukuje działkę (i liczy analizę, gdy jest uprawa) ──
  const linkStarted = useRef(false)
  useEffect(() => {
    if (linkStarted.current || !link.dzialka) return
    linkStarted.current = true
    searchByNumber(link.dzialka)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tylko raz, przy wejściu
  }, [])

  // adres w pasku = bieżąca działka, uprawa i data (można go skopiować wprost z przeglądarki)
  useEffect(() => {
    if (parcel) writeLink({ dzialka: parcel.id, uprawa: crop, data: asOf })
  }, [parcel, crop, asOf])

  function copyLink() {
    if (!parcel) return
    const href = shareLink({ dzialka: parcel.id, uprawa: crop, data: asOf })
    if (!navigator.clipboard) return showToast(t('Skopiuj adres z paska przeglądarki – to link do tej analizy'))
    navigator.clipboard.writeText(href).then(
      () => showToast(t('Skopiowano link do tej analizy')),
      () => showToast(t('Skopiuj adres z paska przeglądarki – to link do tej analizy')),
    )
  }

  // ── raport PDF: te same parametry co analiza ─────────────────────────────────────────────
  const report = useReportDownload(
    parcel && crop && analysis ? { parcelId: parcel.id, numer: parcel.numer, crop, date: asOf } : null,
  )
  const clearReportError = report.clearError
  useEffect(() => clearReportError(), [parcel?.id, crop, asOf, clearReportError])
  // telefon: błąd raportu ma być widoczny – szuflada do połowy
  useEffect(() => {
    if (report.error && isMobile) setSnap('half')
  }, [report.error, isMobile])

  // ── pogoda (Open-Meteo): środek działki albo środek mapy ─────────────────────────────────
  const weatherTarget = useMemo<[number, number]>(() => {
    if (parcel) {
      const c = parcelBounds(parcel).getCenter()
      return [c.lng, c.lat]
    }
    return mapCenter
  }, [parcel, mapCenter])

  const { forecast, state: forecastState } = useForecast(weatherTarget)

  const onMoveEnd = useCallback((lon: number, lat: number) => {
    setMapCenter((prev) => {
      const next: [number, number] = [round1(lon), round1(lat)]
      return prev[0] === next[0] && prev[1] === next[1] ? prev : next
    })
  }, [])

  const where = parcel ? t('dla działki {numer}', { numer: parcel.numer }) : t('dla środka mapy')
  const historical = asOf !== todayIso()
  const updated = forecast?.teraz.czas
    ? new Date(forecast.teraz.czas).toLocaleString(locale(), { dateStyle: 'short', timeStyle: 'short' })
    : null

  function showToast(text: string) {
    setToast(text)
    setTimeout(() => setToast(null), 2500)
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
    run,
    onRetryAnalysis: retryAnalysis,
    saved: parcel ? isSaved(parcel.id) : false,
    onToggleSave: () => {
      if (parcel) toggleSave(parcel)
    },
    onCopied: () => showToast(t('Skopiowano identyfikator działki')),
    onRetry: retry,
    onFocusSearch: focusSearch,
    onLocate: locate,
    report,
    onCopyLink: parcel ? copyLink : undefined,
  }

  const searchBar = (
    <SearchBar
      loading={search.phase === 'loading'}
      error={search.phase === 'error' ? t(search.error.title, search.error.vars) : null}
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
      bare={!compact}
    />
  )

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-bg">
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main
          ref={mainRef}
          className="relative min-w-0 flex-1 overflow-hidden"
          style={{ ['--map-bottom' as string]: `${isMobile ? sheetVisible + 4 : MAP_BOTTOM_DESKTOP}px` }}
        >
          <ParcelMap
            ref={mapRef}
            baseMap={baseMap}
            parcel={parcel}
            parcelStatus={analysis?.status.level ?? 'no_data'}
            layer={layer}
            analysisDate={asOf}
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

          <TopBar
            isMobile={isMobile}
            search={searchBar}
            weather={weather()}
            locating={locating}
            onLocate={locate}
            asOf={asOf}
            onAsOfChange={setAsOf}
            layer={layer}
            onLayerChange={setLayer}
          />

          {mock && (
            <div className="pointer-events-none absolute inset-x-0 bottom-3 z-[1450] flex justify-center px-3 md:top-[76px] md:bottom-auto">
              <SampleDataBanner />
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
              className={isMobile ? 'absolute left-3 z-[1000] w-56' : 'absolute right-[372px] z-[1000] xl:right-[412px]'}
              style={{ bottom: isMobile ? sheetVisible + 32 : FLOAT_BOTTOM }}
            />
          )}

          {/* ── prawy panel działki: 380 px komputer, 340 px tablet (SPEC 4.4, 12) ── */}
          {!isMobile && (
            <aside
              aria-label={t('Panel działki')}
              className="absolute top-[128px] right-4 z-[1100] flex w-[340px] flex-col overflow-hidden rounded-xl bg-surface shadow-float xl:w-[380px]"
              style={{ bottom: FLOAT_BOTTOM }}
            >
              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                <ParcelPanel {...panelProps} />
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
            <MobileSheet
              areaHeight={areaH}
              collapsedHeight={SHEET_COLLAPSED}
              topReserved={SHEET_TOP}
              snap={snap}
              onSnapChange={setSnap}
              header={
                <MobileSheetHeader
                  search={search}
                  parcel={parcel}
                  saved={parcel ? isSaved(parcel.id) : false}
                  onToggleSave={panelProps.onToggleSave}
                  onCopied={panelProps.onCopied}
                  status={analysis?.status.level ?? 'no_data'}
                  onReport={analysis ? report.download : undefined}
                  reportBusy={report.busy}
                />
              }
            >
              <div className="space-y-5">
                <div className="flex gap-2 [&>label]:min-w-0 [&>label]:flex-1">
                  <DateField value={asOf} onChange={setAsOf} compact />
                  {weather(true)}
                </div>
                <ParcelPanel {...panelProps} hideHeader />
                <BottomCardsStack
                  savedCount={saved.length}
                  forecast={forecast}
                  forecastLoading={forecastState === 'loading'}
                  forecastError={forecastState === 'error'}
                  where={where}
                  historical={historical}
                  updated={updated}
                />
              </div>
            </MobileSheet>
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
