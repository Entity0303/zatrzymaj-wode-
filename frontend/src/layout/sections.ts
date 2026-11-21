import { FileText, House, Map as MapIcon, Settings, type LucideIcon } from 'lucide-react'

import type { PageKey } from '@/lib/router'

export type Section = { key: PageKey; label: string; short: string; icon: LucideIcon; ready: boolean }

/** Cztery sekcje (SPEC 3). */
export const SECTIONS: Section[] = [
  { key: 'start', label: 'Start', short: 'Start', icon: House, ready: true },
  { key: 'parcels', label: 'Moje działki', short: 'Działki', icon: MapIcon, ready: true },
  { key: 'reports', label: 'Raporty', short: 'Raporty', icon: FileText, ready: true },
  { key: 'settings', label: 'Ustawienia', short: 'Ustawienia', icon: Settings, ready: true },
]

