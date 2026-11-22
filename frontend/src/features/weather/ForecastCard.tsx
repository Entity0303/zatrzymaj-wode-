import { CloudSun } from 'lucide-react'
import type { Forecast } from '@/api/types'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { NoDataNote as NoData } from '@/components/NoDataNote'
import { SourceTag } from '@/components/SourceTag'
import { Skeleton } from '@/components/ui/skeleton'
import { formatNum, formatSigned, weekdayShort } from '@/lib/format'
import { WeatherIcon } from './WeatherIcon'
import { useLang } from '@/lib/i18n'

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
  const { t } = useLang()
  const days = forecast?.dni.slice(0, 7) ?? []
  return (
    <Card
      icon={CloudSun}
      title="Prognoza 7 dni"
      className={className}
      aside={
        forecast && !historical ? (
          <span className="text-xs text-text-muted">
            <span className="max-sm:hidden">{where} · </span>mm: <span className="text-water">{t('opad')}</span> /{' '}
            <span className="text-earth">{t('parowanie')}</span>
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
        <NoData text="Prognoza chwilowo niedostępna – spróbujemy ponownie po wybraniu działki" />
      ) : (
        <>
          <ol className="grid flex-1 grid-cols-7 gap-0.5 text-center">
            {days.map((d) => (
              <li key={d.data} className="flex min-w-0 flex-col items-center justify-between" title={t('{opis} · opad {opad} mm · parowanie {par} mm', { opis: t(d.opis), opad: d.opad_mm ?? '—', par: d.parowanie_mm ?? '—' })}>
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
              {t('Woda w tym tygodniu (spadnie minus wyparuje):')}{' '}
              <b className="tabular text-text">
                {forecast.bilans_okresu_mm === null ? t('brak danych') : `${formatSigned(forecast.bilans_okresu_mm)} mm`}
              </b>
            </span>
            <SourceTag kind="prognoza" title={t('Open-Meteo, prognoza dobowa; parowanie = ET0 FAO-56')} />
          </div>
        </>
      )}
    </Card>
  )
}
