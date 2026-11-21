import type { Forecast } from '@/api/types'
import { ForecastCard } from '@/features/weather/ForecastCard'
import { TimelineCard } from '@/features/timeline/TimelineCard'
import { cn } from '@/lib/utils'
import { AlertsCard } from './cards/AlertsCard'
import { BalanceCard } from './cards/BalanceCard'
import { FarmCard } from './cards/FarmCard'

/**
 * Dolny pasek 5 kart (SPEC 4.5) – jak na ref-desktop: jedna biała karta, sekcje dzielone linią 1 px.
 * Na tablecie przewijany poziomo, sekcje po 260 px (SPEC 12).
 */
export function BottomCards(props: {
  savedCount: number
  forecast: Forecast | null
  forecastLoading: boolean
  forecastError: boolean
  where: string
  historical: boolean
  updated: string | null
}) {
  const item = 'h-full w-[260px] shrink-0 xl:w-auto xl:min-w-0 xl:flex-1'
  return (
    <div
      className={cn(
        'scrollbar-none flex h-full divide-x divide-line overflow-x-auto rounded-xl bg-surface shadow-float',
        // karty-sekcje bez własnej ramki, tła i cienia
        '[&>div>section]:rounded-none [&>div>section]:border-0 [&>div>section]:bg-transparent [&>div>section]:px-5 [&>div>section]:shadow-none',
      )}
    >
      <div className={item}>
        <FarmCard savedCount={props.savedCount} />
      </div>
      <div className={item}>
        <BalanceCard />
      </div>
      <div className={item}>
        <AlertsCard />
      </div>
      <div className={cn(item, 'w-[420px] xl:flex-[2]')}>
        <ForecastCard
          forecast={props.forecast}
          loading={props.forecastLoading}
          error={props.forecastError}
          where={props.where}
          historical={props.historical}
        />
      </div>
      <div className={item}>
        <TimelineCard updated={props.updated} />
      </div>
    </div>
  )
}
