import type { ErrorInfo } from '@/api/client'
import type { Parcel } from '@/api/types'

export type SearchPhase =
  | { phase: 'idle' }
  | { phase: 'loading'; kind: 'number' | 'point' }
  | { phase: 'error'; error: ErrorInfo }
  | { phase: 'candidates'; total: number }
  | { phase: 'parcel'; parcel: Parcel }

export type ForecastState = 'idle' | 'loading' | 'ok' | 'error'
