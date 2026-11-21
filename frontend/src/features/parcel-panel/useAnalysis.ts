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
 * Analiza działki: startuje, gdy jest działka i uprawa; zmiana uprawy lub daty przelicza ją od nowa
 * (poprzednie zapytanie jest przerywane). Na mocku (?dane=przykladowe) – symulacja kroków.
 */
export function useAnalysis(parcelId: string | null, crop: CropId | null, date: string) {
  const [attempt, setAttempt] = useState(0)
  // wynik przypisany do konkretnego przebiegu; inny klucz = nowe przeliczenie (stan „ładowanie” liczony w renderze)
  const [result, setResult] = useState<{ key: string; run: AnalysisRun } | null>(null)
  const key = parcelId && crop ? `${parcelId}|${crop}|${date}|${attempt}` : null

  useEffect(() => {
    if (!parcelId || !crop || !key) return
    const ctrl = new AbortController()
    const publish = (run: AnalysisRun) => {
      if (!ctrl.signal.aborted) setResult({ key, run })
    }
    const request =
      import.meta.env.DEV && mockRequested()
        ? runMockAnalysis((steps) => publish({ phase: 'loading', steps, key }), ctrl.signal)
        : api.analysis(parcelId, crop, date, ctrl.signal)
    request.then(
      (analysis) => publish({ phase: 'done', analysis }),
      (e) => publish({ phase: 'error', error: describeAnalysisError(e) }),
    )
    return () => ctrl.abort()
  }, [parcelId, crop, date, key])

  const run: AnalysisRun = !key
    ? IDLE
    : result?.key === key
      ? result.run
      : { phase: 'loading', steps: REAL_STEPS, key }
  return { run, retry: () => setAttempt((n) => n + 1) }
}
