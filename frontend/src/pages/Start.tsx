import { parcelShortName } from '@/features/parcel-panel/parcelTitle'
import type { Map as LeafletMap } from 'leaflet'
import { Suspense, cloneElement, lazy, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronUp, Loader2 } from 'lucide-react'
import { ErrorNotice } from '@/components/ErrorNotice'
import L from 'leaflet'
import { ApiError, api, describeError } from '@/api/client'
import type { AnalysisResponse, CropId, Parcel, ParcelCandidates, SearchResult } from '@/api/types'
import { OfflineBanner } from '@/components/OfflineBanner'
import { SampleDataBanner } from '@/components/SampleDataBanner'
import { parcelBounds, parcelContains, type MapInsets } from '@/features/map/geo'
import { layerByKey, type LayerKey } from '@/features/map/layers'
import { useLayerData } from '@/features/map/layers/useLayerData'
import { TERRAIN_PENDING, layerInfoLine, layerLegend, layerStatusText, layerStatusVars } from '@/features/map/layers/responseLegend'
import { LegendCard } from '@/features/map/LegendCard'
import { MapControls } from '@/features/map/MapControls'
import { POLAND_CENTER, POLAND_ZOOM, ParcelMap, type BaseMap } from '@/features/map/ParcelMap'
import { MobileSheetHeader } from '@/features/parcel-panel/MobileSheetHeader'
import { ParcelPanel } from '@/features/parcel-panel/ParcelPanel'
import { ParcelSummary } from '@/features/parcel-panel/ParcelSummary'
import { PanelCollapsed } from '@/features/parcel-panel/PanelCollapsed'
import { ExploreBar } from '@/features/intro/ExploreBar'
import { HERO_SEARCH_FORM, IntroHero } from '@/features/intro/IntroHero'
import { useDemoExamples } from '@/features/intro/useDemoExamples'
import type { SoilImageStatus } from '@/features/map/SoilSusceptibilityLayer'
import { SOIL_CLASS_LABELS, SOIL_COLOR } from '@/theme/soil'
import { LocateButton } from '@/features/search/LocateButton'
import { Passport } from '@/features/passport/Passport'
import { RefineCard } from '@/features/parcel-panel/RefineCard'
import { exampleDate, type Example } from '@/features/parcel-panel/examples'
import { InfraView } from '@/features/infra-reports/InfraView'
import { DrawLayer } from '@/features/draw/DrawLayer'
import { DrawToolbar } from '@/features/draw/DrawToolbar'
import { drawProblem, ringAreaHa, toPolygon } from '@/lib/geoArea'
import type { AnalysisRun, SearchPhase } from '@/features/parcel-panel/types'
import { useAnalysis } from '@/features/parcel-panel/useAnalysis'
import { HydroRetryContext } from '@/features/parcel-panel/hydroRetry'
import { SearchBar } from '@/features/search/SearchBar'
import { useForecast } from '@/features/weather/useForecast'
import { WeatherWidget } from '@/features/weather/WeatherWidget'
import { DateField } from '@/components/DateField'
import { PeriodPicker } from '@/features/period/PeriodPicker'
import { periodShortLabel } from '@/lib/period'
import { LayerMenu } from '@/features/map/LayerMenu'
import { FarmDrawer } from '@/layout/FarmDrawer'
import { BottomTabs } from '@/layout/BottomTabs'
import { MobileSheet, snapHeights, type Snap } from '@/layout/MobileSheet'
import { Sidebar } from '@/layout/Sidebar'
import { TopBar } from '@/layout/TopBar'
import { todayIso } from '@/lib/dates'
import { cn } from '@/lib/utils'
import { formatDatePl, formatArea } from '@/lib/format'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { readLink, shareLink, writeLink } from '@/lib/deepLink'
import { rememberAnalysis, useSettings, useUiPrefs } from '@/lib/storage'
import { useReportDownload } from '@/features/reports/useReportDownload'
import { ReportForm } from '@/features/reports/ReportForm'
import { useMediaQuery, useOnline, usePrefersReducedMotion, useSavedParcels } from '@/lib/hooks'
import { mockApproxParcel, mockApproxRequested, mockRequested } from '@/mocks/useMockAnalysis'
import { locale, useLang } from '@/lib/i18n'
import { queuePosition } from '@/lib/terrainState'
import { goTo, usePage } from '@/lib/router'

/** Ekran Start (SPEC 4, 12): mapa + panel działki + dolny pasek kart / szuflada na telefonie. */

const GEO_ERRORS: Record<number, string> = {
  1: 'Brak zgody na lokalizację. Zezwól na nią w ustawieniach przeglądarki.',
  2: 'Nie udało się ustalić położenia. Wyjdź na otwartą przestrzeń albo wpisz numer działki.',
  3: 'Ustalanie położenia trwa zbyt długo. Spróbuj ponownie.',
}

// Telefon: wysokość zwiniętej szuflady (uchwyt + nazwa działki + status + „Raport”)
const SHEET_COLLAPSED = 156

const SHEET_TOP = 116 // pod wyszukiwarką i pigułkami warstw


const round1 = (v: number) => Math.round(v * 10) / 10

// Widok 3D – osobny plik i biblioteka (MapLibre GL), pobierane dopiero po kliknięciu „3D”
const Terrain3D = lazy(() => import('@/features/map3d/Terrain3D'))


/** stała pusta historia pola – ta sama tablica między renderami (zależności efektów) */
const NO_HISTORY: string[] = []

export default function Start() {
  const { t } = useLang()
  // „Zgłoszenia” (#zgloszenia) to widok Startu z otwartym kreatorem zgłoszeń
  const page = usePage()
  const isMobile = useMediaQuery('(max-width: 767px)')
  const isDesktop = useMediaQuery('(min-width: 1280px)')
  const reducedMotion = usePrefersReducedMotion()
  const online = useOnline()
  const { saved, isSaved, toggle: toggleSave } = useSavedParcels()

  const [search, setSearch] = useState<SearchPhase>({ phase: 'idle' })
  const [candidates, setCandidates] = useState<Parcel[]>([])
  const [crops, setCrops] = useState<Record<string, CropId | null>>({})
  // F-MASTER A2: data siewu wpisana przez rolnika (per działka) – backend nie przyjmuje daty siewu, więc ustawia
  // ona okres „od siewu” od tej daty (date_from = data siewu, date_to = data analizy)
  const [sowings, setSowings] = useState<Record<string, string | null>>({})
  // B3 „Doprecyzuj”: historia pola (indeks 0 = rok temu) i powierzchnia uprawy – na działkę
  const [histories, setHistories] = useState<Record<string, string[]>>({})
  const [areas, setAreas] = useState<Record<string, number | null>>({})
  // A5e: „Co planujesz posiać?” – do 3 upraw / grup, na działkę
  const [plans, setPlans] = useState<Record<string, string[]>>({})
  const [reportFormOpen, setReportFormOpen] = useState(false)
  // obszar przybliżony (brak działki w ULDK): punkt kliknięcia – analiza liczona po lon/lat
  const [approxPoints, setApproxPoints] = useState<Record<string, [number, number]>>({})
  // „Narysuj swoje pole” (A5c): punkty w trakcie rysowania (null = nie rysujemy) i obrysy gotowych pól
  const [draw, setDraw] = useState<[number, number][] | null>(null)
  const [drawnGeoms, setDrawnGeoms] = useState<Record<string, GeoJSON.Polygon>>({})
  // link z adresu (?dzialka=&uprawa=&data=) – czytany raz przy wejściu
  const [link] = useState(readLink)
  const [asOf, setAsOf] = useState(link.data ?? todayIso())
  // F3: okres analizy (znacznik z lib/period.ts, w adresie ?okres=)
  const [period, setPeriod] = useState<string | null>(link.okres)
  const [layer, setLayer] = useState<LayerKey>('teren')
  const [view, setView] = useState<'2d' | '3d'>('2d')
  const [settings] = useSettings()
  const [ui, setUi] = useUiPrefs()
  const [baseMap, setBaseMap] = useState<BaseMap>(settings.baseMap)
  // F9/F10: telefon – legenda warstwy „Gleba” zwinięta do paska „Podatność gleb ▾” (nie zasłania obrysu)
  const [soilLegendOpen, setSoilLegendOpen] = useState(false)
  // F10: obraz IUNG w obrysie działki (warstwa „Gleba”) – wczytywanie / gotowy / błąd
  const [soilImg, setSoilImg] = useState<SoilImageStatus>('loading')
  const [pendingPoint, setPendingPoint] = useState<[number, number] | null>(null)
  const [userPoint, setUserPoint] = useState<[number, number] | null>(null)
  const [locating, setLocating] = useState(false)
  const [snap, setSnap] = useState<Snap>(() => (link.dzialka ? 'collapsed' : 'half')) // bez linku: przykłady widoczne od razu
  const [insidePopup, setInsidePopup] = useState<{ lon: number; lat: number; text: string } | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mapCenter, setMapCenter] = useState<[number, number]>([round1(POLAND_CENTER[1]), round1(POLAND_CENTER[0])])
  const [areaH, setAreaH] = useState(600)
  // paszport wodny: przypięty do konkretnego przeliczenia (klucz) – nowa analiza go zamyka,
  // dociągnięte zdjęcie satelitarne (ten sam klucz) – nie
  const [passportFor, setPassportFor] = useState<string | null>(null)
  // F8: zmiana okresu przy otwartym paszporcie – paszport zostaje otwarty dla tej działki (id), a do czasu
  // nowego wyniku pokazuje poprzedni, przyciemniony
  const [passportCarry, setPassportCarry] = useState<string | null>(null)
  /** zamyka paszport (i nie przenosi go na wynik, który się jeszcze liczy) */
  const hidePassport = () => {
    setPassportFor(null)
    setPassportCarry(null)
  }
  const [highlight, setHighlight] = useState<GeoJSON.Geometry | null>(null)
  // zgłoszenie rowu/zbiornika: otwarty kreator, wskazane miejsce, tryb wskazywania na mapie
  const [infra, setInfra] = useState<{ point: [number, number] | null; picking: boolean } | null>(null)
  const [infraRefresh, setInfraRefresh] = useState(0)

  const mapRef = useRef<LeafletMap>(null)
  const mainRef = useRef<HTMLElement>(null)
  const reqId = useRef(0)
  // uprawa z linku – przypisywana do działki, gdy wyszukiwanie ją znajdzie
  const pendingCrop = useRef(link.uprawa)
  const pendingHistory = useRef(link.historia)
  const pendingPlan = useRef(link.plan)
  // karta powitalna (B0): tylko przy wejściu bez działki w linku; znika po pierwszym działaniu
  const [hero, setHero] = useState(() => !link.dzialka)
  // F4: karta chowa się płynnie (ok. 200 ms) – do końca przejścia zostaje w drzewie jako „leaving”
  const [heroMounted, setHeroMounted] = useState(hero)
  if (hero && !heroMounted) setHeroMounted(true)
  useEffect(() => {
    if (hero) return
    const id = window.setTimeout(() => setHeroMounted(false), 200)
    return () => window.clearTimeout(id)
  }, [hero])
  // poziom przybliżenia, przy którym karta się pokazała – przybliżenie o ≥ 1 poziom ją chowa
  const heroZoom = useRef(POLAND_ZOOM)
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
  const history = parcel ? (histories[parcel.id] ?? NO_HISTORY) : NO_HISTORY
  const area = parcel ? (areas[parcel.id] ?? null) : null
  const planned = parcel ? (plans[parcel.id] ?? NO_HISTORY) : NO_HISTORY
  const approxPoint = parcel ? (approxPoints[parcel.id] ?? null) : null
  const drawnGeom = parcel ? (drawnGeoms[parcel.id] ?? null) : null
  // F3: „od siewu” ma sens tylko z uprawą
  const sowing = parcel ? (sowings[parcel.id] ?? null) : null
  const periodUsed =
    period === 'od_siewu' ? (sowing && sowing < asOf ? `${sowing}_${asOf}` : crop ? period : null) : period
  const { run, retry: retryAnalysis, retryHydro } = useAnalysis(parcel?.id ?? null, crop, asOf, {
    point: approxPoint,
    geometry: drawnGeom,
    cropHistory: history,
    area,
    plannedCrops: planned,
    period: periodUsed,
    sowingDate: sowing,
  })
  const analysis = run.phase === 'done' ? run.analysis : null
  const runKey = run.phase === 'done' ? run.key : null
  // F8: ostatni gotowy wynik – paszport pokazuje go (przyciemniony) w trakcie przeliczania dla nowego okresu
  // (F13: razem z id działki z mapy – pole narysowane ma po stronie serwera inny identyfikator)
  const [lastRun, setLastRun] = useState<{ analysis: AnalysisResponse; parcelId: string } | null>(null)
  if (analysis && parcel && (analysis !== lastRun?.analysis || parcel.id !== lastRun.parcelId)) setLastRun({ analysis, parcelId: parcel.id })
  const lastAnalysis = lastRun && parcel && lastRun.parcelId === parcel.id ? lastRun.analysis : null
  // F13: panel w trakcie przeliczania (zmiana uprawy / okresu…) – poprzedni wynik tej działki, przyciemniony, bez
  // odmontowania treści (scroll i fokus zostają); pierwsze liczenie działki – zwykły ekran ładowania
  const panelRun: AnalysisRun = run.phase === 'loading' && lastAnalysis ? { phase: 'done', analysis: lastAnalysis, key: run.key, recalculating: true } : run
  // A11: zdjęcie satelitarne liczone osobno – warstwy Kondycja / Wilgotność odświeżamy, gdy przyjdzie
  const satellite = analysis?.satellite ?? null
  const satStatus = satellite?.status ?? null
  const satLayer = layer === 'kondycja' || layer === 'wilgotnosc'
  // F3: teren i woda w okolicy liczone w tle – warstwy Teren / Spływ / Woda czekają, potem przeładowanie
  const terrainPending = !!analysis?.terrain && 'status' in analysis.terrain
  // F23: analiza jest, a terenu nie udało się policzyć (po ponawianiu)
  const terrainFailed = !!analysis && analysis.terrain == null
  const hydroStatus = analysis?.hydro?.status ?? null
  const terrainLayer = layer === 'teren' || layer === 'splyw'
  const layerWaiting =
    satLayer && satStatus === 'pending'
      ? 'Pobieram zdjęcie satelitarne…'
      : terrainLayer && terrainPending
        ? TERRAIN_PENDING
        : layer === 'woda' && hydroStatus === 'pending'
          ? 'Szukam wody w okolicy…'
          : null
  // „Spróbuj ponownie” w legendzie: nowy numer próby = to samo zapytanie warstwy jeszcze raz
  const [layerAttempt, setLayerAttempt] = useState(0)
  const layerRefresh = `${satLayer ? (satStatus ?? '') : ''}|${terrainLayer ? String(terrainPending) : ''}|${layer === 'woda' ? (hydroStatus ?? '') : ''}|${layerAttempt}`
  // F10: „Gleba” to obraz IUNG z WMS (SoilParcelOverlay), nie /api/layers – bez zapytania do serwera
  const layerState = useLayerData(layer, layer === 'gleba' ? null : (parcel?.id ?? null), asOf, layerRefresh, layerWaiting, drawnGeom)
  const terrainQueue = (layerState.phase === 'waiting' ? layerState.queue : null) ?? queuePosition(analysis?.terrain)
  const retryLayer = layerState.phase === 'error' ? () => setLayerAttempt((n) => n + 1) : undefined
  const carrying = !!parcel && passportCarry === parcel.id && !!lastAnalysis
  const passportOpen = (!!analysis && passportFor === runKey) || carrying
  // treść paszportu: bieżący wynik albo – w trakcie przeliczania / po błędzie nowego okresu – poprzedni
  const passportAnalysis = analysis && passportFor === runKey ? analysis : carrying ? lastAnalysis : analysis
  const passportLoading = carrying && run.phase !== 'done' && run.phase !== 'error'
  const passportError = carrying && run.phase === 'error' ? run.error : null

  // wysokość obszaru mapy – do położeń szuflady
  useLayoutEffect(() => {
    const el = mainRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setAreaH(el.clientHeight))
    ro.observe(el)
    setAreaH(el.clientHeight)
    return () => ro.disconnect()
  }, [])

  // komputer: przy wybranej działce domyślnie mała karta podsumowania, pełny panel na życzenie
  const summaryOnly = !isMobile && !ui.panel && search.phase === 'parcel' && !passportOpen && !infra
  // komputer: panel zwinięty do samej belki (mapa odsłonięta); nowa działka – znów rozwinięty
  const [panelMin, setPanelMin] = useState(false)
  const [minFor, setMinFor] = useState<string | null>(null)
  if ((parcel?.id ?? null) !== minFor) {
    setMinFor(parcel?.id ?? null)
    setPanelMin(false)
  }
  const collapsed = panelMin && !!parcel && !infra
  // „Moje gospodarstwo” pływa nad mapą (nie zajmuje pasa na dole) – panel sięga do dołu z marginesem 16 px
  const FLOAT_BOTTOM = 16
  // komputer: dół panelu działki – nad rzędem kontrolek mapy (44 px) i atrybucją
  const PANEL_BOTTOM = 32 + 44 + 12
  const MAP_BOTTOM_DESKTOP = 0 // atrybucja w prawym dolnym rogu, pod kontrolkami
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

  // ── podpowiedź z /api/search: działka → wczytaj, miejscowość → mapa przybliża → klik w pole ──
  function pickResult(r: SearchResult) {
    userActed.current = true
    setHero(false)
    if (r.kind === 'parcel' && r.parcel_id) {
      const id = r.parcel_id
      return find(() => api.parcelById(id), 'number')
    }
    const map = mapRef.current
    // F3: adres → mapa na punkt (zoom ~17) i od razu działka spod punktu (jak klik w mapę)
    if (r.kind === 'address') {
      map?.setView([r.lat, r.lon], 17, { animate: !reducedMotion })
      return searchByPoint(r.lon, r.lat)
    }
    if (!map) return
    const opts = {
      paddingTopLeft: [insets.left + 24, insets.top + 24] as [number, number],
      paddingBottomRight: [insets.right + 24, insets.bottom + 24] as [number, number],
      maxZoom: r.bbox_approx ? 14 : 16,
    }
    if (r.bbox) {
      const bb = L.latLngBounds([r.bbox[1], r.bbox[0]], [r.bbox[3], r.bbox[2]])
      if (reducedMotion) map.fitBounds(bb, { ...opts, animate: false })
      else map.flyToBounds(bb, { ...opts, duration: 1 })
    } else if (r.lon != null && r.lat != null) map.setView([r.lat, r.lon], 14, { animate: !reducedMotion })
    showToast(t('{name}: kliknij swoje pole na mapie', { name: r.name ?? r.label }))
  }

  /** Enter bez wybranej podpowiedzi: identyfikator / „obręb numer” → działka */
  const onSearch = (q: string) => {
    userActed.current = true
    setHero(false)
    searchByNumber(q)
  }
  const searchByPoint = (lon: number, lat: number) => {
    setPendingPoint([lon, lat])
    find(async () => {
      // mock (?dane=przykladowe&wariant=obszar): klik = obszar przybliżony, jak przy braku działki w ULDK
      if (mockApproxRequested()) {
        const p = mockApproxParcel(lon, lat)
        setApproxPoints((m) => ({ ...m, [p.id]: [lon, lat] }))
        return p
      }
      try {
        return await api.parcelByPoint(lon, lat)
      } catch (e) {
        // brak działki w tym miejscu albo ULDK chwilowo nie działa – analiza kwadratu wokół punktu
        if (!(e instanceof ApiError) || e.status === 0 || e.status === 409 || e.status === 400) throw e
        const a = await api.analysis({ point: [lon, lat], date: asOf }).catch(() => {
          throw e
        })
        if (a.parcel.source !== 'approximate') return a.parcel
        setApproxPoints((m) => ({ ...m, [a.parcel.id]: [lon, lat] }))
        return a.parcel
      }
    }, 'point')
  }
  const retry = () => {
    if (lastRequest.current) find(lastRequest.current.fn, lastRequest.current.kind)
  }

  function applyPendingCrop(p: Parcel) {
    const pl = pendingPlan.current
    if (pl.length) {
      pendingPlan.current = []
      setPlans((m) => ({ ...m, [p.id]: pl }))
    }
    const h = pendingHistory.current
    if (h.length) {
      pendingHistory.current = []
      setHistories((m) => ({ ...m, [p.id]: h }))
    }
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
    if (draw) {
      setDraw((d) => (d ? [...d, [lon, lat]] : d))
      return
    }
    if (infra?.picking) {
      setInfra({ point: [lon, lat], picking: false })
      if (isMobile) setSnap('full')
      return
    }
    if (parcel && parcelContains(parcel, lon, lat)) {
      // SPEC 5.4: klik wewnątrz działki = wartość aktywnej warstwy w punkcie – tylko gdy warstwa ma dane;
      // brak danych = bez dymka (legenda już to mówi)
      setInsidePopup(null)
      if (layerState.phase !== 'ok') return
      api.layerPoint(layer, lon, lat, asOf).then(
        (v) => v.text && setInsidePopup({ lon, lat, text: t(v.text) }),
        () => undefined,
      )
      return
    }
    searchByPoint(lon, lat)
  }

  // ── „Narysuj swoje pole” ───────────────────────────────────────────────────────────────────
  function startDraw() {
    userActed.current = true
    setHero(false)
    setInsidePopup(null)
    hidePassport()
    setInfra(null)
    setView('2d')
    setDraw([])
    if (isMobile) setSnap('collapsed')
  }
  const cancelDraw = () => setDraw(null)
  function finishDraw() {
    if (!draw || draw.length < 3 || drawProblem(draw)) return
    const geometry = toPolygon(draw)
    // tymczasowa „działka” z obrysu – nazwę, gminę i dokładną powierzchnię poda analizy (POST /api/analysis)
    const c = draw.reduce((a, p) => [a[0] + p[0] / draw.length, a[1] + p[1] / draw.length], [0, 0])
    const id = `narysowane_${c[0].toFixed(5)}_${c[1].toFixed(5)}_${draw.length}`
    const p: Parcel = {
      id,
      wojewodztwo: '',
      powiat: '',
      gmina: '',
      obreb: '',
      numer: '—',
      teryt_gminy: '',
      powierzchnia_ha: Math.round(ringAreaHa(draw) * 10000) / 10000,
      geometria: geometry,
      zrodlo: { nazwa: 'Obrys narysowany przez rolnika', url: '', pobrano: new Date().toISOString(), uwagi: null },
      source: 'drawn',
      name: 'Pole narysowane przez rolnika',
    }
    reqId.current++
    setDrawnGeoms((m) => ({ ...m, [id]: geometry }))
    setCandidates([])
    setDraw(null)
    setSearch({ phase: 'parcel', parcel: p })
    if (isMobile) setSnap('half')
  }
  useEffect(() => {
    if (!draw) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDraw(null)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [draw])

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
    // obszar przybliżony nie ma identyfikatora działki – link bez niego
    if (parcel && !approxPoint && !drawnGeom) writeLink({ dzialka: parcel.id, uprawa: crop, data: asOf, historia: history, plan: planned, okres: period })
  }, [parcel, crop, asOf, history, planned, approxPoint, drawnGeom, period])

  function copyLink() {
    if (!parcel) return
    const href = shareLink({ dzialka: parcel.id, uprawa: crop, data: asOf, historia: history, plan: planned, okres: period, widok: passportOpen ? 'paszport' : null })
    if (!navigator.clipboard) return showToast(t('Skopiuj adres z paska przeglądarki – to link do tej analizy'))
    navigator.clipboard.writeText(href).then(
      () => showToast(t('Skopiowano link do tej analizy')),
      () => showToast(t('Skopiuj adres z paska przeglądarki – to link do tej analizy')),
    )
  }

  // ── paszport wodny i „Pokaż na mapie” ──────────────────────────────────────────────────────
  /** F8: okres zmieniony w paszporcie – paszport zostaje otwarty, analiza liczy się od nowa */
  /** F6: zmiana w formularzu „Podaj, co rosło” w paszporcie – paszport zostaje otwarty na nowym wyniku */
  const inPassport =
    <A,>(f: (a: A) => void) =>
    (a: A) => {
      if (parcel) setPassportCarry(parcel.id)
      f(a)
    }
  function changePeriodInPassport(v: string | null) {
    if (parcel) setPassportCarry(parcel.id)
    setPeriod(v)
  }
  useEffect(() => {
    if (!passportCarry || !runKey) return
    setPassportFor(runKey)
    setPassportCarry(null)
    // tylko nowy wynik (albo ten sam okres wybrany ponownie)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runKey, passportCarry, period])

  function openPassport() {
    if (!runKey) return
    setPassportFor(runKey)
  }
  const closePassport = useCallback(() => {
    setPassportFor(null)
    setPassportCarry(null)
  }, [])
  useEffect(() => {
    if (!passportOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closePassport()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [passportOpen, closePassport])
  // link z ?widok=paszport: otwórz paszport, gdy analiza jest gotowa
  useEffect(() => {
    if (!runKey || !pendingPassport.current) return
    pendingPassport.current = false
    setPassportFor(runKey)
  }, [runKey, isMobile])
  // adres pamięta otwarty paszport (link „Kopiuj” otworzy go od razu)
  useEffect(() => {
    if (analysis) writeLink({ widok: passportOpen ? 'paszport' : null })
  }, [analysis, passportOpen])
  // historia analiz (ekran „Raporty”, stan w „Moje działki”) – tylko prawdziwe wyniki, nie dane przykładowe
  useEffect(() => {
    if (analysis && !mock) rememberAnalysis(analysis)
  }, [analysis, mock])

  // nowa działka / analiza = bez podświetlenia starego miejsca
  useEffect(() => setHighlight(null), [runKey])

  function showOnMap(g: GeoJSON.Geometry) {
    hidePassport()
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
    hidePassport()
    setAsOf(exampleDate(e))
    expandAfterFind.current = true
    searchByNumber(e.parcel)
    if (isMobile) setSnap('half')
  }

  // ── zgłoszenia rowów i zbiorników (SPEC 11) ─────────────────────────────────────────────
  function openInfra() {
    const c = parcel ? parcelBounds(parcel).getCenter() : null
    hidePassport()
    // bez działki – środek mapy (miejsce i tak wskazuje się na mapie)
    setInfra({ point: c ? [c.lng, c.lat] : mapCenter, picking: false })
    if (isMobile) setSnap('full')
  }
  // F22: „Pokaż na mapie” z listy „Moje zgłoszenia” – środek mapy i znacznik w tym miejscu (pinezki pobierane wokół)
  const showInfraPoint = (p: [number, number]) => {
    setInfra({ point: p, picking: false })
    mapRef.current?.setView([p[1], p[0]], 16, { animate: !reducedMotion })
  }
  const closeInfra = () => {
    setInfra(null)
    if (page === 'infra') goTo('start')
  }
  // „Zgłoszenia” z lewego menu / dolnych zakładek (#zgloszenia) – otwiera kreator; okolica wybranej działki albo środek mapy
  useEffect(() => {
    if (page === 'infra' && !infra) openInfra()
    // tylko wejście na stronę
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])
  // kreator zamknięty inną drogą (wybór działki, „Wróć do mapy”) – adres wraca na Start, żeby „Zgłoszenia” znów działały
  const hadInfra = useRef(false)
  useEffect(() => {
    if (infra) hadInfra.current = true
    else if (hadInfra.current) {
      hadInfra.current = false
      if (page === 'infra') goTo('start')
    }
    // tylko zmiana otwarcia kreatora
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!infra])
  const infraCenter = useMemo<[number, number] | null>(() => {
    if (!infra) return null
    if (infra.point) return infra.point
    if (parcel) {
      const c = parcelBounds(parcel).getCenter()
      return [c.lng, c.lat]
    }
    return mapCenter
  }, [infra, parcel, mapCenter])
  const infraOpen = !!infra && !infra.picking
  const infraMarker = useMemo<GeoJSON.Geometry | null>(
    () => (infra?.point ? { type: 'Point', coordinates: infra.point } : null),
    [infra?.point],
  )

  // ── raport PDF: te same parametry co analiza ─────────────────────────────────────────────
  const report = useReportDownload(
    parcel && analysis
      ? { parcelId: parcel.id, point: approxPoint, geometry: drawnGeom, numer: drawnGeom ? 'pole-narysowane' : approxPoint ? 'obszar' : parcel.numer, obreb: parcel.obreb, gmina: parcel.gmina, crop: analysis.crop, date: asOf, cropHistory: history, area, plannedCrops: planned, period: periodUsed, sowingDate: sowing }
      : null,
  )
  // „Pobierz raport” otwiera formularz „Przygotuj raport” (skrócony / szczegółowy)
  // F-MASTER A3: w panelu raport pobierany od razu (skrócony / pełny), w innych miejscach – formularz „Przygotuj raport”
  const reportUi = { ...report, download: () => setReportFormOpen(true), downloadType: (type: 'short' | 'full') => void report.download(type) }
  const reportIncluded = [
    planned.length ? t('plan: {n}', { n: planned.length }) : null,
    history.some((h) => h && h !== 'nie_wiem') ? t('historia pola') : null,
    area ? formatArea(area) : null,
    periodUsed ? t('okres: {p}', { p: t(periodShortLabel(periodUsed)) }) : null,
  ].filter(Boolean) as string[]
  const clearReportError = report.clearError
  useEffect(() => clearReportError(), [parcel?.id, crop, asOf, history, area, planned, periodUsed, clearReportError])
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

  // poziom przybliżenia (po zakończeniu ruchu) – karta powitalna chowa się / wraca
  const [zoom, setZoom] = useState(POLAND_ZOOM)
  const onMoveEnd = useCallback((lon: number, lat: number, z: number) => {
    setZoom(z)
    setMapCenter((prev) => {
      const next: [number, number] = [round1(lon), round1(lat)]
      return prev[0] === next[0] && prev[1] === next[1] ? prev : next
    })
  }, [])

  // F4: karta powitalna – chowa się przy przybliżaniu (≥ 1 poziom) i przeciąganiu, wraca po oddaleniu do całej Polski
  useEffect(() => {
    if (parcel || infra || draw) return
    if (hero && zoom >= heroZoom.current + 1) setHero(false)
    else if (!hero && zoom <= POLAND_ZOOM && search.phase !== 'loading') {
      heroZoom.current = zoom
      setHero(true)
    }
    // tylko zmiana przybliżenia – pozostałe warunki czytamy w chwili zmiany
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoom])
  const onDragStart = useCallback(() => setHero(false), [])
  /** logo / „Start”: zamyka działkę, mapa na całą Polskę, wraca karta powitalna */
  function goHome() {
    backToExplore()
    setDraw(null)
    heroZoom.current = POLAND_ZOOM
    setHero(true)
    const map = mapRef.current
    // już widać całą Polskę – mapa zostaje (bez skakania)
    if (!map || (map.getZoom() <= POLAND_ZOOM && map.getCenter().distanceTo(POLAND_CENTER) < 150_000)) return
    const w = map.getSize().x
    // jak przy pierwszym wejściu: na komputerze Polska przesunięta w prawo (karta po lewej)
    if (w >= 1024) map.once('moveend', () => map.panBy([-Math.round(w * 0.2), 0], { animate: !reducedMotion }))
    if (reducedMotion) map.setView(POLAND_CENTER, POLAND_ZOOM, { animate: false })
    else map.flyTo(POLAND_CENTER, POLAND_ZOOM, { duration: 0.8 })
  }

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

  const legendBase = layerByKey(layer)
  // legenda z odpowiedzi serwera (A11: kolory skali satelity), stan danych jako tekst pod nią (nigdy sam kolor)
  // F10: gleba – udziały kategorii IUNG na działce (analysis.soil.shares) jako % w legendzie, bez nich sama legenda
  const soilShares = analysis?.soil.shares ?? []
  const soilPct = (code: number) => Math.round((soilShares.find((x) => x.code === code)?.share ?? 0) * 100)
  const soilLegend = {
    kind: 'classes' as const,
    items: [1, 2, 3, 4, 5].map((code) => ({
      color: SOIL_COLOR[code],
      label: soilPct(code) > 0 ? `${t(SOIL_CLASS_LABELS[code])}: ${soilPct(code)}%` : SOIL_CLASS_LABELS[code],
    })),
  }
  const soilAgri = soilShares.some((x) => x.code >= 1 && x.code <= 5 && x.share > 0)
  const soilLegendStatus =
    soilImg === 'error' || (soilImg === 'ok' && analysis && !soilAgri)
      ? 'Brak danych IUNG dla tej działki'
      : soilImg === 'loading'
        ? 'Wczytuję warstwę…'
        : 'IUNG-PIB · tylko w obrysie działki'
  const legend = layer === 'gleba' ? { label: legendBase.label, legend: soilLegend } : { label: legendBase.label, legend: layerLegend(legendBase, layerState) }
  const legendStatus =
    layer === 'gleba'
      ? t(soilLegendStatus)
      : t(layerStatusText(layer, layerState, satellite), layerState.phase === 'ok' ? layerStatusVars(layerState.data) : undefined) +
        // dopisek po A23: pozycja w kolejce zadań w tle, gdy serwer ją poda
        (terrainLayer && layerState.phase === 'waiting' && terrainQueue != null ? ` · ${t('w kolejce: {n}', { n: terrainQueue })}` : '')
  // F27: szara linia na dole legendy – skąd i z kiedy są dane warstwy
  const legendInfo = layer === 'gleba' ? t('źródło: {src}', { src: 'IUNG-PIB' }) : layerInfoLine(layer, layerState, t, terrainQueue, layerStatusText(layer, layerState, satellite).includes('{date}'))
  const refine = {
    crop,
    onCropChange: (c: CropId | null) => {
      if (parcel) setCrops((m) => ({ ...m, [parcel.id]: c }))
    },
    history,
    onHistoryChange: (h: string[]) => {
      if (parcel) setHistories((m) => ({ ...m, [parcel.id]: h }))
    },
    onAreaChange: (ha: number | null) => {
      if (parcel) setAreas((m) => ({ ...m, [parcel.id]: ha }))
    },
    planned,
    onPlannedChange: (pl: string[]) => {
      if (parcel) setPlans((m) => ({ ...m, [parcel.id]: pl.slice(0, 3) }))
    },
    period: periodUsed,
    // F-MASTER A2: okres i data siewu w formularzu „Twoja działka”
    periodValue: period,
    onPeriodChange: setPeriod,
    sowing,
    onSowingChange: (d: string | null) => {
      if (!parcel) return
      setSowings((m) => ({ ...m, [parcel.id]: d }))
      if (d) setPeriod('od_siewu')
    },
    asOf,
    historical,
  }
  const panelProps = {
    state: search,
    refine,
    asOf,
    forecastState,
    run: panelRun,
    onRetryAnalysis: retryAnalysis,
    saved: parcel ? isSaved(parcel.id) : false,
    onToggleSave: () => {
      if (parcel) toggleSave(parcel)
    },
    onCopied: () => showToast(t('Skopiowano identyfikator działki')),
    onRetry: retry,
    onFocusSearch: focusSearch,
    onLocate: locate,
    report: reportUi,
    onOpenPassport: openPassport,
    onShowOnMap: showOnMap,
    onExample: openExample,
    examples: demoExamples,
    onClose: backToExplore,
  }

  // warstwy bez danych z serwera – wyszarzone w menu („brak danych”)
  const layerMenu = (side: 'top' | 'bottom') => (
    <LayerMenu
      value={layer}
      onChange={setLayer}
      view={view}
      onViewChange={(v) => {
        setView(v)
        // w 3D najciekawszy jest teren
        if (v === '3d' && (layer === 'kondycja' || layer === 'wilgotnosc')) setLayer('teren')
      }}
      // woda w okolicy: backend bez sekcji `hydro` (stara wersja / awaria) – „brak danych”
      unavailable={analysis && analysis.hydro == null ? ['woda'] : []}
      // F10: gleba tylko w obrysie działki – bez działki nieaktywna
      needsParcel={parcel ? [] : ['gleba']}
      notes={{
        ...(satStatus === 'pending'
          ? { kondycja: 'pobieram…', wilgotnosc: 'pobieram…' }
          : satStatus === 'brak_danych'
            ? { kondycja: 'brak zdjęcia', wilgotnosc: 'brak zdjęcia' }
            : {}),
        // F23: „liczę…” do czasu danych (teren w tle albo warstwa liczona na żywo), „brak danych” po nieudanej próbie
        ...(terrainPending || (terrainLayer && layerState.phase === 'waiting')
          ? { teren: 'liczę…', splyw: 'liczę…' }
          : terrainFailed || (terrainLayer && (layerState.phase === 'error' || layerState.phase === 'unavailable'))
            ? { teren: 'brak danych', splyw: 'brak danych' }
            : {}),
        ...(hydroStatus === 'pending' ? { woda: 'szukam…' } : hydroStatus === 'none' ? { woda: 'brak w pobliżu' } : {}),
      }}
      canUse3d={!!parcel}
      side={side}
      onDraw={startDraw}
    />
  )

  // przeglądanie mapy: dopóki nie wybrano działki – sama mapa (pola uprawne podświetlone) i mały pasek
  const intro = !parcel && !infra

  // „Wróć do mapy”: zamyka działkę, mapa zostaje tam, gdzie była
  function backToExplore() {
    reqId.current++
    setSearch({ phase: 'idle' })
    setCandidates([])
    hidePassport()
    setInfra(null)
    setHighlight(null)
    setInsidePopup(null)
    setPendingPoint(null)
    setView('2d')
    writeLink({ dzialka: null, uprawa: null, data: null, historia: [], plan: [], okres: null, widok: null })
    if (isMobile) setSnap('collapsed')
  }

  const searchBar = (
    <SearchBar
      loading={search.phase === 'loading'}
      // F12: tytuł + podpowiedź (np. „Nie znaleziono działki. Sprawdź numer – pełny identyfikator wygląda tak: …”)
      error={search.phase === 'error' && userActed.current ? `${t(search.error.title, search.error.vars)}. ${t(search.error.message, search.error.vars)}` : null}
      onPickResult={pickResult}
      candidates={candidates}
      total={search.phase === 'candidates' ? search.total : candidates.length}
      onSearch={onSearch}
      onPick={pickCandidate}
      selected={parcel ? (parcel.source === 'approximate' || parcel.source === 'drawn' ? parcelShortName(parcel) : `${parcel.obreb} ${parcel.numer}`) : null}
      placeholder={isMobile ? t('Numer działki lub adres') : undefined}
      onDismiss={() => {
        if (candidates.length) {
          setCandidates([])
          setSearch({ phase: 'idle' })
        }
      }}
      className={isMobile ? 'min-w-0 flex-1' : 'max-w-[560px] min-w-[300px] flex-1'}
    />
  )

  // F26: zdanie o ryzyku na 7 dni pod prognozą (z analizy wybranej działki)
  const risk7 = analysis?.indicators.risk_7d ?? null
  const riskSentence = !risk7
    ? null
    : risk7.days_to_stress != null
      ? t('Według prognozy wody wystarczy na ok. {n} dni', { n: risk7.days_to_stress })
      : risk7.label
        ? `${t('Ryzyko braku wody w 7 dni:')} ${t(risk7.label)}${risk7.note ? ` – ${t(risk7.note)}` : ''}`
        : null
  const weather = (compact?: boolean) => (
    <WeatherWidget
      forecast={forecast}
      loading={forecastState === 'loading'}
      error={forecastState === 'error'}
      where={where}
      compact={compact}
      bare={!compact}
      historical={historical}
      risk={riskSentence}
    />
  )

  // F6: „Ponów” w karcie „Woda w okolicy”, gdy /api/hydro nie odpowiedział
  const hydroRetry = { failed: run.phase === 'done' && !!run.hydroFailed, retry: retryHydro }

  return (
    <HydroRetryContext.Provider value={hydroRetry}>
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-bg print:hidden">
      <div className="flex min-h-0 flex-1">
        {!intro && <Sidebar onHome={goHome} />}
        <main
          ref={mainRef}
          className={`relative min-w-0 flex-1 overflow-hidden ${draw ? 'drawing' : ''}`}
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
            infraCenter={infraCenter}
            intro={intro}
            onSoilStatus={setSoilImg}
            insets={insets}
            reducedMotion={reducedMotion}
            onMapClick={onMapClick}
            onMoveEnd={onMoveEnd}
            onDragStart={onDragStart}
            onSelectCandidate={pickCandidate}
            onClosePopup={() => setInsidePopup(null)}
          >
            {draw && <DrawLayer points={draw} onClose={finishDraw} />}
          </ParcelMap>

          {draw && (
            <DrawToolbar
              points={draw}
              onUndo={() => setDraw((d) => (d ? d.slice(0, -1) : d))}
              onCancel={cancelDraw}
              onDone={finishDraw}
              className={`absolute z-[1460] ${intro || isMobile ? 'left-1/2 -translate-x-1/2' : 'left-4'} ${intro ? 'top-[76px]' : isMobile ? 'top-[120px]' : 'top-[128px]'}`}
            />
          )}

          {intro ? (
            <>
              {heroMounted ? (
                <IntroHero
                  leaving={!hero}
                  // F14: jedna siatka – pole z lupą i „Moja lokalizacja” w środku, data, „Sprawdź” (ten sam formularz)
                  search={cloneElement(searchBar, {
                    variant: 'field',
                    formId: HERO_SEARCH_FORM,
                    // telefon: krótszy tekst – pole ma całą szerokość karty, ale obok są przyciski w polu
                    placeholder: t(isMobile ? 'Numer działki lub adres' : 'Wpisz numer działki lub adres'),
                    trailing: <LocateButton locating={locating} onClick={locate} inField />,
                  })}
                  // F12: data analizy na karcie powitalnej – ten sam stan co w górnym pasku (paska nie ma przy karcie)
                  date={<DateField value={asOf} onChange={setAsOf} field />}
                  examples={demoExamples}
                  onExample={openExample}
                  onDraw={startDraw}
                  isMobile={isMobile}
                />
              ) : (
                <ExploreBar
                  isMobile={isMobile}
                  search={searchBar}
                  locate={<LocateButton locating={locating} onClick={locate} iconOnly />}
                  onExample={openExample}
                  onDraw={startDraw}
                  examples={demoExamples}
                  onHome={goHome}
                />
              )}
              {/* przed wybraniem działki nie ma panelu – stan wyszukiwania i błąd z „co teraz” nad mapą */}
              {search.phase === 'loading' && !draw && (
                <div role="status" className="pointer-events-none absolute inset-x-3 bottom-20 z-[1300] flex justify-center">
                  <p className="flex items-center gap-2 rounded-full bg-surface px-4 py-2.5 text-sm font-medium shadow-float">
                    <Loader2 className="size-4 animate-spin text-brand" aria-hidden />
                    {t(search.kind === 'point' ? 'Szukam działki w tym miejscu…' : 'Szukam działki…')}
                  </p>
                </div>
              )}
              {search.phase === 'error' && userActed.current && !hero && !draw && (
                <div className="absolute inset-x-3 bottom-20 z-[1300] mx-auto max-w-md">
                  <ErrorNotice {...search.error} onRetry={search.error.retryable ? retry : undefined} className="shadow-float" />
                </div>
              )}
              {/* prawy dolny róg, nad kartą powitalną (z-index wyżej) – przyciski mapy zawsze widoczne; nad nimi legenda gleb,
                  tylko gdy nakładka IUNG jest włączona (poniżej progu przybliżenia – „Przybliż mapę…”) */}
              <div
                className={cn(
                  'pointer-events-none absolute z-[1250] flex flex-col items-end gap-2 [&>*]:pointer-events-auto',
                  isMobile ? 'right-3 bottom-20' : 'right-4 bottom-4',
                )}
              >
                <MapControls
                  horizontal
                  onZoomIn={() => mapRef.current?.zoomIn()}
                  onZoomOut={() => mapRef.current?.zoomOut()}
                  onBackToParcel={backToParcel}
                  onLocate={locate}
                  canGoBack={false}
                  baseMap={baseMap}
                  onBaseMapChange={setBaseMap}
                />
              </div>
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
            isMobile={isMobile}
            search={cloneElement(searchBar, { trailing: <LocateButton locating={locating} onClick={locate} inField /> })}
            weather={weather()}
            asOf={asOf}
            onAsOfChange={setAsOf}
            layerButton={isMobile ? layerMenu('bottom') : undefined}
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
            className={isMobile ? 'absolute top-[120px] right-3 z-[1000]' : 'absolute right-4 bottom-8 z-[1000]'}
            horizontal={!isMobile}
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
          {isMobile && snap === 'collapsed' && (
            <LegendCard
              title={legend.label}
              legend={legend.legend}
              status={legendStatus}
              info={legendInfo}
              onRetry={retryLayer}
              compact
              // F9/F10: gleba na telefonie – zwinięta pigułka „Podatność gleb ▾”, rozwijana kliknięciem
              {...(layer === 'gleba' ? { collapsed: !soilLegendOpen, collapsedLabel: 'Podatność gleb', onToggle: () => setSoilLegendOpen((o) => !o) } : {})}
              className={cn('absolute left-3 z-[1000]', !(layer === 'gleba' && !soilLegendOpen) && 'w-56')}
              style={{ bottom: sheetVisible + 32 }}
            />
          )}
          {!isMobile && (
            <div className="absolute bottom-4 left-4 z-[1300] flex flex-col items-start gap-2">
              {!ui.cards && (
                <LegendCard
                  title={legend.label}
                  legend={legend.legend}
                  status={legendStatus}
              info={legendInfo}
                  onRetry={retryLayer}
                  collapsed={!ui.legend}
                  onToggle={() => setUi({ legend: !ui.legend })}
                />
              )}
              <div className="relative flex items-center gap-2">
                {layerMenu('top')}
                <FarmDrawer
                  open={ui.cards}
                  onToggle={() => setUi({ cards: !ui.cards })}
                  panelStyle={{ width: `min(960px, calc(100vw - ${(isDesktop ? 412 : 372) + 140}px))` }}
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
            </div>
          )}

          {/* ── prawy panel działki: 380 px komputer, 340 px tablet (SPEC 4.4, 12) ── */}
          {!isMobile && (
            <aside
              aria-label={t('Panel działki')}
              className="absolute top-[128px] right-4 z-[1100] flex w-[340px] flex-col overflow-hidden rounded-xl bg-surface shadow-float xl:w-[380px]"
              style={{
                bottom: summaryOnly || collapsed ? undefined : PANEL_BOTTOM,
                maxHeight: summaryOnly ? `calc(100% - 128px - ${PANEL_BOTTOM}px)` : undefined,
              }}
            >
              {collapsed && parcel ? (
                <PanelCollapsed
                  parcel={parcel}
                  status={analysis && !analysis.soil.non_agricultural ? analysis.status.level : null}
                  historical={historical}
                  onExpand={() => setPanelMin(false)}
                  onClose={backToExplore}
                />
              ) : (
              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                {infraOpen ? (
                  <div className="-m-5 h-[calc(100%+40px)]">
                    <InfraView
                      parcel={parcel}
                      point={infra.point}
                      onPickPoint={() => setInfra({ point: infra.point, picking: true })}
                      onClose={closeInfra}
                      onSaved={() => setInfraRefresh((n) => n + 1)}
                      onShow={showInfraPoint}
                      hydro={analysis?.hydro}
                    />
                  </div>
                ) : summaryOnly && parcel ? (
                  <div className="-m-5">
                    <ParcelSummary
                      parcel={parcel}
                      refine={refine}
                      run={panelRun}
                      onRetryAnalysis={retryAnalysis}
                      onExpand={() => setUi({ panel: true })}
                      onClose={backToExplore}
                      onCollapse={() => setPanelMin(true)}
                      onOpenPassport={openPassport}
                      onShowOnMap={showOnMap}
                      report={reportUi}
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
              )}
            </aside>
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
                  onClose={backToExplore}
                  status={analysis?.status.level ?? 'no_data'}
                  historical={historical}
                  onReport={analysis ? reportUi.download : undefined}
                  reportBusy={report.busy}
                />
              }
            >
              {infraOpen ? (
                <div className="-mx-4 -mb-6">
                  <InfraView
                    parcel={parcel}
                    point={infra.point}
                    onPickPoint={() => {
                      setInfra({ point: infra.point, picking: true })
                      setSnap('collapsed')
                    }}
                    onClose={closeInfra}
                    onSaved={() => setInfraRefresh((n) => n + 1)}
                    onShow={(p) => {
                      showInfraPoint(p)
                      setSnap('collapsed')
                    }}
                    hydro={analysis?.hydro}
                  />
                </div>
              ) : (
              <div className="space-y-5">
                <div className="flex gap-2 [&>label]:min-w-0 [&>label]:flex-1">
                  <DateField value={asOf} onChange={setAsOf} compact />
                  {weather(true)}
                </div>
                {parcel && <PeriodPicker value={period} onChange={setPeriod} hasCrop={!!crop} asOf={asOf} align="left" />}
                <ParcelPanel {...panelProps} hideHeader />
                <FarmDrawer
                  inline
                  open={ui.cards}
                  onToggle={() => setUi({ cards: !ui.cards })}
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

          {/* paszport wodny – pełny ekran nad mapą i panelem (nic nie prześwituje) */}
          {passportOpen && passportAnalysis && (
            <Passport
              refineForm={
                passportAnalysis && (
                  <RefineCard
                    crop={refine.crop}
                    onCropChange={inPassport(refine.onCropChange)}
                    history={refine.history}
                    onHistoryChange={inPassport(refine.onHistoryChange)}
                    area={passportAnalysis.suggestions?.area ?? null}
                    onAreaChange={inPassport(refine.onAreaChange)}
                    rotationHint={passportAnalysis.suggestions?.rotation_hint}
                    period={period}
                    onPeriodChange={changePeriodInPassport}
                    sowing={sowing}
                    onSowingChange={inPassport(refine.onSowingChange)}
                    typicalSowing={refine.crop ? (passportAnalysis.crop_season?.season_start ?? null) : null}
                    sowingNote={passportAnalysis.crop_season?.sowing_note ?? null}
                    asOf={asOf}
                    historical={historical}
                  />
                )
              }
              analysis={passportAnalysis}
              onClose={closePassport}
              report={passportLoading ? undefined : reportUi}
              onCopyLink={copyLink}
              onShowOnMap={showOnMap}
              period={{
                picker: (
                  <span title={t('Za jaki czas podsumować opady i parowanie – nie zmienia oceny działki ani rankingu upraw.')}>
                  <PeriodPicker
                    value={period}
                    onChange={changePeriodInPassport}
                    hasCrop={!!crop}
                    asOf={asOf}
                    prefix="Okres:"
                    emptyLabel={t('od {d} (sezon uprawy)', { d: formatDatePl(passportAnalysis.history.season_start) })}
                    disabled={passportLoading}
                  />
                  </span>
                ),
                loading: passportLoading,
                error: passportError,
                onRetry: retryAnalysis,
              }}
            />
          )}

          {/* wydruk paszportu: osobna kopia poza układem mapy (window.print) */}
          {passportOpen && passportAnalysis && createPortal(
            <div className="hidden bg-white p-8 text-text print:block">
              <Passport analysis={passportAnalysis} print />
            </div>,
            document.body,
          )}

          </div>
          )}

          <ReportForm
            open={reportFormOpen && !!analysis}
            onClose={() => setReportFormOpen(false)}
            busy={report.busy}
            included={reportIncluded}
            onGenerate={(type) => {
              setReportFormOpen(false)
              void report.download(type)
            }}
          />

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
      {!intro && <BottomTabs onHome={goHome} />}
    </div>
    </HydroRetryContext.Provider>
  )
}
