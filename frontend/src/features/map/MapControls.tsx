import { Crosshair, Map as MapIcon, Minus, Plus, Satellite, type LucideIcon } from 'lucide-react'
import type { CSSProperties } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { BaseMap } from './ParcelMap'
import { useLang } from '@/lib/i18n'

// MapControls (przeprojektowanie): jedna pionowa grupa w prawym dolnym rogu, nad atrybucją –
// rodzaj mapy, przybliż, oddal, wróć do działki. Każdy przycisk 44 × 44 px (cel dotyku).

function CtrlButton({ icon: Icon, label, onClick, tip }: { icon: LucideIcon; label: string; onClick: () => void; tip?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          onClick={onClick}
          className="flex size-11 items-center justify-center text-text transition-colors hover:bg-ok-soft hover:text-brand"
        >
          <Icon className="size-5" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">{tip ?? label}</TooltipContent>
    </Tooltip>
  )
}

export function MapControls({
  onZoomIn,
  onZoomOut,
  onBackToParcel,
  canGoBack,
  baseMap,
  onBaseMapChange,
  className,
  style,
  horizontal,
}: {
  /** komputer: jeden rząd w prawym dolnym rogu */
  horizontal?: boolean
  onZoomIn: () => void
  onZoomOut: () => void
  onBackToParcel: () => void
  /** „Moja lokalizacja” jest w polu wyszukiwania – tu bez duplikatu (zostaje dla zgodności wywołań) */
  onLocate?: () => void
  canGoBack: boolean
  baseMap: BaseMap
  onBaseMapChange: (b: BaseMap) => void
  className?: string
  style?: CSSProperties
}) {
  const { t } = useLang()
  // ikona pokazuje, NA CO się przełączy
  const next: BaseMap = baseMap === 'orto' ? 'osm' : 'orto'
  return (
    <div
      className={cn('glass flex overflow-hidden rounded-xl shadow-float', horizontal ? 'flex-row divide-x divide-line' : 'flex-col divide-y divide-line', className)}
      style={style}
    >
      <CtrlButton
        icon={next === 'osm' ? MapIcon : Satellite}
        label={t('Zmień rodzaj mapy na: {name}', { name: t(next === 'osm' ? 'Mapa' : 'Zdjęcie') })}
        tip={t(next === 'osm' ? 'Pokaż zwykłą mapę z drogami i nazwami' : 'Pokaż zdjęcie lotnicze (ortofotomapa)')}
        onClick={() => onBaseMapChange(next)}
      />
      <CtrlButton icon={Plus} label={t('Przybliż')} onClick={onZoomIn} />
      <CtrlButton icon={Minus} label={t('Oddal')} onClick={onZoomOut} />
      {canGoBack && <CtrlButton icon={Crosshair} label={t('Wróć do mojej działki')} onClick={onBackToParcel} />}
    </div>
  )
}
