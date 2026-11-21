import { useEffect, useState } from 'react'
import type { AnalysisResponse } from '@/api/types'

/**
 * Przykładowa odpowiedź /api/analysis (mocks/analysis.sample.json) – WYŁĄCZNIE do pracy nad UI,
 * zanim backend policzy analizę. Włącza się tylko w trybie deweloperskim (npm run dev) i tylko
 * z parametrem w adresie: http://localhost:5173/?dane=przykladowe
 * W buildzie produkcyjnym ten kod (i plik JSON) jest usuwany. UI pokazuje wtedy „DANE PRZYKŁADOWE”.
 */
export const mockRequested = () =>
  import.meta.env.DEV && new URLSearchParams(window.location.search).get('dane') === 'przykladowe'

export function useMockAnalysis(): AnalysisResponse | null {
  const [mock, setMock] = useState<AnalysisResponse | null>(null)
  useEffect(() => {
    if (!import.meta.env.DEV || !mockRequested()) return
    import('./analysis.sample.json').then((m) => setMock(m.default as unknown as AnalysisResponse))
  }, [])
  return mock
}
