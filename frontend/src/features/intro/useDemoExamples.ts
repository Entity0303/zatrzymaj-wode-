import { Droplets, Flame, Leaf, Mountain, Sprout, Trees, Waves, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { DemoExample } from '@/api/types'
import type { Example } from '@/features/parcel-panel/examples'

/** Wygląd karty przykładu – tylko ikona i kolor, dobierane po identyfikatorze z /api/demo/examples (nieznany → liść). */
function look(id: string): { icon: LucideIcon; tone: string } {
  if (/stok|pogorz|eroz|less/.test(id)) return { icon: Mountain, tone: 'bg-warn-soft text-[#875a12]' }
  if (/obniz|oczk|pojez/.test(id)) return { icon: Droplets, tone: 'bg-water-soft text-water' }
  if (/zulaw|mad/.test(id)) return { icon: Waves, tone: 'bg-water-soft text-water' }
  if (/susz|kujaw/.test(id)) return { icon: Flame, tone: 'bg-danger-soft text-danger' }
  if (/slab|piask/.test(id)) return { icon: Sprout, tone: 'bg-amber-soft text-[#875a12]' }
  if (/las|pole/.test(id)) return { icon: Trees, tone: 'bg-surface-2 text-earth' }
  return { icon: Leaf, tone: 'bg-ok-soft text-brand' }
}

/**
 * Krótszy tytuł dla rodzaju działki (tylko wygląd – gdy tytuł z API jest długi, a jego pierwszy człon mało mówi
 * rolnikowi, np. „Less – Drzewce-Kolonia 203 (gm. Nałęczów)”). Klucz = fragment `id` z /api/demo/examples.
 */
const SHORT_BY_ID: [RegExp, string][] = [
  [/less/, 'Stok na lessie'],
  [/mad[ya]?|zulaw/, 'Mady na Żuławach'],
  [/piask|slab/, 'Słaba ziemia'],
]

/**
 * Tytuł karty: maks. 3 słowa. Długi tytuł („Rodzaj – Miejscowość 203 (gm. X)”) → krótki tytuł z pierwszego członu
 * (albo z SHORT_BY_ID), a miejscowość trafia na początek opisu („Drzewce-Kolonia 203, gm. Nałęczów · …”); opis w karcie – maks. 2 linie.
 */
export function shortExample(d: Pick<DemoExample, 'id' | 'title' | 'description'>): { title: string; text: string } {
  const title = d.title.trim()
  const words = title.split(/\s+/).length
  if (words <= 3 && !/[–(]/.test(title)) return { title, text: d.description }
  const [head, ...rest] = title.split(/\s+[–-]\s+/)
  const place = rest
    .join(' – ')
    .replace(/\s*\(([^)]+)\)\s*/g, ', $1')
    .replace(/,\s*$/, '')
    .trim()
  const byId = SHORT_BY_ID.find(([re]) => re.test(d.id))?.[1]
  const short = byId ?? head.replace(/\s*\(.*$/, '').split(/\s+/).slice(0, 3).join(' ')
  return { title: short, text: place ? `${place} · ${d.description}` : d.description }
}

const toExample = (d: DemoExample): Example => ({
  id: d.id,
  ...look(d.id),
  ...shortExample(d),
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
