import { cn } from '@/lib/utils'
import { LAYERS, type LayerKey } from './layers'

/** Pigułki warstw – jedna aktywna, przewijane na telefonie (SPEC 5.3, 14). */
export function LayerPills({ value, onChange, className }: { value: LayerKey; onChange: (k: LayerKey) => void; className?: string }) {
  return (
    <div role="radiogroup" aria-label="Warstwa mapy" className={cn('scrollbar-none flex gap-2 overflow-x-auto', className)}>
      {LAYERS.map((l) => {
        const active = l.key === value
        const Icon = l.icon
        return (
          <button
            key={l.key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(l.key)}
            className={cn(
              'flex h-10 shrink-0 items-center gap-2 rounded-full border px-3.5 text-sm font-medium whitespace-nowrap shadow-float transition-colors',
              active ? 'border-brand bg-ok-soft text-brand' : 'border-transparent bg-surface text-text hover:bg-surface-2',
            )}
          >
            <Icon className="size-[18px]" aria-hidden />
            {l.label}
          </button>
        )
      })}
    </div>
  )
}
