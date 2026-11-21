import { useEffect, useState } from 'react'
import { api, describeAnalysisError } from '@/api/client'
import type { CropId } from '@/api/types'
import type { Step } from '@/components/LoadingSteps'
import { mockRequested, runMockAnalysis } from '@/mocks/useMockAnalysis'
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
  'Zdjęcia satelitarne',
  'Liczę bilans wody',
].map((label) => ({ label, state: 'active' }))

const IDLE: AnalysisRun = { phase: 'idle' }

/**
 * Analiza działki: startuje od razu po wybraniu działki – uprawa jest opcjonalna („Stan działki” + ranking);
 * zmiana uprawy, daty, historii pola lub powierzchni przelicza od nowa (poprzednie zapytanie jest przerywane).
 * `point` – działka bez granic z ULDK (obszar przybliżony). Na mocku (?dane=przykladowe) – symulacja kroków.
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
    const request =
      import.meta.env.DEV && mockRequested()
        ? runMockAnalysis((steps) => publish({ phase: 'loading', steps, key }), ctrl.signal)
        : api.analysis({ parcelId, point: opts.point, crop, date, cropHistory: opts.cropHistory, area: opts.area, plannedCrops: opts.plannedCrops }, ctrl.signal)
    request.then(
      (analysis) => publish({ phase: 'done', analysis }),
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
