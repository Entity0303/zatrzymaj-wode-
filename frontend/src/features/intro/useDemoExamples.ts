import { CloudRain, Flame, Sprout, Trees, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { DemoExample } from '@/api/types'
import { EXAMPLES, type Example } from '@/features/parcel-panel/examples'

/** Wygląd karty przykładu wg identyfikatora z /api/demo/examples (nieznany → liść). */
function look(id: string): { icon: LucideIcon; tone: string } {
  if (/susz|slab|piask/.test(id)) return { icon: Flame, tone: 'bg-danger-soft text-danger' }
  if (/mokr|wilg|dobr/.test(id)) return { icon: CloudRain, tone: 'bg-water-soft text-water' }
  if (/pole|las/.test(id)) return { icon: Trees, tone: 'bg-surface-2 text-earth' }
  return { icon: Sprout, tone: 'bg-sage-soft text-brand' }
}

const toExample = (d: DemoExample): Example => ({
  id: d.id,
  ...look(d.id),
  title: d.title,
  text: d.description,
  parcel: d.parcel_id,
  crop: d.crop,
  date: d.date,
})

/**
 * Przykłady „jednym klikiem” z GET /api/demo/examples (lista z backendu – działki rozgrzane w pamięci serwera).
 * Gdy serwer nie odpowiada – lokalna lista zapasowa (`examples.ts`).
 */
export function useDemoExamples(): Example[] {
  const [list, setList] = useState<Example[]>(EXAMPLES)
  useEffect(() => {
    const ctrl = new AbortController()
    api.demoExamples(ctrl.signal).then(
      (r) => r.length && setList(r.map(toExample)),
      () => undefined,
    )
    return () => ctrl.abort()
  }, [])
  return list
}
