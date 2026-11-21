import { CalendarRange, Sprout } from 'lucide-react'
import type { CropSeason } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatDayMonth, formatNum } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

const DAY = 86_400_000

/**
 * Faza uprawy w dacie analizy (kontrakt `crop_season`): faza, dzień sezonu, pasek siew → zbiór,
 * głębokość korzeni, czy faza jest wrażliwa na brak wody. Terminy to typowy kalendarz w Polsce (D31).
 */
export function CropSeasonCard({ season, analysisDate }: { season: CropSeason; analysisDate: string }) {
  const { t } = useLang()
  const start = Date.parse(`${season.season_start}T12:00:00`)
  const end = Date.parse(`${season.harvest}T12:00:00`)
  const now = Date.parse(`${analysisDate}T12:00:00`)
  const span = end - start
  // położenie daty analizy na pasku sezonu; poza sezonem znacznik nie jest rysowany
  const pos = span > 0 && now >= start && now <= end ? ((now - start) / span) * 100 : null
  const totalDays = span > 0 ? Math.round(span / DAY) + 1 : null

  return (
    <section aria-label={t('Faza uprawy')} className="rounded-xl border bg-surface p-3.5">
      <div className="flex items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-ok-soft text-brand">
          <Sprout className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-5 text-text-muted">{t('Faza uprawy')}</p>
          <p className="text-base leading-6 font-semibold first-letter:uppercase">{t(season.phase_label)}</p>
        </div>
        <span
          className={cn(
            'shrink-0 rounded-full px-2 py-0.5 text-xs leading-4 font-medium',
            season.sensitive ? 'bg-warn-soft text-[#8a6a00]' : 'bg-surface-2 text-text-muted',
          )}
        >
          {t(season.sensitive ? 'wrażliwa na brak wody' : 'mało wrażliwa')}
        </span>
      </div>

      <div className="mt-3">
        <div className="relative h-1.5 rounded-full bg-surface-2" aria-hidden>
          {pos !== null && (
            <>
              <div className="h-full rounded-full bg-ok" style={{ width: `${pos}%` }} />
              <span
                className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-brand"
                style={{ left: `${pos}%` }}
              />
            </>
          )}
        </div>
        <div className="mt-1.5 flex justify-between gap-2 text-xs leading-4 text-text-muted">
          <span className="flex items-center gap-1">
            <CalendarRange className="size-3.5" aria-hidden />
            {t('start {d}', { d: formatDayMonth(season.season_start) })}
          </span>
          <span className="tabular">
            {season.day_of_season != null && totalDays
              ? t('dzień {n} z {total}', { n: season.day_of_season, total: totalDays })
              : t('poza sezonem')}
          </span>
          <span>{t('zbiór ok. {d}', { d: formatDayMonth(season.harvest) })}</span>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm leading-5 text-text-muted">
          {season.root_depth_m != null
            ? t('Korzenie sięgają ok. {m} m', { m: formatNum(season.root_depth_m, 1) })
            : t('Korzenie: brak danych')}
        </span>
        <SourceTag kind="szacunek_modelu" title={t('Typowy kalendarz upraw w Polsce i fazy FAO-56')} />
      </div>
    </section>
  )
}
