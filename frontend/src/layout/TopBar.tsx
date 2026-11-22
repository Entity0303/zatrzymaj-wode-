import type { ReactNode } from 'react'
import { DateField } from '@/components/DateField'
import { LanguageToggle } from '@/components/LanguageToggle'

/**
 * Górny pasek nad mapą – JEDEN wiersz (przeprojektowanie ekranu mapy): po lewej wyszukiwarka
 * (z „Moja lokalizacja” w środku pola), po prawej data analizy (pełna, nigdy ucięta), pogoda (znika,
 * gdy niedostępna) i język. Bez „Wróć do mapy” – działkę zamyka ✕ w jej panelu.
 * Warstwy mapy są w osobnym przycisku „Warstwa: …” (LayerMenu), nie w pasku.
 */
export function TopBar({
  isMobile,
  search,
  weather,
  asOf,
  onAsOfChange,
  layerButton,
  period,
}: {
  /** F3: przycisk „Okres” (PeriodPicker) obok daty */
  period?: ReactNode
  isMobile: boolean
  /** <SearchBar trailing={<LocateButton inField />} /> */
  search: ReactNode
  /** <WeatherWidget bare /> – null, gdy pogody brak */
  weather: ReactNode
  asOf: string
  onAsOfChange: (v: string) => void
  /** telefon: przycisk warstw pod wyszukiwarką */
  layerButton?: ReactNode
}) {
  if (isMobile)
    return (
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[1200] space-y-2 px-3 pt-3">
        <div className="pointer-events-auto flex items-start gap-2">
          {search}
          <LanguageToggle compact />
        </div>
        {layerButton && <div className="pointer-events-auto w-fit">{layerButton}</div>}
      </div>
    )
  return (
    <div className="pointer-events-none absolute inset-x-4 top-4 z-[1200] flex items-start gap-3 [&>*]:pointer-events-auto">
      {search}
      {/* data · pogoda · język – jedna pigułka; elementy bez danych znikają */}
      <div className="glass ml-auto flex h-12 shrink-0 items-center divide-x divide-line rounded-full pr-1 shadow-float">
        <DateField value={asOf} onChange={onAsOfChange} bare />
        {period && <div className="px-1">{period}</div>}
        {weather}
        <LanguageToggle compact className="ml-1 size-10 bg-transparent shadow-none" />
      </div>
    </div>
  )
}
