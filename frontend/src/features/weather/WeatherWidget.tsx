import type { Forecast } from '@/api/types'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { WeatherIcon } from './WeatherIcon'
import { useLang } from '@/lib/i18n'

/** Pogoda teraz (SPEC 4.2, 14): ikona, temperatura, opis – Open-Meteo dla działki lub środka mapy. */
export function WeatherWidget({
  forecast,
  loading,
  error,
  where,
  compact,
  bare,
}: {
  forecast: Forecast | null
  loading: boolean
  error: boolean
  where: string
  compact?: boolean
  /** bez własnego tła i cienia – w grupie górnego paska */
  bare?: boolean
}) {
  const { t } = useLang()
  const now = forecast?.teraz
  const label = now
    ? t('Pogoda teraz {where}: {temp}, {opis}. Źródło: Open-Meteo.', {
        where,
        temp: now.temperatura === null ? t('brak temperatury') : `${Math.round(now.temperatura)}°C`,
        opis: t(now.opis),
      })
    : t('Pogoda')
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          tabIndex={0}
          aria-label={label}
          className={cn(
            'flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface px-4 shadow-float',
            compact && 'h-11 border px-3 shadow-none',
            bare && 'rounded-none bg-transparent shadow-none',
          )}
        >
          {loading && !now ? (
            <>
              <Skeleton className="size-6 rounded-full bg-surface-2" />
              <Skeleton className="h-4 w-20 bg-surface-2" />
            </>
          ) : error || !now ? (
            <span className="text-sm text-text-muted">{t('Pogoda niedostępna')}</span>
          ) : (
            <>
              <WeatherIcon icon={now.ikona} night={!now.dzien} className="size-6" />
              <span className="tabular text-base font-semibold">
                {now.temperatura === null ? '—' : `${Math.round(now.temperatura)}°C`}
              </span>
              {!compact && <span className="hidden max-w-36 truncate text-sm text-text-muted xl:inline">{t(now.opis)}</span>}
            </>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>{now ? `${t(now.opis)} · ${where} · Open-Meteo` : t('Pogoda z Open-Meteo')}</TooltipContent>
    </Tooltip>
  )
}
