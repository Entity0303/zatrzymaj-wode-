import { FileText, House, Map as MapIcon, Settings, type LucideIcon } from 'lucide-react'

export type Section = { key: string; label: string; short: string; icon: LucideIcon; ready: boolean }

/** Cztery sekcje (SPEC 3). Gotowy jest na razie tylko „Start”. */
export const SECTIONS: Section[] = [
  { key: 'start', label: 'Start', short: 'Start', icon: House, ready: true },
  { key: 'parcels', label: 'Moje działki', short: 'Działki', icon: MapIcon, ready: false },
  { key: 'reports', label: 'Raporty', short: 'Raporty', icon: FileText, ready: false },
  { key: 'settings', label: 'Ustawienia', short: 'Ustawienia', icon: Settings, ready: false },
]

export const ACTIVE = 'start'
