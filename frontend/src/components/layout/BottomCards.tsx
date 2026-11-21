import { Bell, CalendarRange, ChartNoAxesCombined, CloudSun, Tractor, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Forecast } from '@/api'
import { WeatherIcon } from '@/components/common/Art'
import { SourceTag } from '@/components/common/SourceTag'
import { Skeleton } from '@/components/ui/skeleton'
import { formatNum, formatSigned, weekdayShort } from '@/lib/format'
import { cn } from '@/lib/utils'

function Card({
  icon: Icon,
  title,
  children,
  className,
  aside,
}: {
  icon: LucideIcon
  title: string
  children: ReactNode
  className?: string
  aside?: ReactNode
}) {
  return (
    <section
      aria-label={title}
      className={cn('flex h-full min-w-0 flex-col rounded-xl border bg-surface px-4 py-3 shadow-card', className)}
    >
      <header className="mb-1.5 flex items-center gap-2">
        <Icon className="size-5 text-brand" aria-hidden />
        <h3 className="text-sm leading-5 font-semibold">{title}</h3>
        {aside && <span className="ml-auto">{aside}</span>}
      </header>
      {children}
    </section>
  )
}

function NoData({ text = 'Brak danych – analiza w budowie' }: { text?: string }) {
  return (
    <div className="hatch-nodata flex flex-1 flex-col items-start justify-center gap-1.5 rounded-lg px-3 py-2">
      <p className="text-sm leading-5 text-text-muted">{text}</p>
      <SourceTag kind="brak" />
    </div>
  )
}

export function FarmCard({ savedCount }: { savedCount: number }) {
  return (
    <Card icon={Tractor} title="Gospodarstwo">
      <div className="flex items-baseline gap-2">
        <span className="tabular text-[32px] leading-10 font-semibold">{savedCount}</span>
        <span className="text-sm text-text-muted">
          {savedCount === 1 ? 'zapisana działka' : savedCount >= 2 && savedCount <= 4 ? 'zapisane działki' : 'zapisanych działek'}
        </span>
      </div>
      <p className="mt-auto text-sm leading-5 text-text-muted">
        {savedCount ? 'Stan działek: brak danych – analiza w budowie' : 'Zapisz działkę gwiazdką w panelu działki'}
      </p>
    </Card>
  )
}

export function BalanceCard() {
  return (
    <Card icon={ChartNoAxesCombined} title="Bilans wody">
      <NoData />
    </Card>
  )
}

export function AlertsCard() {
  return (
    <Card icon={Bell} title="Alerty">
      <NoData text="Alerty pojawią się po analizie (w budowie)" />
    </Card>
  )
}

export function ForecastCard({
  forecast,
  loading,
  error,
  where,
  historical,
  className,
}: {
  forecast: Forecast | null
  loading: boolean
  error: boolean
  where: string
  historical: boolean
  className?: string
}) {
  const days = forecast?.dni.slice(0, 7) ?? []
  return (
    <Card
      icon={CloudSun}
      title="Prognoza 7 dni"
      className={className}
      aside={
        forecast && !historical ? (
          <span className="text-xs text-text-muted">
            <span className="max-sm:hidden">{where} · </span>mm: <span className="text-water">opad</span> /{' '}
            <span className="text-earth">parowanie</span>
          </span>
        ) : undefined
      }
    >
      {historical ? (
        <NoData text="Prognoza dotyczy dni od dziś – dla analizy historycznej jej nie pokazujemy" />
      ) : loading && !forecast ? (
        <div className="flex flex-1 gap-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-full flex-1 bg-surface-2" />
          ))}
        </div>
      ) : error || !forecast ? (
        <NoData text="Prognoza niedostępna (Open-Meteo nie odpowiada)" />
      ) : (
        <>
          <ol className="grid flex-1 grid-cols-7 gap-0.5 text-center">
            {days.map((d) => (
              <li key={d.data} className="flex min-w-0 flex-col items-center justify-between" title={`${d.opis} · opad ${d.opad_mm ?? '—'} mm · parowanie ${d.parowanie_mm ?? '—'} mm`}>
                <span className="text-sm leading-[18px] font-medium text-text-muted capitalize">{weekdayShort(d.data)}</span>
                <WeatherIcon icon={d.ikona} className="size-5" />
                <span className="tabular text-sm leading-[18px] font-semibold whitespace-nowrap">
                  {d.temp_max === null ? '—' : Math.round(d.temp_max)}°
                  <span className="max-sm:block max-sm:font-normal max-sm:text-text-muted">
                    <span className="max-sm:hidden">/</span>
                    {d.temp_min === null ? '—' : Math.round(d.temp_min)}°
                  </span>
                </span>
                <span className="tabular text-sm leading-[18px] font-semibold text-water">
                  {d.opad_mm === null ? '—' : formatNum(d.opad_mm)}
                </span>
                <span className="tabular text-sm leading-[18px] text-earth">
                  {d.parowanie_mm === null ? '—' : formatNum(d.parowanie_mm)}
                </span>
              </li>
            ))}
          </ol>
          <div className="mt-1 flex items-center justify-between gap-2 text-xs leading-4">
            <span className="text-sm leading-5 text-text-muted">
              Bilans tygodnia:{' '}
              <b className="tabular text-text">
                {forecast.bilans_okresu_mm === null ? 'brak danych' : `${formatSigned(forecast.bilans_okresu_mm)} mm`}
              </b>
            </span>
            <SourceTag kind="prognoza" title="Open-Meteo, prognoza dobowa; parowanie = ET0 FAO-56" />
          </div>
        </>
      )}
    </Card>
  )
}

export function TimelineCard({ updated }: { updated: string | null }) {
  const months = ['S', 'L', 'M', 'K', 'M', 'C', 'L', 'S', 'W', 'P', 'L', 'G']
  return (
    <Card icon={CalendarRange} title="Oś czasu">
      <div className="flex gap-0.5" aria-label="Stan w kolejnych miesiącach: brak danych">
        {months.map((m, i) => (
          <div key={i} className="flex flex-1 flex-col items-center gap-0.5">
            <span className="hatch-nodata h-5 w-full rounded-sm" />
            <span className="text-[12px] leading-4 text-text-muted">{m}</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-sm leading-5 text-text-muted">Brak danych – analiza w budowie</p>
      <p className="mt-auto text-xs leading-4 text-text-muted">
        Ostatnia aktualizacja danych: {updated ?? '—'}
      </p>
    </Card>
  )
}

/** Dolny pasek 5 kart (SPEC 4.5); na tablecie przewijany poziomo, karty po 260 px (SPEC 12). */
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
    <div className="scrollbar-none flex h-full gap-3 overflow-x-auto xl:overflow-visible">
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
