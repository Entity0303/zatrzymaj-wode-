import { CloudRain, Flame, Sprout, Trees, type LucideIcon } from 'lucide-react'
import type { CropId } from '@/api/types'
import { todayIso } from '@/lib/dates'

/**
 * „Zobacz przykład” – jeden klik = pełna analiza (uwagi mentora: jury ma 3 minuty).
 * Działki i daty sprawdzone na żywo 21.11.2026 na prawdziwym /api/analysis (.ai/test-parcels.md).
 * Karty opisują scenariusz – wynik zawsze liczy serwer, nic nie jest tu wpisane na sztywno.
 * Do podmiany na GET /api/demo/examples, gdy pojawi się w kontrakcie.
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

export const EXAMPLES: Example[] = [
  {
    id: 'susza-2018',
    icon: Flame,
    tone: 'bg-danger-soft text-danger',
    title: 'Susza 2018',
    text: 'Zboża ozime w lipcu suchego roku – Podlasie',
    parcel: '201305_2.0038.6/1',
    crop: 'zboza_ozime',
    date: '2018-07-15',
  },
  {
    id: 'mokry-2021',
    icon: CloudRain,
    tone: 'bg-water-soft text-water',
    title: 'Wilgotniejszy 2021',
    text: 'To samo pole trzy lata później – porównaj z 2018',
    parcel: '201305_2.0038.6/1',
    crop: 'zboza_ozime',
    date: '2021-07-15',
  },
  {
    id: 'kukurydza-dzis',
    icon: Sprout,
    tone: 'bg-sage-soft text-brand',
    title: 'Kukurydza dziś',
    text: 'Stan wody w glebie na dziś i co robić teraz',
    parcel: '201305_2.0038.6/1',
    crop: 'kukurydza_ziarno',
    date: null,
  },
  {
    id: 'nie-pole',
    icon: Trees,
    tone: 'bg-surface-2 text-earth',
    title: 'To nie jest pole',
    text: 'Działka w większości leśna – aplikacja mówi to wprost',
    parcel: '143203_2.0027.112/11',
    crop: 'zboza_ozime',
    date: null,
  },
]

export const exampleDate = (e: Example) => e.date ?? todayIso()
