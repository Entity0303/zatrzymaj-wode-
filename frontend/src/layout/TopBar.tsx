import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { useLang } from '@/lib/i18n'
import { DateField } from '@/components/DateField'
import { LanguageToggle } from '@/components/LanguageToggle'
import { LayerPills } from '@/features/map/LayerPills'
import type { LayerKey } from '@/features/map/layers'
import { LocateButton } from '@/features/search/LocateButton'

/**
 * Górny pływający pasek (SPEC 4.2, 12): wyszukiwarka, „Moja lokalizacja”, pogoda, data analizy,
 * druga linia – pigułki warstw i 2D|3D. Na telefonie: wyszukiwarka + lokalizacja, pod nimi pigułki.
 */
export function TopBar({
  onBack,
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
  /** wraca do przeglądania mapy (zamyka działkę) */
  onBack?: () => void
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
  const { t } = useLang()
  if (isMobile)
    return (
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[1200] space-y-2 pt-3">
        <div className="pointer-events-auto flex items-start gap-2 px-3">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              aria-label={t('Wróć do mapy')}
              className="flex size-12 shrink-0 items-center justify-center rounded-full bg-surface shadow-float hover:bg-sage-soft"
            >
              <ArrowLeft className="size-5" />
            </button>
          )}
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
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface pr-4 pl-3 text-sm font-semibold shadow-float hover:bg-sage-soft"
          >
            <ArrowLeft className="size-5 text-brand" /> {t('Wróć do mapy')}
          </button>
        )}
        {search}
        <LocateButton locating={locating} onClick={onLocate} />
        {/* pogoda · data · język – jedna biała pigułka z liniami podziału (ref-desktop) */}
        <div className="ml-auto flex h-12 shrink-0 items-center divide-x divide-line rounded-full bg-surface pr-1 shadow-float">
          {weather}
          <DateField value={asOf} onChange={onAsOfChange} bare />
          <LanguageToggle compact className="ml-1 size-10 bg-transparent shadow-none" />
        </div>
      </div>
      <div className="flex max-w-full items-center gap-3 [&>*]:pointer-events-auto">
        <LayerPills value={layer} onChange={onLayerChange} className="min-w-0 py-1" />
      </div>
    </div>
  )
}
