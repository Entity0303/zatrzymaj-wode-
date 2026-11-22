import { ChevronDown, CircleAlert, Loader2, Minus, Satellite as SatelliteIcon, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import type { Satellite, SatelliteTrend } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, formatNum, formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { useSettings } from '@/lib/storage'
import { cn } from '@/lib/utils'
import { SatelliteSeriesChart } from './SatelliteSeriesChart'

const TREND: Record<SatelliteTrend, { label: string; icon: LucideIcon; cls: string }> = {
  lepiej: { label: 'zieleń bujniejsza niż rok temu', icon: TrendingUp, cls: 'text-brand' },
  podobnie: { label: 'zieleń podobna do zeszłorocznej', icon: Minus, cls: 'text-text-muted' },
  gorzej: { label: 'zieleń słabsza niż rok temu', icon: TrendingDown, cls: 'text-danger' },
}

/**
 * „Z satelity” (A11, Sentinel-2): data zdjęcia, jedno zdanie dla rolnika, porównanie z tą samą porą rok temu,
 * mały wykres z 12 miesięcy. Wskaźniki techniczne (NDVI / NDMI, udział widocznej części, chmury) – tylko
 * w „Szczegółach”. Zdjęcie liczy się osobno: `pending` = „Pobieram zdjęcie satelitarne…”.
 * `passport` – wersja do paszportu (większa, wykres z wilgotnością roślin, szczegóły otwarte w wydruku).
 */
export function SatelliteCard({ satellite: s, passport, chartWidth }: { satellite: Satellite; passport?: boolean; chartWidth?: number }) {
  const { t } = useLang()
  const [settings] = useSettings()
  const advisor = settings.mode === 'doradca'
  const [open, setOpen] = useState(!!chartWidth)
  const head = (
    <div className="flex items-center gap-2">
      <SatelliteIcon className="size-5 shrink-0 text-brand" aria-hidden />
      <h4 className={cn('min-w-0 flex-1 font-semibold', passport ? 'text-lg leading-7' : 'text-base leading-6')}>{t('Z satelity')}</h4>
      {s.status === 'ok' && s.date && (
        <span title={s.source_tag.source ?? undefined} className="text-sm leading-5 whitespace-nowrap text-text-muted">
          {t('zdjęcie z {d}', { d: formatDatePl(s.date) })}
        </span>
      )}
    </div>
  )
  const box = cn('space-y-2.5 rounded-xl bg-surface', passport ? 'p-4 shadow-card' : 'border p-3.5')

  if (s.status === 'pending')
    return (
      <section aria-label={t('Z satelity')} aria-busy className={box}>
        {head}
        <p className="flex items-center gap-2 text-sm leading-5 text-text-muted" role="status">
          <Loader2 className="size-4 animate-spin text-brand" aria-hidden /> {t('Pobieram zdjęcie satelitarne…')}
        </p>
      </section>
    )

  if (s.status !== 'ok')
    return (
      <section aria-label={t('Z satelity')} className={box}>
        {head}
        <p className="text-sm leading-5 text-text-muted">{t(s.sentence ?? s.warning ?? 'Brak bezchmurnego zdjęcia przed tą datą – reszta wyniku jest pełna')}</p>
        <SourceTag kind="brak_danych" title={s.source_tag.source ?? undefined} />
      </section>
    )

  const trend = s.trend ? TREND[s.trend] : null
  const TrendIcon = trend?.icon
  const series = s.series ?? []
  return (
    <section aria-label={t('Z satelity')} className={box}>
      {head}
      {s.sentence && <p className={cn('font-medium', passport ? 'text-lg leading-7' : 'text-base leading-6')}>{t(s.sentence)}</p>}
      {/* F31: tryb Doradca – nota z typowym zakresem zieleni (NDVI) dla uprawy i miesiąca (A25) */}
      {advisor && s.note && <p className="text-sm leading-5 text-text-muted">{t(s.note)}</p>}
      {trend && TrendIcon && (
        <p className={cn('flex items-center gap-1.5 text-sm leading-5', trend.cls)}>
          <TrendIcon className="size-4 shrink-0" aria-hidden />
          <span>
            {t(trend.label)}
            {s.last_year?.date && <span className="text-text-muted"> · {t('zdjęcie z {d}', { d: formatDatePl(s.last_year.date) })}</span>}
          </span>
        </p>
      )}
      {s.warning && (
        <p className="flex gap-2 rounded-lg bg-warn-soft px-3 py-2 text-sm leading-5">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-[#875a12]" aria-hidden /> {t(s.warning)}
        </p>
      )}
      {series.length > 1 && (
        <div className="space-y-1">
          <p className="text-xs leading-4 font-medium text-text-muted">{t('Ostatnie 12 miesięcy')}</p>
          <SatelliteSeriesChart series={series} withMoisture={passport} height={passport ? 170 : 96} width={chartWidth} />
        </div>
      )}

      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-brand hover:underline"
      >
        {t(open ? 'Ukryj szczegóły' : 'Szczegóły dla dociekliwych')}
        <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm leading-5">
          <dt className="text-text-muted">{t('Kondycja (NDVI)')}</dt>
          <dd className="tabular">
            {s.ndvi != null ? formatNum(s.ndvi, 2) : t('brak danych')}
            {s.ndvi_label && <span className="text-text-muted"> · {t(s.ndvi_label)}</span>}
          </dd>
          <dt className="text-text-muted">{t('Wilgotność roślin (NDMI)')}</dt>
          <dd className="tabular">
            {s.ndmi != null ? formatNum(s.ndmi, 2) : t('brak danych')}
            <span className="text-text-muted"> · {t(s.ndmi_label ?? 'oceniamy od kwietnia do września, gdy łan jest gęsty')}</span>
          </dd>
          {s.last_year && (
            <>
              <dt className="text-text-muted">{t('Rok temu')}</dt>
              <dd className="tabular">
                {s.last_year.ndvi != null ? `NDVI ${formatNum(s.last_year.ndvi, 2)}` : t('brak danych')} ({formatDatePl(s.last_year.date)})
                {s.ndvi_change != null && <span className="text-text-muted"> · {t('zmiana {v}', { v: formatSigned(s.ndvi_change, 2) })}</span>}
              </dd>
            </>
          )}
          {s.valid_pct != null && (
            <>
              <dt className="text-text-muted">{t('Widoczna część działki')}</dt>
              <dd className="tabular">{formatNum(s.valid_pct, 0)}%</dd>
            </>
          )}
          {s.cloud_pct != null && (
            <>
              <dt className="text-text-muted">{t('Chmury nad działką')}</dt>
              <dd className="tabular">{formatNum(s.cloud_pct, 0)}%</dd>
            </>
          )}
          {s.series_note && <dd className="col-span-2 text-xs leading-4 text-text-muted">{t(s.series_note)}</dd>}
          {s.note && !advisor && <dd className="col-span-2 text-xs leading-4 text-text-muted">{t(s.note)}</dd>}
          {s.scene_id && <dd className="col-span-2 text-xs leading-4 break-all text-text-muted">{s.scene_id}</dd>}
        </dl>
      )}
    </section>
  )
}
