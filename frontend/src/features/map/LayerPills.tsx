import { cn } from '@/lib/utils'
import { LAYERS, type LayerKey } from './layers'
import { useLang } from '@/lib/i18n'

/** Pigułki warstw – jedna aktywna, przewijane na telefonie (SPEC 5.3, 14). */
export function LayerPills({ value, onChange, className }: { value: LayerKey; onChange: (k: LayerKey) => void; className?: string }) {
  const { t } = useLang()
  return (
    <div role="radiogroup" aria-label={t('Warstwa mapy')} className={cn('scrollbar-none flex gap-2 overflow-x-auto', className)}>
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
              'flex h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-medium whitespace-nowrap shadow-float transition-colors',
              active ? 'border-brand bg-sage-soft text-brand-dark' : 'border-transparent bg-surface text-text hover:bg-surface-2',
            )}
          >
            <Icon className="size-[18px]" aria-hidden />
            {t(l.label)}
          </button>
        )
      })}
    </div>
  )
}
