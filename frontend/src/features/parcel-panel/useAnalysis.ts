import { useEffect, useState } from 'react'
import { api, describeAnalysisError, type AnalysisQuery } from '@/api/client'
import type { AnalysisResponse, CropId, Satellite } from '@/api/types'
import type { Step } from '@/components/LoadingSteps'
import { mockRequested, runMockAnalysis, runMockSatellite } from '@/mocks/useMockAnalysis'
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
  'Liczę, ile wody zostało (spadło minus wyparowało)',
].map((label) => ({ label, state: 'active' }))

const IDLE: AnalysisRun = { phase: 'idle' }

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
  opts: { point?: [number, number] | null; cropHistory?: string[]; area?: number | null; plannedCrops?: string[] } = {},
) {
  const extra = `${opts.point?.join(',') ?? ''}|${(opts.cropHistory ?? []).join(',')}|${opts.area ?? ''}|${(opts.plannedCrops ?? []).join(',')}`
  const [attempt, setAttempt] = useState(0)
  // wynik przypisany do konkretnego przebiegu; inny klucz = nowe przeliczenie (stan „ładowanie” liczony w renderze)
  const [result, setResult] = useState<{ key: string; run: AnalysisRun } | null>(null)
  const key = parcelId ? `${parcelId}|${crop ?? ''}|${date}|${extra}|${attempt}` : null

  useEffect(() => {
    if (!parcelId || !key) return
    const ctrl = new AbortController()
    const publish = (run: AnalysisRun) => {
      if (!ctrl.signal.aborted) setResult({ key, run })
    }
    const mock = import.meta.env.DEV && mockRequested()
    const q: AnalysisQuery = { parcelId, point: opts.point, crop, date, cropHistory: opts.cropHistory, area: opts.area, plannedCrops: opts.plannedCrops }
    const request = mock
      ? runMockAnalysis((steps) => publish({ phase: 'loading', steps, key }), ctrl.signal, opts.point)
      : api.analysis(q, ctrl.signal)

    async function loadSatellite(first: AnalysisResponse) {
      const done = (analysis: AnalysisResponse) => publish({ phase: 'done', analysis, key: key! })
      try {
        const sat = mock ? await runMockSatellite(ctrl.signal) : await api.satellite(q, ctrl.signal)
        if (sat.status !== 'ok' || mock) return done({ ...first, satellite: sat })
        // zdjęcie jest w cache serwera – ta sama analiza jeszcze raz, już z satelitą
        const fresh = await api.analysis(q, ctrl.signal).catch((e) => {
          if ((e as Error).name === 'AbortError') throw e
          return null
        })
        done(fresh && fresh.satellite?.status === 'ok' ? fresh : { ...first, satellite: sat })
      } catch (e) {
        if ((e as Error).name === 'AbortError' || ctrl.signal.aborted) return
        done({ ...first, satellite: satelliteFailed(first.satellite) })
      }
    }

    request.then(
      (analysis) => {
        publish({ phase: 'done', analysis, key })
        if (analysis.satellite?.status === 'pending') void loadSatellite(analysis)
      },
      (e) => publish({ phase: 'error', error: describeAnalysisError(e) }),
    )
    return () => ctrl.abort()
    // opts zawarte w `key`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parcelId, crop, date, key])

  const run: AnalysisRun = !key
    ? IDLE
    : result?.key === key
      ? result.run
      : { phase: 'loading', steps: REAL_STEPS, key }
  return { run, retry: () => setAttempt((n) => n + 1) }
}
