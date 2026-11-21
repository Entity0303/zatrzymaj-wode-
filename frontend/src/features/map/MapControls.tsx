import { Crosshair, Layers2, LocateFixed, Minus, Plus, type LucideIcon } from 'lucide-react'
import { useState, type CSSProperties } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { BaseMap } from './ParcelMap'
import { useLang } from '@/lib/i18n'

// MapControls: pionowa grupa białych kwadratowych przycisków 44 px (SPEC 5.2, 14)

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
  const { t } = useLang()
  const [baseOpen, setBaseOpen] = useState(false)
  return (
    <div className={cn('flex flex-col items-start gap-2', className)} style={style}>
      {/* mały przycisk podkładu mapy (SPEC 5.1) */}
      <div className="relative">
        <div className="overflow-hidden rounded-md shadow-float">
          <CtrlButton icon={Layers2} label={t('Podkład mapy')} onClick={() => setBaseOpen((o) => !o)} pressed={baseOpen} />
        </div>
        {baseOpen && (
          <div
            role="radiogroup"
            aria-label={t('Podkład mapy')}
            className="absolute bottom-0 left-full z-10 ml-2 flex w-44 flex-col gap-1 rounded-xl bg-surface p-1.5 shadow-float max-md:top-0 max-md:right-full max-md:bottom-auto max-md:left-auto max-md:mr-2 max-md:ml-0"
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
                {t(label)}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex flex-col divide-y divide-line overflow-hidden rounded-md shadow-float">
        <CtrlButton icon={Plus} label={t('Przybliż')} onClick={onZoomIn} />
        <CtrlButton icon={Minus} label={t('Oddal')} onClick={onZoomOut} />
        <CtrlButton icon={Crosshair} label={t('Wróć do mojej działki')} onClick={onBackToParcel} disabled={!canGoBack} />
        <CtrlButton icon={LocateFixed} label={t('Moja lokalizacja')} onClick={onLocate} />
      </div>
    </div>
  )
}
