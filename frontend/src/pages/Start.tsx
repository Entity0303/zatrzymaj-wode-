import type { Map as LeafletMap } from 'leaflet'
import { Suspense, lazy, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown, ChevronUp, LayoutPanelTop } from 'lucide-react'
import L from 'leaflet'
import { ApiError, api, describeError } from '@/api/client'
import { isPlaceQuery, type Place } from '@/api/places.proposal'
import type { CropId, Parcel, ParcelCandidates } from '@/api/types'
import { OfflineBanner } from '@/components/OfflineBanner'
import { SampleDataBanner } from '@/components/SampleDataBanner'
import { parcelBounds, parcelContains, type MapInsets } from '@/features/map/geo'
import { layerByKey, type LayerKey } from '@/features/map/layers'
import { useLayerData } from '@/features/map/layers/useLayerData'
import { LegendCard } from '@/features/map/LegendCard'
import { MapControls } from '@/features/map/MapControls'
import { POLAND_CENTER, ParcelMap, type BaseMap } from '@/features/map/ParcelMap'
import { MobileSheetHeader } from '@/features/parcel-panel/MobileSheetHeader'
import { ParcelPanel } from '@/features/parcel-panel/ParcelPanel'
import { ParcelSummary } from '@/features/parcel-panel/ParcelSummary'
import { ExploreBar } from '@/features/intro/ExploreBar'
import { IntroHero } from '@/features/intro/IntroHero'
import { useDemoExamples } from '@/features/intro/useDemoExamples'
import { SOIL_SUSCEPTIBILITY_LEGEND } from '@/features/map/SoilSusceptibilityLayer'
import { LocateButton } from '@/features/search/LocateButton'
import { Passport } from '@/features/passport/Passport'
import { exampleDate, type Example } from '@/features/parcel-panel/examples'
import { InfraReportWizard } from '@/features/infra-reports/InfraReportWizard'
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
import { formatDatePl, formatNum } from '@/lib/format'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { readLink, shareLink, writeLink } from '@/lib/deepLink'
import { rememberAnalysis, useSettings, useUiPrefs } from '@/lib/storage'
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


// karty schowane: przycisk „Pogoda, gospodarstwo…” 44 px w lewym dolnym rogu
const TOGGLE_H = 44

const round1 = (v: number) => Math.round(v * 10) / 10

// Widok 3D – osobny plik i biblioteka (MapLibre GL), pobierane dopiero po kliknięciu „3D”
const Terrain3D = lazy(() => import('@/features/map3d/Terrain3D'))

// Komputer: paszport wodny jako szeroki panel (SPEC 7)
const PASSPORT_W = 640

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
  const [layer, setLayer] = useState<LayerKey>('teren') // Kondycja upraw nie ma jeszcze danych
  const [view, setView] = useState<'2d' | '3d'>('2d')
  const [settings] = useSettings()
  const [ui, setUi] = useUiPrefs()
  const [baseMap, setBaseMap] = useState<BaseMap>(settings.baseMap)
  const [pendingPoint, setPendingPoint] = useState<[number, number] | null>(null)
  const [userPoint, setUserPoint] = useState<[number, number] | null>(null)
  const [locating, setLocating] = useState(false)
  const [snap, setSnap] = useState<Snap>(() => (link.dzialka ? 'collapsed' : 'half')) // bez linku: przykłady widoczne od razu
  const [insidePopup, setInsidePopup] = useState<{ lon: number; lat: number; text: string } | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mapCenter, setMapCenter] = useState<[number, number]>([round1(POLAND_CENTER[1]), round1(POLAND_CENTER[0])])
  const [areaH, setAreaH] = useState(600)
  // paszport wodny: przypięty do konkretnego wyniku – nowa analiza go zamyka
  const [passportFor, setPassportFor] = useState<object | null>(null)
  const [highlight, setHighlight] = useState<GeoJSON.Geometry | null>(null)
  // zgłoszenie rowu/zbiornika: otwarty kreator, wskazane miejsce, tryb wskazywania na mapie
  const [infra, setInfra] = useState<{ point: [number, number] | null; picking: boolean } | null>(null)
  const [infraRefresh, setInfraRefresh] = useState(0)

  const mapRef = useRef<LeafletMap>(null)
  const mainRef = useRef<HTMLElement>(null)
  const reqId = useRef(0)
  // uprawa z linku – przypisywana do działki, gdy wyszukiwanie ją znajdzie
  const pendingCrop = useRef(link.uprawa)
  // karta powitalna (B0): tylko przy wejściu bez działki w linku; znika po pierwszym działaniu
  const [hero, setHero] = useState(() => !link.dzialka)
  const demoExamples = useDemoExamples()
  // przykład jednym klikiem: na telefonie po znalezieniu działki szuflada do połowy (wynik od razu widoczny)
  const expandAfterFind = useRef(false)
  // ?widok=paszport – po pierwszej gotowej analizie od razu paszport wodny
  const pendingPassport = useRef(link.widok === 'paszport')
  const lastRequest = useRef<{ fn: () => Promise<Parcel>; kind: 'number' | 'point' } | null>(null)

  const parcel = search.phase === 'parcel' ? search.parcel : null
  const crop = parcel ? (crops[parcel.id] ?? null) : null
  // analiza: startuje po wyborze uprawy, zmiana uprawy/daty przelicza; dopóki backend zwraca 501,
  // w trybie deweloperskim można podejrzeć mock z symulacją ładowania (?dane=przykladowe)
  const mock = mockRequested()
  const { run, retry: retryAnalysis } = useAnalysis(parcel?.id ?? null, crop, asOf)
  const analysis = run.phase === 'done' ? run.analysis : null
  const layerState = useLayerData(layer, parcel?.id ?? null, asOf)
  const passportOpen = !!analysis && passportFor === analysis

  // wysokość obszaru mapy – do położeń szuflady
  useLayoutEffect(() => {
    const el = mainRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setAreaH(el.clientHeight))
    ro.observe(el)
    setAreaH(el.clientHeight)
    return () => ro.disconnect()
  }, [])

  // komputer/tablet: dolny pasek kart tylko na życzenie (mniej rzeczy naraz na ekranie)
  const cardsShown = !isMobile && ui.cards
  // komputer: przy wybranej działce domyślnie mała karta podsumowania, pełny panel na życzenie
  const summaryOnly = !isMobile && !ui.panel && search.phase === 'parcel' && !passportOpen && !infra
  const FLOAT_BOTTOM = cardsShown ? 16 + CARDS_H + 24 : 16 // dół panelu i legendy
  const CONTROLS_BOTTOM = cardsShown ? FLOAT_BOTTOM + 28 : 16 + TOGGLE_H + 36 // kontrolki nad skalą mapy
  const MAP_BOTTOM_DESKTOP = cardsShown ? 16 + CARDS_H + 2 : 16 + TOGGLE_H + 4 // skala i atrybucje
  const sheetVisible = snapHeights(areaH, SHEET_COLLAPSED, SHEET_TOP)[snap]
  const insets: MapInsets = isMobile
    ? { top: 120, right: 64, bottom: SHEET_COLLAPSED + 130, left: 8 }
    : { top: 128, right: (passportOpen ? PASSPORT_W : isDesktop ? 380 : 340) + 16, bottom: FLOAT_BOTTOM, left: 76 }

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
      if (isMobile) setSnap(expandAfterFind.current ? 'half' : 'collapsed')
      expandAfterFind.current = false
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
  // komunikaty o błędach usług pokazujemy dopiero po działaniu użytkownika (nie przy wejściu z linku)
  const userActed = useRef(false)

  // ── miejsce po nazwie („Tczów”): lista obrębów/gmin → mapa przybliża → klik w pole ──────────
  const [places, setPlaces] = useState<Place[]>([])
  const [placeBusy, setPlaceBusy] = useState(false)
  const [placeError, setPlaceError] = useState<string | null>(null)
  const placeReq = useRef(0)

  async function searchPlace(q: string) {
    const id = ++placeReq.current
    setPlaces([])
    setPlaceError(null)
    setPlaceBusy(true)
    try {
      const r = await api.places(q)
      if (id !== placeReq.current) return
      if (r.places.length === 1) pickPlace(r.places[0])
      else setPlaces(r.places)
    } catch (e) {
      if (id !== placeReq.current) return
      setPlaceError(
        e instanceof ApiError && e.status === 404 && (e.detail as { message?: string } | null)?.message === 'nie znaleziono miejsca'
          ? t('Nie znaleziono miejsca „{q}”', { q })
          : e instanceof ApiError && (e.status === 404 || e.status === 501)
            ? t('Szukanie po samej nazwie jeszcze w budowie – wpisz nazwę z numerem działki, np. „{q} 123”', { q })
            : t('Nie udało się wyszukać miejsca – spróbuj ponownie'),
      )
    } finally {
      if (id === placeReq.current) setPlaceBusy(false)
    }
  }

  function pickPlace(pl: Place) {
    setPlaces([])
    setPlaceError(null)
    const map = mapRef.current
    if (!map) return
    const b = L.latLngBounds([pl.bbox[1], pl.bbox[0]], [pl.bbox[3], pl.bbox[2]])
    const opts = {
      paddingTopLeft: [insets.left + 24, insets.top + 24] as [number, number],
      paddingBottomRight: [insets.right + 24, insets.bottom + 24] as [number, number],
      maxZoom: 15,
    }
    if (reducedMotion) map.fitBounds(b, { ...opts, animate: false })
    else map.flyToBounds(b, { ...opts, duration: 1 })
    showToast(t('{name}: kliknij swoje pole na mapie', { name: pl.name }))
  }

  /** jedno pole wyszukiwania, 3 rodzaje zapytań: identyfikator / „obręb numer” → działka, sama nazwa → miejsce */
  const onSearch = (q: string) => {
    userActed.current = true
    setHero(false)
    if (isPlaceQuery(q)) return searchPlace(q)
    setPlaces([])
    setPlaceError(null)
    searchByNumber(q)
  }
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
    userActed.current = true
    setHero(false)
    if (infra?.picking) {
      setInfra({ point: [lon, lat], picking: false })
      if (isMobile) setSnap('full')
      return
    }
    if (parcel && parcelContains(parcel, lon, lat)) {
      // SPEC 5.4: klik wewnątrz działki = wartość aktywnej warstwy w punkcie
      const name = t(layerByKey(layer).label)
      setInsidePopup({ lon, lat, text: t('{layer}: sprawdzam wartość w tym punkcie…', { layer: name }) })
      api.layerPoint(layer, lon, lat, asOf).then(
        (v) => setInsidePopup((cur) => (cur && cur.lon === lon && cur.lat === lat ? { lon, lat, text: t(v.text) } : cur)),
        (e) =>
          setInsidePopup((cur) =>
            cur && cur.lon === lon && cur.lat === lat
              ? {
                  lon,
                  lat,
                  text:
                    e instanceof ApiError && (e.status === 404 || e.status === 501)
                      ? t('{layer}: brak danych w tym punkcie – warstwa w budowie.', { layer: name })
                      : t('{layer}: nie udało się pobrać wartości w tym punkcie.', { layer: name }),
                }
              : cur,
          ),
      )
      return
    }
    searchByPoint(lon, lat)
  }

  function locate() {
    userActed.current = true
    setHero(false)
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

  // tytuł karty przeglądarki: nazwa produktu + podtytuł w bieżącym języku
  const tagline = t(BRAND_TAGLINE)
  useEffect(() => {
    document.title = `${BRAND_NAME} – ${tagline}`
  }, [tagline])

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
    const href = shareLink({ dzialka: parcel.id, uprawa: crop, data: asOf, widok: passportOpen ? 'paszport' : null })
    if (!navigator.clipboard) return showToast(t('Skopiuj adres z paska przeglądarki – to link do tej analizy'))
    navigator.clipboard.writeText(href).then(
      () => showToast(t('Skopiowano link do tej analizy')),
      () => showToast(t('Skopiuj adres z paska przeglądarki – to link do tej analizy')),
    )
  }

  // ── paszport wodny i „Pokaż na mapie” ──────────────────────────────────────────────────────
  function openPassport() {
    if (!analysis) return
    setPassportFor(analysis)
    if (isMobile) setSnap('full')
  }
  const closePassport = useCallback(() => setPassportFor(null), [])
  useEffect(() => {
    if (!passportOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closePassport()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [passportOpen, closePassport])
  // link z ?widok=paszport: otwórz paszport, gdy analiza jest gotowa
  useEffect(() => {
    if (!analysis || !pendingPassport.current) return
    pendingPassport.current = false
    setPassportFor(analysis)
    if (isMobile) setSnap('full')
  }, [analysis, isMobile])
  // adres pamięta otwarty paszport (link „Kopiuj” otworzy go od razu)
  useEffect(() => {
    if (analysis) writeLink({ widok: passportOpen ? 'paszport' : null })
  }, [analysis, passportOpen])
  // historia analiz (ekran „Raporty”, stan w „Moje działki”) – tylko prawdziwe wyniki, nie dane przykładowe
  useEffect(() => {
    if (analysis && !mock) rememberAnalysis(analysis)
  }, [analysis, mock])

  // nowa działka / analiza = bez podświetlenia starego miejsca
  useEffect(() => setHighlight(null), [analysis])

  function showOnMap(g: GeoJSON.Geometry) {
    setHighlight(g)
    if (isMobile) setSnap('collapsed')
    const map = mapRef.current
    if (!map) return
    const b = L.geoJSON(g).getBounds()
    const opts = {
      paddingTopLeft: [insets.left + 32, insets.top + 32] as [number, number],
      paddingBottomRight: [insets.right + 32, insets.bottom + 32] as [number, number],
      maxZoom: 18,
    }
    if (reducedMotion) map.fitBounds(b, { ...opts, animate: false })
    else map.flyToBounds(b, { ...opts, duration: 0.8 })
  }

  // ── „Zobacz przykład”: działka + uprawa + data jednym klikiem ───────────────────────────────
  function openExample(e: Example) {
    userActed.current = true
    setHero(false)
    pendingCrop.current = e.crop
    setPassportFor(null)
    setAsOf(exampleDate(e))
    expandAfterFind.current = true
    searchByNumber(e.parcel)
    if (isMobile) setSnap('half')
  }

  // ── zgłoszenia rowów i zbiorników (SPEC 11) ─────────────────────────────────────────────
  function openInfra() {
    const c = parcel ? parcelBounds(parcel).getCenter() : null
    setPassportFor(null)
    setInfra({ point: c ? [c.lng, c.lat] : null, picking: false })
    if (isMobile) setSnap('full')
  }
  const closeInfra = () => setInfra(null)
  const infraOpen = !!infra && !infra.picking
  const infraMarker = useMemo<GeoJSON.Geometry | null>(
    () => (infra?.point ? { type: 'Point', coordinates: infra.point } : null),
    [infra?.point],
  )

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

  // jeden licznik – nowy komunikat nie znika przez licznik poprzedniego
  const toastTimer = useRef<number | undefined>(undefined)
  function showToast(text: string) {
    setToast(text)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 2500)
  }

  const legend = layerByKey(layer)
  // stan danych warstwy jako tekst pod legendą (nigdy sam kolor)
  const legendStatus =
    layerState.phase === 'idle'
      ? t('Wybierz działkę, aby zobaczyć warstwę')
      : layerState.phase === 'loading'
        ? t('Wczytuję warstwę…')
        : layerState.phase === 'unavailable'
          ? isMobile
            ? t('Brak danych – w budowie')
            : t('Brak danych dla działki – warstwa w budowie')
          : layerState.phase === 'error'
            ? t('Nie udało się pobrać warstwy – mapa działa dalej')
            : layerState.data.layer === 'teren' && layerState.data.value_range
              ? t('Wysokość od {a} do {b} m n.p.m.', {
                  a: formatNum(layerState.data.value_range[0], 1),
                  b: formatNum(layerState.data.value_range[1], 1),
                })
              : layerState.data.source_tag.date
              ? t('Dane z {date}', { date: formatDatePl(layerState.data.source_tag.date) })
              : (layerState.data.source_tag.source ?? '')
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
    onOpenPassport: openPassport,
    onShowOnMap: showOnMap,
    onReportInfra: openInfra,
    onExample: openExample,
  }

  // przeglądanie mapy: dopóki nie wybrano działki – sama mapa (pola uprawne podświetlone) i mały pasek
  const intro = !parcel && !infra

  // „Wróć do mapy”: zamyka działkę, mapa zostaje tam, gdzie była
  function backToExplore() {
    reqId.current++
    setSearch({ phase: 'idle' })
    setCandidates([])
    setPassportFor(null)
    setInfra(null)
    setHighlight(null)
    setInsidePopup(null)
    setPendingPoint(null)
    setView('2d')
    writeLink({ dzialka: null, uprawa: null, data: null, widok: null })
    if (isMobile) setSnap('collapsed')
  }

  const searchBar = (
    <SearchBar
      loading={search.phase === 'loading' || placeBusy}
      error={placeError ?? (search.phase === 'error' && userActed.current ? t(search.error.title, search.error.vars) : null)}
      places={places}
      onPickPlace={pickPlace}
      candidates={candidates}
      total={search.phase === 'candidates' ? search.total : candidates.length}
      onSearch={onSearch}
      onPick={pickCandidate}
      selected={parcel ? `${parcel.obreb} ${parcel.numer}` : null}
      placeholder={isMobile ? t('Numer działki') : undefined}
      onDismiss={() => {
        setPlaces([])
        setPlaceError(null)
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
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-bg print:hidden">
      <div className="flex min-h-0 flex-1">
        {!intro && <Sidebar />}
        <main
          ref={mainRef}
          className="relative min-w-0 flex-1 overflow-hidden"
          style={{ ['--map-bottom' as string]: `${intro ? 0 : isMobile ? sheetVisible + 4 : MAP_BOTTOM_DESKTOP}px` }}
        >
          <ParcelMap
            ref={mapRef}
            baseMap={baseMap}
            parcel={parcel}
            parcelStatus={analysis?.status.level ?? 'no_data'}
            layer={layer}
            layerData={layerState.phase === 'ok' ? layerState.data : null}
            analysisDate={asOf}
            candidates={candidates}
            pendingPoint={pendingPoint}
            userPoint={userPoint}
            insidePopup={insidePopup}
            highlight={infra ? infraMarker : highlight}
            infraRefresh={infraRefresh}
            intro={intro}
            soil={intro}
            insets={insets}
            reducedMotion={reducedMotion}
            onMapClick={onMapClick}
            onMoveEnd={onMoveEnd}
            onSelectCandidate={pickCandidate}
            onClosePopup={() => setInsidePopup(null)}
          />

          {intro ? (
            <>
              {hero ? (
                <IntroHero
                  search={searchBar}
                  locate={<LocateButton locating={locating} onClick={locate} iconOnly />}
                  examples={demoExamples}
                  onExample={openExample}
                />
              ) : (
                <ExploreBar
                  isMobile={isMobile}
                  search={searchBar}
                  locate={<LocateButton locating={locating} onClick={locate} iconOnly />}
                  onExample={openExample}
                  examples={demoExamples}
                />
              )}
              {/* legenda mapy startowej: podatność gleb na suszę (IUNG) */}
              <LegendCard
                title="Podatność gleb na suszę"
                legend={SOIL_SUSCEPTIBILITY_LEGEND}
                status="IUNG-PIB · tereny nierolnicze bez koloru"
                compact={isMobile}
                className={isMobile ? 'absolute right-3 bottom-20 z-[1100] w-52' : 'absolute right-4 bottom-4 z-[1300]'}
              />
              <MapControls
                className={isMobile ? 'absolute top-[76px] right-3 z-[1000]' : 'absolute bottom-4 left-4 z-[1000]'}
                onZoomIn={() => mapRef.current?.zoomIn()}
                onZoomOut={() => mapRef.current?.zoomOut()}
                onBackToParcel={backToParcel}
                onLocate={locate}
                canGoBack={false}
                baseMap={baseMap}
                onBaseMapChange={setBaseMap}
              />
            </>
          ) : (
          <div className="contents ui-appear">
          {view === '3d' && parcel && (
            <Suspense
              fallback={
                <div className="absolute inset-0 z-[500] flex items-center justify-center bg-bg/60 text-sm font-medium text-text-muted">
                  {t('Wczytuję widok 3D…')}
                </div>
              }
            >
              <Terrain3D
                parcel={parcel}
                layerData={layerState.phase === 'ok' ? layerState.data : null}
                reducedMotion={reducedMotion}
                onClose={() => setView('2d')}
              />
            </Suspense>
          )}
          <TopBar
            onBack={backToExplore}
            isMobile={isMobile}
            search={searchBar}
            weather={weather()}
            locating={locating}
            onLocate={locate}
            asOf={asOf}
            onAsOfChange={setAsOf}
            layer={layer}
            onLayerChange={setLayer}
            view={view}
            onViewChange={(v) => {
              setView(v)
              // w 3D najciekawszy jest teren
              if (v === '3d' && (layer === 'kondycja' || layer === 'wilgotnosc')) setLayer('teren')
            }}
          />

          {/* telefon: przy pełnej szufladzie napis zasłaniałby nagłówek działki */}
          {mock && !(isMobile && snap === 'full') && (
            <div className="pointer-events-none absolute top-[116px] right-16 left-3 z-[1450] flex justify-start md:top-[132px] md:right-auto md:left-4">
              <SampleDataBanner />
            </div>
          )}

          {!online && (
            <div className="pointer-events-none absolute inset-x-0 top-[124px] z-[1250] flex justify-center px-3 md:top-[132px]">
              <OfflineBanner />
            </div>
          )}

          {/* ── kontrolki mapy: komputer – lewy dolny róg; telefon – po prawej (SPEC 5.2, 12) ── */}
          {view === '2d' && (
          <MapControls
            className={isMobile ? 'absolute top-[120px] right-3 z-[1000]' : 'absolute left-4 z-[1000]'}
            style={isMobile ? undefined : { bottom: CONTROLS_BOTTOM }}
            onZoomIn={() => mapRef.current?.zoomIn()}
            onZoomOut={() => mapRef.current?.zoomOut()}
            onBackToParcel={backToParcel}
            onLocate={locate}
            canGoBack={!!parcel}
            baseMap={baseMap}
            onBaseMapChange={setBaseMap}
          />
          )}

          {/* ── legenda aktywnej warstwy (SPEC 5.3) ── */}
          {/* telefon: tylko przy zwiniętej szufladzie – wyżej zasłaniałaby działkę na małym kawałku mapy */}
          {(!isMobile || snap === 'collapsed') && (
            <LegendCard
              title={legend.label}
              legend={legend.legend}
              status={legendStatus}
              compact={isMobile}
              collapsed={!isMobile && !ui.legend}
              onToggle={isMobile ? undefined : () => setUi({ legend: !ui.legend })}
              className={
                isMobile
                  ? 'absolute left-3 z-[1000] w-56'
                  : passportOpen
                    ? 'absolute right-[672px] z-[1000]'
                    : 'absolute right-[372px] z-[1000] xl:right-[412px]'
              }
              style={{ bottom: isMobile ? sheetVisible + 32 : FLOAT_BOTTOM }}
            />
          )}

          {/* ── prawy panel działki: 380 px komputer, 340 px tablet (SPEC 4.4, 12) ── */}
          {!isMobile && (
            <aside
              aria-label={passportOpen ? t('Paszport wodny') : t('Panel działki')}
              className={
                passportOpen
                  ? 'absolute top-[128px] right-4 z-[1100] flex flex-col overflow-hidden rounded-xl bg-surface shadow-float'
                  : 'absolute top-[128px] right-4 z-[1100] flex w-[340px] flex-col overflow-hidden rounded-xl bg-surface shadow-float xl:w-[380px]'
              }
              style={{
                bottom: summaryOnly ? undefined : FLOAT_BOTTOM,
                maxHeight: summaryOnly ? `calc(100% - 128px - ${FLOAT_BOTTOM}px)` : undefined,
                width: passportOpen ? `min(${PASSPORT_W}px, calc(100% - 120px))` : undefined,
              }}
            >
              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                {infraOpen ? (
                  <div className="-m-5 h-[calc(100%+40px)]">
                    <InfraReportWizard
                      parcel={parcel}
                      point={infra.point}
                      onPickPoint={() => setInfra({ point: infra.point, picking: true })}
                      onClose={closeInfra}
                      onSaved={() => setInfraRefresh((n) => n + 1)}
                    />
                  </div>
                ) : passportOpen && analysis ? (
                  <Passport analysis={analysis} onClose={closePassport} report={report} onCopyLink={copyLink} onShowOnMap={showOnMap} />
                ) : summaryOnly && parcel ? (
                  <div className="-m-5">
                    <ParcelSummary
                      parcel={parcel}
                      crop={crop}
                      onCropChange={panelProps.onCropChange}
                      run={run}
                      onRetryAnalysis={retryAnalysis}
                      onExpand={() => setUi({ panel: true })}
                      onClose={backToExplore}
                      onOpenPassport={openPassport}
                    />
                  </div>
                ) : (
                  <>
                    {!isMobile && search.phase === 'parcel' && (
                      <button
                        type="button"
                        onClick={() => setUi({ panel: false })}
                        className="-mt-2 mb-2 ml-auto flex h-9 w-fit items-center gap-1 rounded-full px-3 text-sm font-medium text-text-muted hover:bg-surface-2"
                      >
                        <ChevronUp className="size-4" aria-hidden /> {t('Zwiń panel')}
                      </button>
                    )}
                    <ParcelPanel {...panelProps} />
                  </>
                )}
              </div>
            </aside>
          )}

          {/* ── dolny pasek 5 kart (SPEC 4.5) ── */}
          {!isMobile && !cardsShown && (
            <button
              type="button"
              onClick={() => setUi({ cards: true })}
              aria-expanded={false}
              className="absolute bottom-4 left-4 z-[1000] flex items-center gap-2 rounded-full bg-surface px-4 text-sm font-medium shadow-float hover:bg-sage-soft"
              style={{ height: TOGGLE_H }}
            >
              <LayoutPanelTop className="size-4 text-brand" aria-hidden />
              {t('Pogoda, gospodarstwo, oś czasu')}
              <ChevronUp className="size-4 text-text-muted" aria-hidden />
            </button>
          )}
          {cardsShown && (
            <div className="absolute inset-x-4 bottom-4 z-[1000]" style={{ height: CARDS_H }}>
              <button
                type="button"
                onClick={() => setUi({ cards: false })}
                aria-expanded
                className="absolute top-2 right-2 z-10 flex h-8 items-center gap-1 rounded-full bg-surface-2 px-2.5 text-sm font-medium hover:bg-sage-soft"
              >
                <ChevronDown className="size-4 text-text-muted" aria-hidden /> {t('Ukryj')}
              </button>
              <BottomCards
                saved={saved}
                analysis={analysis}
                asOf={asOf}
                onAsOfChange={setAsOf}
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
              {infraOpen ? (
                <div className="-mx-4 -mb-6">
                  <InfraReportWizard
                    parcel={parcel}
                    point={infra.point}
                    onPickPoint={() => {
                      setInfra({ point: infra.point, picking: true })
                      setSnap('collapsed')
                    }}
                    onClose={closeInfra}
                    onSaved={() => setInfraRefresh((n) => n + 1)}
                  />
                </div>
              ) : passportOpen && analysis ? (
                <div className="px-1 pt-5">
                  <Passport analysis={analysis} onClose={closePassport} report={report} onCopyLink={copyLink} onShowOnMap={showOnMap} />
                </div>
              ) : (
              <div className="space-y-5">
                <div className="flex gap-2 [&>label]:min-w-0 [&>label]:flex-1">
                  <DateField value={asOf} onChange={setAsOf} compact />
                  {weather(true)}
                </div>
                <ParcelPanel {...panelProps} hideHeader />
                <BottomCardsStack
                  saved={saved}
                analysis={analysis}
                asOf={asOf}
                onAsOfChange={setAsOf}
                  forecast={forecast}
                  forecastLoading={forecastState === 'loading'}
                  forecastError={forecastState === 'error'}
                  where={where}
                  historical={historical}
                  updated={updated}
                />
              </div>
              )}
            </MobileSheet>
          )}

          {infra?.picking && (
            <div role="status" className="absolute top-[176px] left-1/2 z-[1460] flex -translate-x-1/2 items-center gap-3 rounded-full bg-text py-2 pr-2 pl-4 text-sm text-white shadow-float md:top-[132px]">
              {t('Kliknij na mapie miejsce rowu lub zbiornika')}
              <button
                type="button"
                onClick={() => {
                  setInfra({ point: infra.point, picking: false })
                  if (isMobile) setSnap('full')
                }}
                className="h-9 rounded-full bg-white/15 px-3 font-medium hover:bg-white/25"
              >
                {t('Anuluj')}
              </button>
            </div>
          )}

          {/* wydruk paszportu: osobna kopia poza układem mapy (window.print) */}
          {passportOpen && analysis && createPortal(
            <div className="hidden bg-white p-8 text-text print:block">
              <Passport analysis={analysis} print />
            </div>,
            document.body,
          )}

          </div>
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
      {!intro && <BottomTabs />}
    </div>
  )
}
