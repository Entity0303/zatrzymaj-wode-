import { Crosshair, Layers2, LocateFixed, Minus, Plus, type LucideIcon } from 'lucide-react'
import { useState, type CSSProperties } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { LegendSpec } from '@/lib/layers'
import { cn } from '@/lib/utils'
import type { BaseMap } from './ParcelMap'

// ── MapControls: pionowa grupa białych kwadratowych przycisków 44 px (SPEC 5.2, 14) ──────────

function CtrlButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  pressed,
}: {
  icon: LucideIcon
  label: string
  onClick: () => void
  disabled?: boolean
  pressed?: boolean
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          aria-pressed={pressed}
          onClick={onClick}
          disabled={disabled}
          className="flex size-11 items-center justify-center bg-surface text-text transition-colors hover:bg-ok-soft hover:text-brand disabled:text-text-muted/40 disabled:hover:bg-surface"
        >
          <Icon className="size-5" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  )
}

export function MapControls({
  onZoomIn,
  onZoomOut,
  onBackToParcel,
  onLocate,
  canGoBack,
  baseMap,
  onBaseMapChange,
  className,
  style,
}: {
  onZoomIn: () => void
  onZoomOut: () => void
  onBackToParcel: () => void
  onLocate: () => void
  canGoBack: boolean
  baseMap: BaseMap
  onBaseMapChange: (b: BaseMap) => void
  className?: string
  style?: CSSProperties
}) {
  const [baseOpen, setBaseOpen] = useState(false)
  return (
    <div className={cn('flex flex-col items-start gap-2', className)} style={style}>
      {/* mały przycisk podkładu mapy (SPEC 5.1) */}
      <div className="relative">
        <div className="overflow-hidden rounded-md border shadow-float">
          <CtrlButton icon={Layers2} label="Podkład mapy" onClick={() => setBaseOpen((o) => !o)} pressed={baseOpen} />
        </div>
        {baseOpen && (
          <div
            role="radiogroup"
            aria-label="Podkład mapy"
            className="absolute bottom-0 left-full z-10 ml-2 flex w-44 flex-col gap-1 rounded-xl border bg-surface p-1.5 shadow-float max-md:top-0 max-md:right-full max-md:bottom-auto max-md:left-auto max-md:mr-2 max-md:ml-0"
          >
            {(
              [
                ['orto', 'Ortofotomapa'],
                ['osm', 'Mapa (OpenStreetMap)'],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                role="radio"
                aria-checked={baseMap === k}
                onClick={() => {
                  onBaseMapChange(k)
                  setBaseOpen(false)
                }}
                className={cn(
                  'min-h-11 rounded-md px-3 text-left text-sm font-medium',
                  baseMap === k ? 'bg-ok-soft text-brand' : 'hover:bg-surface-2',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex flex-col divide-y overflow-hidden rounded-md border shadow-float">
        <CtrlButton icon={Plus} label="Przybliż" onClick={onZoomIn} />
        <CtrlButton icon={Minus} label="Oddal" onClick={onZoomOut} />
        <CtrlButton icon={Crosshair} label="Wróć do mojej działki" onClick={onBackToParcel} disabled={!canGoBack} />
        <CtrlButton icon={LocateFixed} label="Moja lokalizacja" onClick={onLocate} />
      </div>
    </div>
  )
}

// ── LegendCard: ciemna karta z paskiem gradientu i opisami krańców (SPEC 5.3, 14) ────────────

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
  return (
    <section
      aria-label={`Legenda: ${title}`}
      style={style}
      className={cn('w-60 rounded-xl bg-legend/90 text-sm leading-5 text-white shadow-float', compact ? 'p-2.5' : 'p-3', className)}
    >
      <h3 className={cn('text-sm font-semibold', compact ? 'mb-1.5' : 'mb-2')}>{title}</h3>
      {legend.kind === 'gradient' && (
        <>
          <div className="h-2.5 rounded-full" style={{ background: `linear-gradient(90deg, ${legend.colors.join(',')})` }} />
          <div className="mt-1.5 flex justify-between gap-2 text-xs leading-4 text-white/85">
            <span>{legend.left}</span>
            <span className="text-right">{legend.right}</span>
          </div>
          {legend.note && !compact && <p className="mt-1 text-xs leading-4 text-white/70">{legend.note}</p>}
        </>
      )}
      {legend.kind === 'classes' && (
        <ul className="space-y-1">
          {legend.items.map((it) => (
            <li key={it.label} className="flex items-center gap-2 text-xs leading-4">
              <span className="size-3.5 shrink-0 rounded-[4px] ring-1 ring-white/25" style={{ background: it.color }} />
              {it.label}
            </li>
          ))}
        </ul>
      )}
      {legend.kind === 'symbols' && (
        <ul className="space-y-1">
          {legend.items.map((it) => (
            <li key={it.label} className="flex items-center gap-2 text-xs leading-4">
              <Symbol symbol={it.symbol} />
              {it.label}
            </li>
          ))}
        </ul>
      )}
      {status && (
        <p className="mt-2 flex items-start gap-1.5 border-t border-white/15 pt-2 text-xs leading-4 text-white/85">
          <span className="mt-1 size-2 shrink-0 rounded-full bg-nodata" aria-hidden />
          {status}
        </p>
      )}
    </section>
  )
}
