import { Droplets, ShowerHead, Sprout, type LucideIcon } from 'lucide-react'
import type { RecommendationCategory } from '@/api/types'

/** Kategorie rekomendacji; kolejność zawsze: retencja → agrotechnika → nawadnianie (SPEC 7.D). */
export const REC_CATEGORY: Record<RecommendationCategory, { label: string; icon: LucideIcon; cls: string }> = {
  retencja: { label: 'Zatrzymaj wodę', icon: Droplets, cls: 'bg-water-soft text-water' },
  agrotechnika: { label: 'Zmiany w uprawie', icon: Sprout, cls: 'bg-ok-soft text-brand' },
  nawadnianie: { label: 'Nawadnianie', icon: ShowerHead, cls: 'bg-surface-2 text-earth' },
}
