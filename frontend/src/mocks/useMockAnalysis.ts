import type { AnalysisResponse } from '@/api/types'
import type { Step } from '@/components/LoadingSteps'

/**
 * Przykładowa odpowiedź /api/analysis (mocks/analysis.sample.json) – WYŁĄCZNIE do pracy nad UI,
 * zanim backend policzy analizę. Włącza się tylko w trybie deweloperskim (npm run dev) i tylko
 * z parametrem w adresie: http://localhost:5173/?dane=przykladowe
 * W buildzie produkcyjnym ten kod (i plik JSON) jest usuwany. UI pokazuje wtedy „DANE PRZYKŁADOWE”.
 */
export const mockRequested = () =>
  import.meta.env.DEV && new URLSearchParams(window.location.search).get('dane') === 'przykladowe'

/** pojedynczy krok w symulacji trwa tyle, ile w mocku (`duration_ms`), ale nie dłużej niż 2,5 s */
const MAX_STEP_MS = 2500

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => {
      clearTimeout(t)
      reject(new DOMException('aborted', 'AbortError'))
    })
  })
}

/**
 * Symulacja ekranu ładowania na mocku: kroki z analysis.sample.json przechodzą kolejno
 * ⏳ → ✓ w tempie `duration_ms`, na końcu zwracamy przykładową odpowiedź.
 */
export async function runMockAnalysis(onSteps: (steps: Step[]) => void, signal: AbortSignal): Promise<AnalysisResponse> {
  const data = (await import('./analysis.sample.json')).default as unknown as AnalysisResponse
  const final = data.steps
  for (let i = 0; i < final.length; i++) {
    onSteps(
      final.map((s, j) => ({
        label: s.label,
        state: j < i ? s.state : j === i ? 'active' : 'pending',
        note: j < i ? (s.note ?? undefined) : undefined,
      })),
    )
    await wait(Math.min(final[i].duration_ms ?? 500, MAX_STEP_MS), signal)
  }
  return data
}
