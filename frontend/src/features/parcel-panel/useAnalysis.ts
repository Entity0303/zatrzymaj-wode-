import { useEffect, useRef, useState } from 'react'
import { api, describeAnalysisError, type AnalysisQuery } from '@/api/client'
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

    async function loadSatellite(first: AnalysisResponse) {
      try {
        const sat = mock ? await runMockSatellite(ctrl.signal) : await api.satellite(q, ctrl.signal)
        if (sat.status !== 'ok' || mock) return update((a) => ({ ...a, satellite: sat }))
        // zdjęcie jest w cache serwera – ta sama analiza jeszcze raz, już z satelitą (werdykt „Rośliny”, wskaźniki);
        // teren i woda, które już doszły, zostają
        const fresh = await api.analysis(q, ctrl.signal).catch((e) => {
          if (aborted(e)) throw e
          return null
        })
        update((a) =>
          fresh && fresh.satellite?.status === 'ok'
            ? {
                ...fresh,
                terrain: isPending(fresh.terrain) ? a.terrain : fresh.terrain,
                terrain_note: isPending(fresh.terrain) ? a.terrain_note : fresh.terrain_note,
                hydro: fresh.hydro?.status === 'pending' ? a.hydro : fresh.hydro,
              }
            : { ...a, satellite: sat },
        )
      } catch (e) {
        if (!aborted(e)) update((a) => ({ ...a, satellite: satelliteFailed(first.satellite) }))
      }
    }

    // F3: ukształtowanie terenu w tle – 404/501/awaria = „brak danych” z powodem, nigdy błąd całej analizy
    async function loadTerrain() {
      try {
        const terrain = mock ? await runMockBackground('terrain', ctrl.signal) : await api.terrain(q, ctrl.signal)
        update((a) => ({ ...a, terrain }))
        if (mock) return
        // teren jest już w cache serwera – analiza jeszcze raz (werdykt „Teren”, reguły zastawki / oczka korzystają z terenu);
        // satelita i woda, które już doszły, zostają
        const fresh = await api.analysis(q, ctrl.signal).catch((err) => {
          if (aborted(err)) throw err
          return null
        })
        if (fresh && !isPending(fresh.terrain))
          update((a) => ({
            ...fresh,
            satellite: fresh.satellite?.status === 'pending' ? a.satellite : fresh.satellite,
            hydro: fresh.hydro?.status === 'pending' ? a.hydro : fresh.hydro,
          }))
      } catch (e) {
        if (!aborted(e)) update((a) => ({ ...a, terrain: null, terrain_note: 'Nie udało się policzyć ukształtowania terenu. Pozostała analiza jest kompletna.' }))
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
        if (analysis.satellite?.status === 'pending') void loadSatellite(analysis)
        if (isPending(analysis.terrain)) void loadTerrain()
        if (analysis.hydro?.status === 'pending') void loadHydro()
      },
      (e) => publish({ phase: 'error', error: describeAnalysisError(e) }),
    )
    return () => {
      ctrl.abort()
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
