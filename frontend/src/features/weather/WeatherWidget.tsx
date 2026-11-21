import type { Forecast } from '@/api/types'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { WeatherIcon } from './WeatherIcon'

/** Pogoda teraz (SPEC 4.2, 14): ikona, temperatura, opis – Open-Meteo dla działki lub środka mapy. */
export function WeatherWidget({
  forecast,
  loading,
  error,
  where,
  compact,
}: {
  forecast: Forecast | null
  loading: boolean
  error: boolean
  where: string
  compact?: boolean
}) {
  const now = forecast?.teraz
  const label = now
    ? `Pogoda teraz ${where}: ${now.temperatura === null ? 'brak temperatury' : `${Math.round(now.temperatura)}°C`}, ${now.opis}. Źródło: Open-Meteo.`
    : 'Pogoda'
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          tabIndex={0}
          aria-label={label}
          className={cn(
            'flex h-12 shrink-0 items-center gap-2 rounded-full border bg-surface px-4 shadow-float',
            compact && 'h-11 px-3 shadow-none',
          )}
        >
          {loading && !now ? (
            <>
              <Skeleton className="size-6 rounded-full bg-surface-2" />
              <Skeleton className="h-4 w-20 bg-surface-2" />
            </>
          ) : error || !now ? (
            <span className="text-sm text-text-muted">Pogoda niedostępna</span>
          ) : (
            <>
              <WeatherIcon icon={now.ikona} night={!now.dzien} className="size-6" />
              <span className="tabular text-base font-semibold">
                {now.temperatura === null ? '—' : `${Math.round(now.temperatura)}°C`}
              </span>
              {!compact && <span className="hidden max-w-36 truncate text-sm text-text-muted xl:inline">{now.opis}</span>}
            </>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>{now ? `${now.opis} · ${where} · Open-Meteo` : 'Pogoda z Open-Meteo'}</TooltipContent>
    </Tooltip>
  )
}
