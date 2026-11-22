import type { ErrorInfo } from '@/api/client'
import type { AnalysisResponse, Parcel } from '@/api/types'
import type { Step } from '@/components/LoadingSteps'

export type SearchPhase =
  | { phase: 'idle' }
  | { phase: 'loading'; kind: 'number' | 'point' }
  | { phase: 'error'; error: ErrorInfo }
  | { phase: 'candidates'; total: number }
  | { phase: 'parcel'; parcel: Parcel }

export type ForecastState = 'idle' | 'loading' | 'ok' | 'error'

/** Przebieg analizy działki (GET /api/analysis albo symulacja na mocku). */
export type AnalysisRun =
  | { phase: 'idle' }
  | { phase: 'loading'; steps: Step[]; /** zmienia się przy każdym nowym przeliczeniu */ key: string }
  | { phase: 'error'; error: ErrorInfo }
  | { phase: 'done'; analysis: AnalysisResponse; /** klucz przeliczenia – ten sam po dociągnięciu zdjęcia satelitarnego */ key: string }
