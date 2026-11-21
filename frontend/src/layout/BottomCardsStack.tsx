import type { BottomCardsProps } from './cards/types'
import { ForecastCard } from '@/features/weather/ForecastCard'
import { TimelineCard } from '@/features/timeline/TimelineCard'
import { AlertsCard } from './cards/AlertsCard'
import { BalanceCard } from './cards/BalanceCard'
import { FarmCard } from './cards/FarmCard'
import { useLang } from '@/lib/i18n'

/** Karty dolnego paska ułożone pionowo – w pełnej szufladzie na telefonie (SPEC 12). */
export function BottomCardsStack(props: BottomCardsProps) {
  const { t } = useLang()
  return (
    <section className="space-y-3 border-t pt-5">
      <h3 className="text-lg leading-6 font-semibold">{t('Gospodarstwo i pogoda')}</h3>
      <div className="h-[224px]">
        <ForecastCard
          forecast={props.forecast}
          loading={props.forecastLoading}
          error={props.forecastError}
          where={props.where}
          historical={props.historical}
        />
      </div>
      <div className="h-[140px]">
        <FarmCard saved={props.saved} />
      </div>
      <div className="h-[140px]">
        <BalanceCard analysis={props.analysis} />
      </div>
      <div className="h-[140px]">
        <AlertsCard analysis={props.analysis} />
      </div>
      <div className="h-[156px]">
        <TimelineCard updated={props.updated} analysis={props.analysis} asOf={props.asOf} onAsOfChange={props.onAsOfChange} />
      </div>
    </section>
  )
}
