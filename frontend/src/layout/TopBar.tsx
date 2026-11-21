import type { ReactNode } from 'react'
import { DateField } from '@/components/DateField'
import { LanguageToggle } from '@/components/LanguageToggle'
import { LayerPills } from '@/features/map/LayerPills'
import type { LayerKey } from '@/features/map/layers'
import { ViewToggle } from '@/features/map/ViewToggle'
import { LocateButton } from '@/features/search/LocateButton'

/**
 * Górny pływający pasek (SPEC 4.2, 12): wyszukiwarka, „Moja lokalizacja”, pogoda, data analizy,
 * druga linia – pigułki warstw i 2D|3D. Na telefonie: wyszukiwarka + lokalizacja, pod nimi pigułki.
 */
export function TopBar({
  isMobile,
  search,
  weather,
  locating,
  onLocate,
  asOf,
  onAsOfChange,
  layer,
  onLayerChange,
}: {
  isMobile: boolean
  /** <SearchBar /> – stan wyszukiwania trzyma strona */
  search: ReactNode
  /** <WeatherWidget /> */
  weather: ReactNode
  locating: boolean
  onLocate: () => void
  asOf: string
  onAsOfChange: (v: string) => void
  layer: LayerKey
  onLayerChange: (k: LayerKey) => void
}) {
  if (isMobile)
    return (
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[1200] space-y-2 pt-3">
        <div className="pointer-events-auto flex items-start gap-2 px-3">
          {search}
          <LocateButton locating={locating} onClick={onLocate} iconOnly />
          <LanguageToggle compact />
        </div>
        <LayerPills value={layer} onChange={onLayerChange} className="pointer-events-auto px-3 pb-2" />
      </div>
    )
  return (
    <div className="pointer-events-none absolute inset-x-4 top-4 z-[1200] space-y-3">
      <div className="flex items-start gap-3 [&>*]:pointer-events-auto">
        {search}
        <LocateButton locating={locating} onClick={onLocate} />
        {/* pogoda · data · język – jedna biała pigułka z liniami podziału (ref-desktop) */}
        <div className="ml-auto flex h-12 shrink-0 items-center divide-x divide-line rounded-full bg-surface pr-1 shadow-float">
          {weather}
          <DateField value={asOf} onChange={onAsOfChange} bare />
          <LanguageToggle bare className="pl-2" />
        </div>
      </div>
      <div className="flex max-w-full items-center gap-3 [&>*]:pointer-events-auto">
        <LayerPills value={layer} onChange={onLayerChange} className="min-w-0 py-1" />
        <ViewToggle />
      </div>
    </div>
  )
}
