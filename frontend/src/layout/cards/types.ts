import type { AnalysisResponse, Forecast } from '@/api/types'
import type { SavedParcel } from '@/lib/hooks'

/** Wspólne dane dolnego paska kart (komputer) i ich pionowej wersji w szufladzie (telefon). */
export type BottomCardsProps = {
  saved: SavedParcel[]
  forecast: Forecast | null
  forecastLoading: boolean
  forecastError: boolean
  where: string
  historical: boolean
  updated: string | null
  /** wynik analizy wybranej działki (null = brak / w toku) */
  analysis: AnalysisResponse | null
  asOf: string
  onAsOfChange: (iso: string) => void
}
