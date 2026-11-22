import { Droplets } from 'lucide-react'
import type { SoilWaterState } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatNum } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/**
 * Stan wody w glebie (kontrakt `soil_water`) – także poza sezonem: zakres (strefa korzeni / profil),
 * opis, porównanie z tym samym dniem w 10 latach, podsumowanie zakończonego sezonu.
 */
export function SoilWaterCard({ state }: { state: SoilWaterState }) {
  const { t } = useLang()
  const { rank, last_season: last } = state
  return (
    <section aria-label={t('Zapas wody w glebie – szczegóły')} className="rounded-xl border bg-surface p-3.5">
      <div className="flex items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-water-soft text-water">
          <Droplets className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-5 text-text-muted">
            {t(state.scope === 'strefa_korzeni' ? 'Strefa korzeni, ok. {m} m' : 'Cały profil gleby, ok. {m} m', {
              m: formatNum(state.depth_m, 1),
            })}
          </p>
          <p className="text-base leading-6 font-medium first-letter:uppercase">{t(state.description)}</p>
        </div>
      </div>

      {rank && rank.of_years > 0 && (
        <div className="mt-3">
          {/* jeden znacznik = jeden rok; wypełnione = lata, w których tego dnia było MNIEJ wody niż teraz */}
          <div className="flex gap-1" aria-hidden>
            {Array.from({ length: rank.of_years }, (_, i) => (
              <span key={i} className={cn('h-2 flex-1 rounded-full', i < rank.lower_years ? 'bg-water' : 'bg-surface-2')} />
            ))}
          </div>
          <p className="mt-1.5 text-sm leading-5">
            {t('Tego dnia mniej wody było w {n} z {of} ostatnich lat', { n: rank.lower_years, of: rank.of_years })}
          </p>
        </div>
      )}

      {last && (
        <p className="mt-2 text-sm leading-5 text-text-muted">
          {t('Sezon {year}: {days}', {
            year: last.year,
            days: last.stress_days == null ? t('dni stresu – brak danych') : t(last.stress_days === 1 ? '{n} dzień stresu wodnego' : '{n} dni stresu wodnego', { n: last.stress_days }),
          })}
          {last.mean_prev_stress_days != null &&
            ` (${t('średnio {n}', { n: formatNum(last.mean_prev_stress_days, 0) })})`}
        </p>
      )}

      <div className="mt-2.5">
        <SourceTag kind="szacunek_modelu" title={t('Model wody w glebie FAO-56')} />
      </div>
    </section>
  )
}
