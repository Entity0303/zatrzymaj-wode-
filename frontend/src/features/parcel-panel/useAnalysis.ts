import { useEffect, useRef, useState } from 'react'
import { ApiError, api, describeAnalysisError, type AnalysisQuery } from '@/api/client'
import { TERRAIN_NODATA, queuePosition, serverMessage } from '@/lib/terrainState'
import type { AnalysisResponse, CropId, Satellite, Terrain, TerrainPending } from '@/api/types'
import type { Step } from '@/components/LoadingSteps'
import { mockRequested, runMockAnalysis, runMockBackground, runMockSatellite } from '@/mocks/useMockAnalysis'
import type { AnalysisRun } from './types'

/**
 * Kroki pokazywane podczas czekania na GET /api/analysis. Backend nie przesyła postępu,
 * więc nie udajemy, które kroki są gotowe – wszystkie „w toku” do czasu odpowiedzi (SPEC 15.1).
 */
const REAL_STEPS: Step[] = [
  'Szukam działki',
  'Pobieram pogodę z 10 lat',
  'Sprawdzam glebę',
  'Analizuję teren',
  'Liczę bilans wody (opad minus parowanie)',
].map((label) => ({ label, state: 'active' }))

const IDLE: AnalysisRun = { phase: 'idle' }

/** F13: zmiana uprawy / historii / powierzchni / okresu tej samej działki – liczymy dopiero po tej przerwie. */
const REFINE_DEBOUNCE_MS = 400

/** Overpass (woda w okolicy) bywa wolny – po tylu ms przestajemy czekać i pokazujemy „Ponów”. */
const HYDRO_TIMEOUT_MS = 75_000

/** F33: wspólne odświeżenie analizy po zadaniach w tle – najwyżej tyle ponownych analiz na działkę */
const MAX_REFRESHES = 2
/** F33: gdy nie wszystkie zadania w tle skończyły – odśwież najpóźniej po tylu ms od pierwszego wyniku */
const REFRESH_MAX_WAIT_MS = 15_000
/** F33: same widełki rankingu w tle – tyle czekamy przed odświeżeniem (serwer liczy je kilka sekund) */
const RANGES_WAIT_MS = 4000

/** F23: teren „pending” – co ile i ile razy pytamy ponownie (ok. 1 min) */
const TERRAIN_WAIT_MS = 3000
const TERRAIN_TRIES = 20

const isPending = (t: Terrain | TerrainPending | null | undefined): t is TerrainPending => !!t && 'status' in t && t.status === 'pending'

/** Zdjęcie satelitarne nie przyszło (sieć / serwer) – reszta analizy zostaje, mówimy wprost, czego brak. */
function satelliteFailed(prev: Satellite | null | undefined): Satellite {
  return {
    status: 'brak_danych',
    warning: 'Nie udało się pobrać zdjęcia satelitarnego. Pozostała analiza jest kompletna.',
    series: [],
    layers: [],
    source_tag: prev?.source_tag ?? { kind: 'brak_danych', date: null, source: 'Sentinel-2 L2A' },
  }
}

/**
 * Analiza działki: startuje od razu po wybraniu działki – uprawa jest opcjonalna („Stan działki” + ranking);
 * zmiana uprawy, daty, historii pola lub powierzchni przelicza od nowa (poprzednie zapytanie jest przerywane).
 * `point` – działka bez granic z ULDK (obszar przybliżony). Na mocku (?dane=przykladowe) – symulacja kroków.
 *
 * A11: zdjęcie satelitarne liczy się osobno. Gdy w analizie `satellite.status = "pending"`, wynik jest od razu
 * pokazywany, a w tle idzie GET /api/satellite; po zdjęciu analiza jest pobierana jeszcze raz (z cache serwera –
 * szybko), żeby werdykt („Rośliny”) i wskaźniki z satelity były spójne z kartą „Z satelity”.
 */
export function useAnalysis(
  parcelId: string | null,
  crop: CropId | null,
  date: string,
  opts: {
    point?: [number, number] | null
    geometry?: GeoJSON.Polygon | null
    cropHistory?: string[]
    area?: number | null
    plannedCrops?: string[]
    /** F3: okres (lib/period.ts) */
    period?: string | null
    /** F18: data siewu wpisana przez rolnika → sowing_date */
    sowingDate?: string | null
  } = {},
) {
  const extra = `${opts.point?.join(',') ?? ''}|${opts.geometry ? JSON.stringify(opts.geometry.coordinates) : ''}|${(opts.cropHistory ?? []).join(',')}|${opts.area ?? ''}|${(opts.plannedCrops ?? []).join(',')}|${opts.period ?? ''}|${opts.sowingDate ?? ''}`
  const [attempt, setAttempt] = useState(0)
  // wynik przypisany do konkretnego przebiegu; inny klucz = nowe przeliczenie (stan „ładowanie” liczony w renderze)
  const [result, setResult] = useState<{ key: string; run: AnalysisRun } | null>(null)
  const key = parcelId ? `${parcelId}|${crop ?? ''}|${date}|${extra}|${attempt}` : null
  // „Ponów” w karcie „Woda w okolicy” – ponawia tylko /api/hydro w bieżącym przebiegu
  const retryHydroRef = useRef<(() => void) | null>(null)

  // F13: debounce ok. 400 ms dla zmian tej samej działki (kilka kliknięć w „Doprecyzuj” = jedno przeliczenie);
  // nowa działka / pierwsze wejście – od razu (klucz ustawiany w renderze)
  const [effKey, setEffKey] = useState(key)
  const samePlace = !!effKey && !!key && effKey.split('|')[0] === key.split('|')[0]
  if (key !== effKey && !samePlace) setEffKey(key)
  useEffect(() => {
    if (key === effKey || !samePlace) return
    const id = window.setTimeout(() => setEffKey(key), REFINE_DEBOUNCE_MS)
    return () => window.clearTimeout(id)
  }, [key, effKey, samePlace])

  useEffect(() => {
    if (!parcelId || !key || effKey !== key) return
    const ctrl = new AbortController()
    const publish = (run: AnalysisRun) => {
      if (!ctrl.signal.aborted) setResult({ key, run })
    }
    const mock = import.meta.env.DEV && mockRequested() && !opts.geometry
    const q: AnalysisQuery = {
      parcelId,
      point: opts.point,
      geometry: opts.geometry,
      crop,
      date,
      cropHistory: opts.cropHistory,
      area: opts.area,
      plannedCrops: opts.plannedCrops,
      period: opts.period,
      sowingDate: opts.sowingDate,
    }
    const request = mock
      ? runMockAnalysis((steps) => publish({ phase: 'loading', steps, key }), ctrl.signal, opts.point, opts.period)
      : api.analysis(q, ctrl.signal)
    const aborted = (e: unknown) => (e as Error).name === 'AbortError' || ctrl.signal.aborted

    // bieżący wynik – części liczone w tle (satelita, teren, woda) dopisują się do niego po kolei
    let current: AnalysisResponse | null = null
    // F6: woda w okolicy nie przyszła (502 / ponad 75 s) – karta pokazuje „Ponów” (retryHydro)
    let hydroFailed = false
    const update = (patch: (a: AnalysisResponse) => AnalysisResponse) => {
      if (!current || ctrl.signal.aborted) return
      current = patch(current)
      publish({ phase: 'done', analysis: current, key: key!, hydroFailed })
    }

    // ── F33: JEDNO wspólne odświeżenie analizy zamiast osobnej analizy po satelicie, po terenie i do 3 przy widełkach ──
    // Zadania w tle (satelita, teren) po zakończeniu wołają scheduleRefresh(). Gdy wszystkie oczekiwane zadania są
    // gotowe – odświeżamy od razu; inaczej najpóźniej REFRESH_MAX_WAIT_MS od pierwszego wyniku. Najwyżej
    // MAX_REFRESHES ponownych analiz na działkę; zmiana działki / daty / uprawy (ctrl) anuluje timer.
    let analysisCalls = 1 // pierwsza analiza; licznik do konsoli w trybie dev
    const outstanding = new Set<'satellite' | 'terrain'>() // zadania w tle, na które jeszcze czekamy
    let dirty = false // serwer ma nowe dane (zdjęcie / teren), których bieżąca analiza jeszcze nie uwzględnia
    let rangesPending = false // widełki rankingu liczą się na serwerze (bez osobnego zapytania)
    let refreshes = 0
    let refreshing = false
    let firstResultAt: number | null = null
    let refreshTimer: number | null = null
    const clearRefreshTimer = () => {
      if (refreshTimer !== null) window.clearTimeout(refreshTimer)
      refreshTimer = null
    }

    async function refreshAnalysis() {
      refreshTimer = null
      if (ctrl.signal.aborted || refreshing || refreshes >= MAX_REFRESHES || mock) return
      refreshing = true
      refreshes += 1
      dirty = false
      firstResultAt = null
      analysisCalls += 1
      const fresh = await api.analysis(q, ctrl.signal).catch(() => null)
      refreshing = false
      if (ctrl.signal.aborted) return
      if (import.meta.env.DEV) console.debug(`[useAnalysis] /api/analysis ×${analysisCalls} (odświeżenie ${refreshes}/${MAX_REFRESHES})`)
      if (fresh) {
        rangesPending = !!fresh.suggestions?.ranges_pending
        // scalanie jak dotąd: teren / satelita / woda, które już doszły, zostają, gdy świeża analiza ma je jeszcze „pending”
        update((a) => ({
          ...fresh,
          satellite: fresh.satellite?.status === 'pending' ? a.satellite : fresh.satellite,
          terrain: isPending(fresh.terrain) ? a.terrain : fresh.terrain,
          terrain_note: isPending(fresh.terrain) ? a.terrain_note : fresh.terrain_note,
          hydro: fresh.hydro?.status === 'pending' ? a.hydro : fresh.hydro,
        }))
      }
      scheduleRefresh() // coś doszło w trakcie albo widełki nadal się liczą – ostatnie dozwolone odświeżenie
    }

    function scheduleRefresh() {
      if (ctrl.signal.aborted || mock || refreshing || refreshes >= MAX_REFRESHES) return
      if (!dirty && !rangesPending) return
      if (outstanding.size === 0) {
        // wszystko gotowe: od razu; same widełki – daj serwerowi chwilę na policzenie
        clearRefreshTimer()
        refreshTimer = window.setTimeout(() => void refreshAnalysis(), dirty ? 0 : RANGES_WAIT_MS)
        return
      }
      if (refreshTimer !== null) return // timer „najpóźniej po 15 s od pierwszego wyniku” już biegnie
      firstResultAt ??= Date.now()
      refreshTimer = window.setTimeout(() => void refreshAnalysis(), Math.max(0, REFRESH_MAX_WAIT_MS - (Date.now() - firstResultAt)))
    }
    const taskDone = (task: 'satellite' | 'terrain', gotData: boolean) => {
      outstanding.delete(task)
      if (gotData) dirty = true
      scheduleRefresh()
    }

    async function loadSatellite(first: AnalysisResponse) {
      try {
        const sat = mock ? await runMockSatellite(ctrl.signal) : await api.satellite(q, ctrl.signal)
        update((a) => ({ ...a, satellite: sat }))
        // zdjęcie jest w cache serwera – wspólne odświeżenie dołoży werdykt „Rośliny” i wskaźniki
        taskDone('satellite', sat.status === 'ok' && !mock)
      } catch (e) {
        if (aborted(e)) return
        update((a) => ({ ...a, satellite: satelliteFailed(first.satellite) }))
        taskDone('satellite', false)
      }
    }

    // F3: ukształtowanie terenu w tle – 404/501/awaria = „brak danych” z powodem, nigdy błąd całej analizy
    // F23: odpowiedź „pending” (teren jeszcze się liczy) albo 502/503/brak sieci – ponawiamy co 3 s, najwyżej 20 razy
    // (ok. minuty), w tle; zmiana działki / daty przerywa (ctrl). 404/501 – od razu „brak danych”.
    async function fetchTerrain(): Promise<Terrain> {
      if (mock) return runMockBackground('terrain', ctrl.signal)
      let last: unknown = null
      for (let i = 0; i < TERRAIN_TRIES; i++) {
        if (i > 0) await new Promise<void>((res) => setTimeout(res, TERRAIN_WAIT_MS))
        if (ctrl.signal.aborted) throw new DOMException('przerwano', 'AbortError')
        try {
          const res = (await api.terrain(q, ctrl.signal)) as Terrain | TerrainPending
          if (!isPending(res)) return res
          // pozycja w kolejce (gdy serwer ją poda) – do „w kolejce: N” w karcie terenu i legendzie
          if (queuePosition(res) != null) update((a) => (isPending(a.terrain) ? { ...a, terrain: res } : a))
          last = null
        } catch (e) {
          if (aborted(e)) throw e
          if (e instanceof ApiError && (e.status === 404 || e.status === 501)) throw e
          last = e
        }
      }
      throw last ?? new Error('teren nadal się liczy')
    }

    async function loadTerrain() {
      try {
        const terrain = await fetchTerrain()
        update((a) => ({ ...a, terrain }))
        // teren jest już w cache serwera – wspólne odświeżenie dołoży werdykt „Teren” i reguły zastawki / oczka
        taskDone('terrain', !mock)
      } catch (e) {
        if (aborted(e)) return
        // komunikat błędu z serwera (detail.message), gdy jest – inaczej nasze zdanie
        const detail = e instanceof ApiError ? (e.detail as { message?: unknown } | null) : null
        const msg = serverMessage(typeof detail?.message === 'string' ? detail.message : null) ?? TERRAIN_NODATA
        update((a) => ({ ...a, terrain: null, terrain_note: msg }))
        taskDone('terrain', false)
      }
    }

    // F3/F6: woda w okolicy w tle (Overpass bywa wolny – do ok. 60 s). Awaria albo brak odpowiedzi w 75 s =
    // „Nie udało się sprawdzić wody w okolicy” + „Ponów”; reszta panelu działa dalej.
    async function loadHydro() {
      hydroFailed = false
      update((a) => ({ ...a, hydro: { status: 'pending' } }))
      const hc = new AbortController()
      const stop = () => hc.abort()
      ctrl.signal.addEventListener('abort', stop)
      const timer = window.setTimeout(stop, HYDRO_TIMEOUT_MS)
      try {
        const hydro = mock ? await runMockBackground('hydro', hc.signal) : await api.hydro(q, hc.signal)
        update((a) => ({ ...a, hydro }))
      } catch {
        // przerwane przez nową analizę – nic; awaria albo limit czasu – „Ponów”
        if (ctrl.signal.aborted) return
        hydroFailed = true
        update((a) => ({ ...a, hydro: null }))
      } finally {
        window.clearTimeout(timer)
        ctrl.signal.removeEventListener('abort', stop)
      }
    }
    retryHydroRef.current = () => void loadHydro()

    request.then(
      (analysis) => {
        current = analysis
        publish({ phase: 'done', analysis, key })
        // F33: najpierw lista oczekiwanych zadań, potem ich start – odświeżenie czeka na wszystkie (albo 15 s)
        if (analysis.satellite?.status === 'pending') outstanding.add('satellite')
        if (isPending(analysis.terrain)) outstanding.add('terrain')
        rangesPending = !!analysis.suggestions?.ranges_pending && !mock
        if (import.meta.env.DEV) console.debug('[useAnalysis] /api/analysis ×1 (pierwsza analiza)')
        if (outstanding.has('satellite')) void loadSatellite(analysis)
        if (outstanding.has('terrain')) void loadTerrain()
        if (analysis.hydro?.status === 'pending') void loadHydro() // woda w okolicy: osobny wynik, bez odświeżania analizy
        scheduleRefresh() // same widełki (bez satelity i terenu w tle) – jedno odświeżenie po chwili
      },
      (e) => publish({ phase: 'error', error: describeAnalysisError(e) }),
    )
    return () => {
      ctrl.abort()
      clearRefreshTimer()
      retryHydroRef.current = null
    }
    // opts zawarte w `key`; start dopiero, gdy klucz „odczekał” (effKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effKey])

  const run: AnalysisRun = !key
    ? IDLE
    : result?.key === key
      ? result.run
      : { phase: 'loading', steps: REAL_STEPS, key }
  return { run, retry: () => setAttempt((n) => n + 1), retryHydro: () => retryHydroRef.current?.() }
}
