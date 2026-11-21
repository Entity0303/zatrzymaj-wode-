import { Crosshair, Map as MapIcon, Minus, Plus, Satellite, type LucideIcon } from 'lucide-react'
import type { CSSProperties } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { BaseMap } from './ParcelMap'
import { useLang } from '@/lib/i18n'

// MapControls: przełącznik rodzaju mapy z podpisem + mała grupa przybliżania (SPEC 5.2, 14).
// Komputer: przyciski 28 px (mniej rzeczy na ekranie); telefon: 44 px (wygodne dla palca).

function CtrlButton({ icon: Icon, label, onClick }: { icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          onClick={onClick}
          className="flex size-11 items-center justify-center bg-surface text-text transition-colors hover:bg-ok-soft hover:text-brand md:size-7"
        >
          <Icon className="size-5 md:size-4" aria-hidden />
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
  canGoBack,
  baseMap,
  onBaseMapChange,
  className,
  style,
}: {
  onZoomIn: () => void
  onZoomOut: () => void
  onBackToParcel: () => void
  /** „Moja lokalizacja” jest w górnym pasku – tu bez duplikatu (zostaje dla zgodności wywołań) */
  onLocate?: () => void
  canGoBack: boolean
  baseMap: BaseMap
  onBaseMapChange: (b: BaseMap) => void
  className?: string
  style?: CSSProperties
}) {
  const { t } = useLang()
  // przycisk pokazuje, NA CO się przełączy – zrozumiałe bez znajomości ikon
  const next: BaseMap = baseMap === 'orto' ? 'osm' : 'orto'
  const NextIcon = next === 'osm' ? MapIcon : Satellite
  const nextLabel = next === 'osm' ? 'Mapa' : 'Satelita'
  return (
    <div className={cn('flex flex-col items-start gap-2', className)} style={style}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={() => onBaseMapChange(next)}
            aria-label={t('Zmień rodzaj mapy na: {name}', { name: t(nextLabel) })}
            className="flex h-11 items-center gap-1.5 rounded-full bg-surface pr-3 pl-2.5 text-sm font-semibold shadow-float hover:bg-sage-soft md:h-9"
          >
            <NextIcon className="size-4 text-brand" aria-hidden />
            {t(nextLabel)}
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">
          {t(next === 'osm' ? 'Pokaż zwykłą mapę z drogami i nazwami' : 'Pokaż zdjęcie satelitarne (ortofotomapa)')}
        </TooltipContent>
      </Tooltip>
      <div className="flex flex-col divide-y divide-line overflow-hidden rounded-md shadow-float">
        <CtrlButton icon={Plus} label={t('Przybliż')} onClick={onZoomIn} />
        <CtrlButton icon={Minus} label={t('Oddal')} onClick={onZoomOut} />
        {canGoBack && <CtrlButton icon={Crosshair} label={t('Wróć do mojej działki')} onClick={onBackToParcel} />}
      </div>
    </div>
  )
}
