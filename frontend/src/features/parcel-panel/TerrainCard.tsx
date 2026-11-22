import { ChevronDown, Loader2, Mountain } from 'lucide-react'
import { useState } from 'react'
import type { Terrain, TerrainPending, TerrainRating } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, formatNum } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

const RATING: Record<TerrainRating, { label: string; dot: string }> = {
  dobrze: { label: 'dobrze', dot: 'bg-ok' },
  uwaga: { label: 'uwaga', dot: 'bg-warn' },
  zle: { label: 'źle', dot: 'bg-danger' },
}

/**
 * Teren działki z NMT (kontrakt A6): pasek stref (górka → stok → płasko → dołek, szerokość = udział,
 * kolor z odpowiedzi – ten sam co na mapie), podsumowanie, zdania o strefach z oceną,
 * „Dla dociekliwych” – szczegóły metody. Brak terenu → `terrain_note` szarym tekstem.
 */
export function TerrainCard({
  terrain: input,
  note,
  bare,
}: {
  terrain: Terrain | TerrainPending | null | undefined
  note?: string | null
  /** F6: bez własnej ramki i tła – wewnątrz karty paszportu */
  bare?: boolean
}) {
  const { t } = useLang()
  const [open, setOpen] = useState(false)

  // F3: teren liczony w tle (analysis.terrain = { status: 'pending' }) – dociąga go useAnalysis
  if (input && 'status' in input && input.status === 'pending')
    return (
      <section aria-label={t('Teren działki')} aria-busy className={bare ? '' : 'rounded-xl border bg-surface p-3.5'}>
        <p className="flex items-center gap-2 text-sm font-medium">
          <Mountain className="size-4 text-earth" aria-hidden /> {t('Teren działki')}
        </p>
        <p className="mt-1 flex items-center gap-2 text-sm leading-5 text-text-muted" role="status">
          <Loader2 className="size-4 animate-spin text-brand" aria-hidden /> {t('Liczę teren i spływ… (do ok. minuty)')}
        </p>
      </section>
    )
  const terrain = input && 'zones' in input ? input : null

  if (!terrain)
    return (
      <section aria-label={t('Teren działki')} className={bare ? '' : 'hatch-nodata rounded-xl border p-3.5'}>
        <p className="flex items-center gap-2 text-sm font-medium">
          <Mountain className="size-4 text-earth" aria-hidden /> {t('Teren działki')}
        </p>
        <p className="mt-1 text-sm leading-5 text-text-muted">{t(note && !/HTTP|\b\d{3}\b/.test(note) ? note : 'Brak danych o terenie – spróbuj za chwilę')}</p>
      </section>
    )

  const zones = terrain.zones.filter((z) => z.share_pct > 0)
  const d = terrain.details
  return (
    <section aria-label={t('Teren działki')} className={bare ? '' : 'rounded-xl border bg-surface p-3.5'}>
      <div className="flex items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-earth">
          <Mountain className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-base leading-6 font-semibold">{t('Teren działki')}</p>
          {terrain.relief_m != null && (
            <p className="text-sm leading-5 text-text-muted">
              {t('Różnica wysokości {m} m', { m: formatNum(terrain.relief_m, 1) })}
              {terrain.slope_max_pct != null && ` · ${t('największy spadek {p}%', { p: formatNum(terrain.slope_max_pct, 0) })}`}
            </p>
          )}
        </div>
      </div>

      {/* pasek stref – kolejność i kolory z odpowiedzi */}
      <div className="mt-3 flex h-7 overflow-hidden rounded-lg" role="img" aria-label={zones.map((z) => `${t(z.label)} ${Math.round(z.share_pct)}%`).join(', ')}>
        {zones.map((z) => (
          <span
            key={z.key}
            className="flex min-w-0 items-center justify-center text-xs font-semibold text-white [text-shadow:0_1px_2px_rgb(0_0_0/0.35)]"
            style={{ width: `${z.share_pct}%`, background: z.color }}
            title={`${t(z.label)} · ${Math.round(z.share_pct)}%`}
          >
            {z.share_pct >= 9 ? `${Math.round(z.share_pct)}%` : ''}
          </span>
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs leading-4 text-text-muted">
        {zones.map((z) => (
          <li key={z.key} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: z.color }} aria-hidden />
            {t(z.label)}
          </li>
        ))}
      </ul>

      <p className="mt-3 text-sm leading-5">{t(terrain.summary)}</p>

      {zones.some((z) => z.sentence) && (
        <ul className="mt-2 space-y-1.5">
          {zones
            .filter((z) => z.sentence)
            .map((z) => (
              <li key={z.key} className="flex gap-2 text-sm leading-5">
                <span className={cn('mt-1.5 size-2.5 shrink-0 rounded-full', z.rating ? RATING[z.rating].dot : 'bg-nodata')} aria-hidden />
                <span>
                  {t(z.sentence!)}
                  {z.rating && <span className="sr-only"> ({t(RATING[z.rating].label)})</span>}
                </span>
              </li>
            ))}
        </ul>
      )}

      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="mt-2 inline-flex min-h-11 items-center gap-1 text-sm font-medium text-brand hover:underline"
      >
        {t('Dla dociekliwych')} <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-lg bg-surface-2/60 p-3 text-sm leading-5">
          {terrain.elev_min_m != null && terrain.elev_max_m != null && (
            <>
              <dt className="text-text-muted">{t('Wysokość')}</dt>
              <dd className="tabular">
                {formatNum(terrain.elev_min_m, 1)}–{formatNum(terrain.elev_max_m, 1)} m n.p.m.
              </dd>
            </>
          )}
          {terrain.slope_mean_pct != null && (
            <>
              <dt className="text-text-muted">{t('Średni spadek')}</dt>
              <dd className="tabular">{formatNum(terrain.slope_mean_pct, 1)}%</dd>
            </>
          )}
          {terrain.main_flow_direction && (
            <>
              <dt className="text-text-muted">{t('Woda spływa na')}</dt>
              <dd>{t(terrain.main_flow_direction)}</dd>
            </>
          )}
          {terrain.depressions_count != null && (
            <>
              <dt className="text-text-muted">{t('Zagłębienia bez odpływu')}</dt>
              <dd className="tabular">{terrain.depressions_count}</dd>
            </>
          )}
          {d.twi_mean != null && (
            <>
              <dt className="text-text-muted">{t('Gdzie zbiera się woda')}</dt>
              <dd className="tabular">{formatNum(d.twi_mean, 1)}</dd>
            </>
          )}
          <dt className="text-text-muted">{t('Siatka NMT')}</dt>
          <dd className="tabular">{formatNum(d.grid_step_m, 0)} m</dd>
          <dt className="text-text-muted">{t('Metoda')}</dt>
          <dd>{t(d.method)}</dd>
        </dl>
      )}

      <div className="mt-2.5">
        <SourceTag
          kind={terrain.source_tag.kind}
          date={terrain.source_tag.date ? formatDatePl(terrain.source_tag.date) : undefined}
          title={terrain.source_tag.source ?? undefined}
        />
      </div>
    </section>
  )
}
