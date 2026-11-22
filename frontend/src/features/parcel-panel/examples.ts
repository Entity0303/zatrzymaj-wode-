import type { LucideIcon } from 'lucide-react'
import type { CropId } from '@/api/types'
import { todayIso } from '@/lib/dates'

/**
 * „Zobacz przykład” – jeden klik = pełna analiza (uwagi mentora: jury ma 3 minuty).
 * Lista przychodzi WYŁĄCZNIE z GET /api/demo/examples (działki rozgrzane w pamięci serwera) – tu jest tylko
 * kształt karty; wynik zawsze liczy serwer.
 */
export type Example = {
  id: string
  icon: LucideIcon
  tone: string
  title: string
  text: string
  parcel: string
  crop: CropId
  /** null = dziś */
  date: string | null
}

export const exampleDate = (e: Example) => e.date ?? todayIso()
