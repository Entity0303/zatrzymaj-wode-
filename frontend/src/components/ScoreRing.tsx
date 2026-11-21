import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/**
 * Okrąg 0–100 z liczbą w środku (SPEC 14, styl ref-style).
 * value = null -> przerywany szary okrąg i „—” (brak danych, nigdy zero).
 */
export function ScoreRing({
  value,
  size = 64,
  stroke = 7,
  color = 'var(--color-ok)',
  track = 'var(--color-ok-soft)',
  caption,
  className,
}: {
  value: number | null
  size?: number
  stroke?: number
  color?: string
  /** tor okręgu – jasny odcień koloru (ref-style) */
  track?: string
  caption?: string
  className?: string
}) {
  const { t } = useLang()
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const v = value === null ? 0 : Math.max(0, Math.min(100, value))
  return (
    <div
      className={cn('relative inline-flex shrink-0 items-center justify-center', className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={value === null ? t('Brak danych') : t('{v} na 100', { v: Math.round(v) })}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={value === null ? 'var(--color-nodata)' : track}
          strokeWidth={stroke}
          strokeDasharray={value === null ? '4 5' : undefined}
        />
        {value !== null && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${(v / 100) * c} ${c}`}
          />
        )}
      </svg>
      <span className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className={cn('tabular font-semibold', size >= 120 ? 'text-[40px]' : size >= 80 ? 'text-2xl' : 'text-base', value === null && 'text-text-muted')}>
          {value === null ? '—' : Math.round(v)}
        </span>
        {caption && <span className="mt-0.5 text-xs text-text-muted">{t(caption)}</span>}
      </span>
    </div>
  )
}
