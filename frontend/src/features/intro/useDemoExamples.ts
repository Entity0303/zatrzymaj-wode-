import { Droplets, Flame, Leaf, Mountain, Sprout, Trees, Waves, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { DemoExample } from '@/api/types'
import type { Example } from '@/features/parcel-panel/examples'

/** Wygląd karty przykładu – tylko ikona i kolor, dobierane po identyfikatorze z /api/demo/examples (nieznany → liść). */
function look(id: string): { icon: LucideIcon; tone: string } {
  if (/stok|pogorz|eroz/.test(id)) return { icon: Mountain, tone: 'bg-warn-soft text-[#875a12]' }
  if (/obniz|oczk|pojez/.test(id)) return { icon: Droplets, tone: 'bg-water-soft text-water' }
  if (/zulaw|mad/.test(id)) return { icon: Waves, tone: 'bg-water-soft text-water' }
  if (/susz|kujaw/.test(id)) return { icon: Flame, tone: 'bg-danger-soft text-danger' }
  if (/slab|piask/.test(id)) return { icon: Sprout, tone: 'bg-amber-soft text-[#875a12]' }
  if (/las|pole/.test(id)) return { icon: Trees, tone: 'bg-surface-2 text-earth' }
  return { icon: Leaf, tone: 'bg-ok-soft text-brand' }
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

export type DemoExamples = { examples: Example[]; state: 'loading' | 'ok' | 'error' }

/**
 * Przykłady „jednym klikiem” z GET /api/demo/examples – bez listy zapasowej w kodzie.
 * Serwer nie odpowiada → `state: 'error'` (karta powitalna mówi, że przykłady są chwilowo niedostępne).
 */
export function useDemoExamples(): DemoExamples {
  const [res, setRes] = useState<DemoExamples>({ examples: [], state: 'loading' })
  useEffect(() => {
    const ctrl = new AbortController()
    api.demoExamples(ctrl.signal).then(
      (r) => setRes({ examples: r.map(toExample), state: r.length ? 'ok' : 'error' }),
      (e) => (e as Error).name !== 'AbortError' && setRes({ examples: [], state: 'error' }),
    )
    return () => ctrl.abort()
  }, [])
  return res
}
