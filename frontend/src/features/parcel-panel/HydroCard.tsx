import { ArrowDownRight, Droplets, Gauge, Loader2 } from 'lucide-react'
import type { Hydro, HydroGauge } from '@/api/types'
import { formatDistance, HYDRO_KIND } from '@/lib/hydro'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, formatNum } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const GAUGE: Record<HydroGauge['state'], { label: string; cls: string }> = {
  niski: { label: 'stan niski', cls: 'bg-warn-soft text-[#875a12]' },
  sredni: { label: 'stan średni', cls: 'bg-ok-soft text-brand' },
  wysoki: { label: 'stan wysoki', cls: 'bg-water-soft text-[#1d5d96]' },
}

/**
 * „Woda w okolicy” (F3, analysis.hydro): jedno zdanie, 3 najbliższe obiekty (rodzaj, nazwa, odległość,
 * czy w stronę odpływu wody z działki) i najbliższy wodowskaz ze stanem. `pending` – „Sprawdzam wodę w okolicy…”
 * (dociąga useAnalysis); brak sekcji w odpowiedzi – karty nie ma.
 */
export function HydroCard({ hydro: h, passport }: { hydro?: Hydro | null; passport?: boolean }) {
  const { t } = useLang()
  if (!h) return null
  const box = cn('space-y-2.5 rounded-xl bg-surface', passport ? 'p-4 shadow-card' : 'border p-3.5')
  const head = (
    <div className="flex items-center gap-2">
      <Droplets className="size-5 shrink-0 text-water" aria-hidden />
      <h4 className={cn('min-w-0 flex-1 font-semibold', passport ? 'text-lg leading-7' : 'text-base leading-6')}>{t('Woda w okolicy')}</h4>
    </div>
  )
  if (h.status === 'pending')
    return (
      <section aria-label={t('Woda w okolicy')} aria-busy className={box}>
        {head}
        <p className="flex items-center gap-2 text-sm leading-5 text-text-muted" role="status">
          <Loader2 className="size-4 animate-spin text-brand" aria-hidden /> {t('Sprawdzam wodę w okolicy…')}
        </p>
      </section>
    )
  const near = [...(h.features ?? [])].sort((a, b) => a.distance_m - b.distance_m).slice(0, 3)
  const g = h.gauge
  return (
    <section aria-label={t('Woda w okolicy')} className={box}>
      {head}
      {h.sentence && <p className={cn(passport ? 'text-base leading-6' : 'text-sm leading-5')}>{t(h.sentence)}</p>}
      {h.status === 'none' && !h.sentence && <p className="text-sm leading-5 text-text-muted">{t('W pobliżu działki nie ma rzek, rowów ani stawów.')}</p>}
      {near.length > 0 && (
        <ul className="space-y-1.5">
          {near.map((f, i) => (
            <li key={`${f.kind}-${i}`} className="flex items-start gap-2 text-sm leading-5">
              <span className="mt-1.5 size-2 shrink-0 rounded-full bg-water" aria-hidden />
              <span className="min-w-0 flex-1">
                <b className="font-semibold">{t(HYDRO_KIND[f.kind])}</b>
                {f.name && <span> {f.name}</span>}
                {f.toward_outflow && (
                  <span className="mt-0.5 flex items-center gap-1 text-xs leading-4 text-text-muted">
                    <ArrowDownRight className="size-3.5 text-water" aria-hidden /> {t('w stronę, w którą woda spływa z działki')}
                  </span>
                )}
              </span>
              <span className="tabular shrink-0 font-medium">{formatDistance(f.distance_m)}</span>
            </li>
          ))}
        </ul>
      )}
      {g && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg bg-surface-2/70 px-3 py-2 text-sm leading-5">
          <Gauge className="size-4 shrink-0 text-water" aria-hidden />
          <span className="min-w-0">
            {t('Wodowskaz {name} ({river}) · {km}', { name: g.name, river: g.river, km: `${formatNum(g.distance_km, 0)} km` })}
          </span>
          <span className={cn('rounded-full px-2 py-0.5 text-xs leading-4 font-medium', GAUGE[g.state].cls)}>{t(GAUGE[g.state].label)}</span>
          <span className="tabular text-text-muted">
            {formatNum(g.level_cm, 0)} cm · {formatDatePl(g.date)}
          </span>
        </div>
      )}
      {(h.sources ?? []).length > 0 && (
        <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs leading-4 text-text-muted">
          <SourceTag kind="pomiar" />
          {(h.sources ?? []).map((s, i) => (
            <span key={s.name}>
              {i > 0 && '· '}
              <a href={s.url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                {s.name}
              </a>
            </span>
          ))}
        </p>
      )}
    </section>
  )
}
