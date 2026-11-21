import { ChevronDown, Droplets, MapPinned, ShowerHead, Sprout, type LucideIcon } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { SourceTag } from './SourceTag'

/** Kolejność zawsze: RETENCJA → AGROTECHNIKA → NAWADNIANIE (CLAUDE.md, SPEC 7.D). */
export type RecCategory = 'retencja' | 'agrotechnika' | 'nawadnianie'

export const REC_CATEGORY: Record<RecCategory, { label: string; icon: LucideIcon; cls: string }> = {
  retencja: { label: 'Zatrzymaj wodę', icon: Droplets, cls: 'bg-water-soft text-water' },
  agrotechnika: { label: 'Zmiany w uprawie', icon: Sprout, cls: 'bg-ok-soft text-brand' },
  nawadnianie: { label: 'Nawadnianie', icon: ShowerHead, cls: 'bg-surface-2 text-earth' },
}

/**
 * Karta rekomendacji (SPEC 14): ikona kategorii, tytuł, zdanie, rozwijane „Dlaczego?”,
 * opcjonalnie „Pokaż na mapie”. noData = karta-zaślepka bez treści udającej wynik.
 */
export function RecommendationCard({
  category,
  title,
  text,
  why,
  noData,
  onShowOnMap,
}: {
  category: RecCategory
  title: string
  text: string
  why: ReactNode
  noData?: boolean
  onShowOnMap?: () => void
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const c = REC_CATEGORY[category]
  const Icon = c.icon
  return (
    <div className={cn('rounded-xl border bg-surface p-3.5 shadow-card', noData && 'hatch-nodata')}>
      <div className="flex gap-3">
        <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-lg', noData ? 'bg-surface-2 text-text-muted' : c.cls)}>
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs leading-4 font-medium tracking-wide text-text-muted uppercase">{c.label}</p>
          <p className="text-base leading-6 font-semibold">{title}</p>
          <p className="text-sm leading-5 text-text-muted">{text}</p>
          {noData && <SourceTag kind="brak" className="mt-2" />}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 pl-12">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen((o) => !o)}
          className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-brand hover:underline"
        >
          Dlaczego?
          <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
        </button>
        {onShowOnMap && (
          <button
            type="button"
            onClick={onShowOnMap}
            className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-brand hover:underline"
          >
            <MapPinned className="size-4" aria-hidden /> Pokaż na mapie
          </button>
        )}
      </div>
      {open && (
        <div id={id} className="mt-1 ml-12 rounded-lg bg-surface-2/70 p-3 text-sm leading-5 text-text">
          {why}
        </div>
      )}
    </div>
  )
}
