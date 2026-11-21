import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** Przełącznik 2D | 3D (SPEC 4.2, 8) – 3D: teren działki i okolicy z ortofotomapą. */
export function ViewToggle({ value, onChange, className }: { value: '2d' | '3d'; onChange: (v: '2d' | '3d') => void; className?: string }) {
  const { t } = useLang()
  const btn = (v: '2d' | '3d', label: string) => (
    <button
      type="button"
      role="radio"
      aria-checked={value === v}
      onClick={() => onChange(v)}
      className={cn(
        'h-8 min-w-11 rounded-full px-3.5 text-sm font-semibold transition-colors',
        value === v ? 'bg-brand text-white' : 'text-text-muted hover:bg-surface-2',
      )}
    >
      {label}
    </button>
  )
  return (
    <div role="radiogroup" aria-label={t('Widok mapy')} className={cn('flex h-10 shrink-0 items-center rounded-full bg-surface p-1 shadow-float', className)}>
      {btn('2d', '2D')}
      {btn('3d', '3D')}
    </div>
  )
}
