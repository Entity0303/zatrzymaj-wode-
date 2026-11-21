import type { CSSProperties } from 'react'
import { cn } from '@/lib/utils'
import type { LegendSpec } from './layers/types'
import { useLang } from '@/lib/i18n'

// LegendCard: ciemna karta z paskiem gradientu i opisami krańców (SPEC 5.3, 14)

function Symbol({ symbol }: { symbol: 'arrow' | 'spot' | 'outflow' | 'line' | 'pin' }) {
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
}: {
  compact?: boolean
  title: string
  legend: LegendSpec
  /** komunikat o stanie danych warstwy (np. brak danych) – zawsze widoczny jako tekst */
  status?: string
  className?: string
  style?: CSSProperties
}) {
  const { t } = useLang()
  return (
    <section
      aria-label={t('Legenda: {title}', { title: t(title) })}
      style={style}
      className={cn('w-60 rounded-xl bg-legend/90 text-sm leading-5 text-white shadow-float', compact ? 'p-2.5' : 'p-3', className)}
    >
      <h3 className={cn('text-sm font-semibold', compact ? 'mb-1.5' : 'mb-2')}>{t(title)}</h3>
      {legend.kind === 'gradient' && (
        <>
          <div className="h-2.5 rounded-full" style={{ background: `linear-gradient(90deg, ${legend.colors.join(',')})` }} />
          <div className="mt-1.5 flex justify-between gap-2 text-xs leading-4 text-white/85">
            <span>{t(legend.left)}</span>
            <span className="text-right">{t(legend.right)}</span>
          </div>
          {legend.note && !compact && <p className="mt-1 text-xs leading-4 text-white/70">{t(legend.note)}</p>}
        </>
      )}
      {legend.kind === 'classes' && (
        <ul className="space-y-1">
          {legend.items.map((it) => (
            <li key={it.label} className="flex items-center gap-2 text-xs leading-4">
              <span className="size-3.5 shrink-0 rounded-[4px] ring-1 ring-white/25" style={{ background: it.color }} />
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
    </section>
  )
}
