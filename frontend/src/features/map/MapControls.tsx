import { Check, Crosshair, Map as MapIcon, Minus, Plus, Satellite, Sprout, type LucideIcon } from 'lucide-react'
import type { CSSProperties } from 'react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { BaseMap } from './ParcelMap'
import { SOIL_ZOOM_HINT, soilLayerInRange } from './SoilSusceptibilityLayer'
import { useLang } from '@/lib/i18n'

// MapControls (przeprojektowanie): jedna pionowa grupa w prawym dolnym rogu, nad atrybucją –
// podkład i nakładki (menu: zdjęcie / mapa + „Podatność gleb na suszę”, SPEC 5.1, F7), przybliż, oddal,
// wróć do działki. Każdy przycisk 44 × 44 px (cel dotyku).

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

const BASE_MAPS: { key: BaseMap; icon: LucideIcon; label: string; hint: string }[] = [
  { key: 'orto', icon: Satellite, label: 'Zdjęcie lotnicze', hint: 'Ortofotomapa GUGiK' },
  { key: 'osm', icon: MapIcon, label: 'Mapa', hint: 'Drogi i nazwy miejscowości' },
]

/** „Mały przycisk warstw podkładu w rogu mapy” (SPEC 5.1): podkład + nakładka gleb IUNG (domyślnie wyłączona, F7). */
function BaseMapMenu({
  baseMap,
  onBaseMapChange,
  soilOn,
  onSoilChange,
  soilInRange,
}: {
  baseMap: BaseMap
  onBaseMapChange: (b: BaseMap) => void
  soilOn: boolean
  onSoilChange?: (on: boolean) => void
  soilInRange: boolean
}) {
  const { t } = useLang()
  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={t('Podkład i nakładki mapy')}
              className="flex size-11 items-center justify-center text-text transition-colors hover:bg-ok-soft hover:text-brand data-[state=open]:bg-ok-soft data-[state=open]:text-brand"
            >
              <MapIcon className="size-5" aria-hidden />
            </button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent side="top">{t('Podkład i nakładki mapy')}</TooltipContent>
      </Tooltip>
      <DropdownMenuContent side="top" align="end" sideOffset={8} className="z-[1700] w-80 rounded-xl p-1.5">
        <DropdownMenuLabel className="px-2.5 pt-1.5 pb-1 text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Podkład')}</DropdownMenuLabel>
        {BASE_MAPS.map((b) => {
          const Icon = b.icon
          const on = b.key === baseMap
          return (
            <DropdownMenuItem
              key={b.key}
              role="menuitemradio"
              aria-checked={on}
              onSelect={() => onBaseMapChange(b.key)}
              className={cn('min-h-12 items-start gap-3 rounded-lg px-2.5 py-2', on && 'bg-sage-soft')}
            >
              <Icon className={cn('mt-0.5 size-5 shrink-0', on ? 'text-brand' : 'text-text-muted')} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-sm leading-5 font-semibold">{t(b.label)}</span>
                <span className="block text-sm leading-5 text-text-muted">{t(b.hint)}</span>
              </span>
              {on && <Check className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />}
            </DropdownMenuItem>
          )
        })}
        {onSoilChange && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="px-2.5 pt-1.5 pb-1 text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Nakładki')}</DropdownMenuLabel>
            <DropdownMenuItem
              role="menuitemcheckbox"
              aria-checked={soilOn}
              // menu zostaje otwarte – widać, że przełącznik zadziałał
              onSelect={(e) => {
                e.preventDefault()
                onSoilChange(!soilOn)
              }}
              className="min-h-14 items-start gap-3 rounded-lg px-2.5 py-2"
            >
              <Sprout className={cn('mt-0.5 size-5 shrink-0', soilOn ? 'text-brand' : 'text-text-muted')} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-sm leading-5 font-semibold">{t('Podatność gleb na suszę')}</span>
                <span className="block text-sm leading-5 text-text-muted">
                  {soilInRange ? t('Mapa IUNG-PIB – kategorie I–IV') : t(SOIL_ZOOM_HINT)}
                </span>
              </span>
              {/* przełącznik (wizualnie) – stan dla czytnika ekranu w aria-checked */}
              <span
                aria-hidden
                className={cn('mt-0.5 flex h-6 w-10 shrink-0 items-center rounded-full p-0.5 transition-colors', soilOn ? 'bg-brand' : 'bg-line')}
              >
                <span className={cn('size-5 rounded-full bg-surface shadow-sm transition-transform', soilOn && 'translate-x-4')} />
              </span>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function MapControls({
  onZoomIn,
  onZoomOut,
  onBackToParcel,
  canGoBack,
  baseMap,
  onBaseMapChange,
  soilOn = false,
  onSoilChange,
  zoom,
  className,
  style,
  horizontal,
}: {
  /** nakładka „Podatność gleb na suszę” (IUNG) – przełącznik w menu podkładu */
  soilOn?: boolean
  onSoilChange?: (on: boolean) => void
  /** bieżące przybliżenie mapy (po zakończeniu ruchu) – podpowiedź „Przybliż mapę…” */
  zoom?: number
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
  return (
    <div
      className={cn('glass flex overflow-hidden rounded-xl shadow-float', horizontal ? 'flex-row divide-x divide-line' : 'flex-col divide-y divide-line', className)}
      style={style}
    >
      <BaseMapMenu
        baseMap={baseMap}
        onBaseMapChange={onBaseMapChange}
        soilOn={soilOn}
        onSoilChange={onSoilChange}
        soilInRange={zoom == null || soilLayerInRange(zoom)}
      />
      <CtrlButton icon={Plus} label={t('Przybliż')} onClick={onZoomIn} />
      <CtrlButton icon={Minus} label={t('Oddal')} onClick={onZoomOut} />
      {canGoBack && <CtrlButton icon={Crosshair} label={t('Wróć do mojej działki')} onClick={onBackToParcel} />}
    </div>
  )
}
