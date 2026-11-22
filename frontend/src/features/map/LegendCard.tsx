import type { CSSProperties } from 'react'
import { ChevronDown, ChevronUp, RotateCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LegendSpec } from './layers/types'
import { useLang } from '@/lib/i18n'

// LegendCard: ciemna karta z paskiem gradientu i opisami krańców (SPEC 5.3, 14)

function Symbol({ symbol }: { symbol: 'arrow' | 'spot' | 'outflow' | 'line' | 'pin' | 'pond' }) {
  const common = { width: 22, height: 14, 'aria-hidden': true }
  switch (symbol) {
    case 'arrow':
      return (
        <svg {...common} viewBox="0 0 22 14">
          <path d="M2 7h15m-4-4 4 4-4 4" stroke="#9cc7ef" strokeWidth="2" fill="none" strokeLinecap="round" />
        </svg>
      )
    case 'spot':
      return (
        <svg {...common} viewBox="0 0 22 14">
          <ellipse cx="11" cy="7" rx="9" ry="5.5" fill="#2F80C9" opacity=".85" />
        </svg>
      )
    case 'outflow':
      return (
        <svg {...common} viewBox="0 0 22 14">
          <path d="M2 7h15m-4-4 4 4-4 4" stroke="#E5675C" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </svg>
      )
    case 'line':
      return (
        <svg {...common} viewBox="0 0 22 14">
          <path d="M1 10c5-6 9 2 20-6" stroke="#4fa3ec" strokeWidth="2.5" fill="none" />
        </svg>
      )
    case 'pond':
      return (
        <svg {...common} viewBox="0 0 22 14">
          <circle cx="11" cy="7" r="5" fill="#2E5B3F" stroke="#fff" strokeWidth="1.5" />
        </svg>
      )
    case 'pin':
      return (
        <svg {...common} viewBox="0 0 22 14">
          <circle cx="11" cy="6" r="4.5" fill="#E8B931" stroke="#fff" strokeWidth="1.5" />
        </svg>
      )
  }
}

export function LegendCard({
  title,
  legend,
  status,
  compact,
  className,
  style,
  collapsed,
  onToggle,
  onRetry,
}: {
  /** błąd pobrania warstwy – przycisk „Spróbuj ponownie” (to samo zapytanie: warstwa, działka, data) */
  onRetry?: () => void
  /** zwinięta do pigułki z nazwą warstwy (komputer) */
  collapsed?: boolean
  onToggle?: () => void
  compact?: boolean
  title: string
  legend: LegendSpec
  /** komunikat o stanie danych warstwy (np. brak danych) – zawsze widoczny jako tekst */
  status?: string
  className?: string
  style?: CSSProperties
}) {
  const { t } = useLang()
  if (collapsed && onToggle) {
    // zwinięta: sam pasek kolorów warstwy (gradient albo próbki klas) – rozwija się po kliknięciu
    const colors =
      legend.kind === 'gradient' ? null : legend.kind === 'classes' ? legend.items.map((i) => i.color) : ['#9cc7ef', '#2F80C9', '#E5675C']
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={false}
        aria-label={t('Pokaż legendę: {title}', { title: t(title) })}
        style={style}
        className={cn('flex h-9 w-56 items-center gap-2 rounded-full bg-legend/90 px-3 shadow-float hover:bg-legend', className)}
      >
        {colors ? (
          <span className="flex h-2 flex-1 overflow-hidden rounded-full" aria-hidden>
            {colors.map((c) => (
              <span key={c} className="flex-1" style={{ background: c }} />
            ))}
          </span>
        ) : (
          legend.kind === 'gradient' && (
            <span className="h-2 flex-1 rounded-full" style={{ background: `linear-gradient(90deg, ${legend.colors.join(',')})` }} aria-hidden />
          )
        )}
        <ChevronUp className="size-4 text-white/80" aria-hidden />
      </button>
    )
  }
  return (
    <section
      aria-label={t('Legenda: {title}', { title: t(title) })}
      style={style}
      className={cn('w-64 rounded-lg bg-legend/90 text-sm leading-5 text-white shadow-float', compact ? 'px-3 py-2.5' : 'px-3.5 py-3', className)}
    >
      <div className={cn('flex items-center gap-2', compact ? 'mb-1.5' : 'mb-2')}>
        <h3 className="min-w-0 flex-1 text-sm font-semibold">{t(title)}</h3>
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-expanded
            aria-label={t('Zwiń legendę')}
            className="-my-1 -mr-1.5 flex size-8 items-center justify-center rounded-full text-white/80 hover:bg-white/10"
          >
            <ChevronDown className="size-4" />
          </button>
        )}
      </div>
      {legend.kind === 'gradient' && (
        <>
          <div className="flex gap-1.5">
            <div className="h-1.5 flex-1 rounded-full" style={{ background: `linear-gradient(90deg, ${legend.colors.join(',')})` }} />
            {legend.extra && <div className="h-1.5 w-10 rounded-full" style={{ background: legend.extra.color }} />}
          </div>
          <div className="mt-1.5 flex justify-between gap-2 text-xs leading-4 text-white/85">
            <span>{t(legend.left)}</span>
            <span className="flex gap-3 text-right">
              {t(legend.right)}
              {legend.extra && <span className="w-10 text-center">{t(legend.extra.label)}</span>}
            </span>
          </div>
          {legend.note && !compact && <p className="mt-1 text-xs leading-4 text-white/70">{t(legend.note)}</p>}
        </>
      )}
      {legend.kind === 'classes' && (
        <ul className="space-y-1">
          {legend.items.map((it) => (
            <li key={it.label} className="flex items-center gap-2 text-xs leading-4">
              <span className="size-3 shrink-0 rounded-full ring-1 ring-white/25" style={{ background: it.color }} />
              {t(it.label)}
            </li>
          ))}
        </ul>
      )}
      {legend.kind === 'symbols' && (
        <ul className="space-y-1">
          {legend.items.map((it) => (
            <li key={it.label} className="flex items-center gap-2 text-xs leading-4">
              <Symbol symbol={it.symbol} />
              {t(it.label)}
            </li>
          ))}
        </ul>
      )}
      {status && (
        <p className="mt-2 flex items-start gap-1.5 border-t border-white/15 pt-2 text-xs leading-4 text-white/85">
          <span className="mt-1 size-2 shrink-0 rounded-full bg-nodata" aria-hidden />
          {t(status)}
        </p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 flex min-h-11 w-full items-center justify-center gap-1.5 rounded-md bg-white/15 px-3 text-sm font-semibold text-white hover:bg-white/25"
        >
          <RotateCw className="size-4" aria-hidden /> {t('Spróbuj ponownie')}
        </button>
      )}
    </section>
  )
}
