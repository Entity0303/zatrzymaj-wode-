import { ChevronDown, Loader2 } from 'lucide-react'
import { useState } from 'react'
import type { AnalysisResponse } from '@/api/types'
import { SatelliteCard } from '@/features/parcel-panel/SatelliteCard'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { useSettings } from '@/lib/storage'
import { cn } from '@/lib/utils'
import { PassportCard } from './PassportCard'

const TREND_LABEL = { lepiej: 'bujniej niż rok temu', podobnie: 'podobnie jak rok temu', gorzej: 'słabiej niż rok temu' } as const

/** Kafel wskaźnika z satelity: ocena słowami, „rok temu” pod spodem. */
function Tile({ title, value, lastYear, muted }: { title: string; value: string; lastYear?: string | null; muted?: boolean }) {
  return (
    <div className="min-w-0 rounded-xl border border-paper-line p-3">
      <p className="text-sm leading-5 text-text-muted">{title}</p>
      <p className={cn('mt-0.5 text-base leading-6 font-semibold first-letter:uppercase', muted && 'font-normal text-text-muted')}>{value}</p>
      {lastYear && <p className="mt-0.5 text-xs leading-4 text-text-muted">{lastYear}</p>}
    </div>
  )
}

/**
 * 5b. Z satelity (F6): zdanie słowami, kafle „Kondycja upraw” i „Wilgotność roślin” (z porównaniem z rokiem
 * wcześniej), mini-słupki zieleni z dostępnego szeregu (12 mies.), data zdjęcia. Bez NDVI / NDMI w głównym widoku –
 * liczby w trybie Doradca pod „Szczegóły” (dotychczasowa karta z wykresem i tabelą).
 */
export function SatelliteSection({ analysis, chartWidth }: { analysis: AnalysisResponse; chartWidth?: number }) {
  const { t } = useLang()
  const [settings] = useSettings()
  const [open, setOpen] = useState(false)
  const s = analysis.satellite
  const ind = analysis.indicators
  const series = (s?.series ?? []).filter((p) => p.ndvi != null)
  const maxNdvi = Math.max(0.01, ...series.map((p) => p.ndvi ?? 0))
  return (
    <div id="pp-satelita" className="grid content-start gap-4">
      <h3 id="pp-satelita-h" className="font-display text-[22px] leading-7 font-bold">
        {t('Z satelity')}
      </h3>
      <PassportCard
        title={t('Zdjęcie satelitarne')}
        aside={s?.status === 'ok' && s.date ? <span className="text-sm text-text-muted">{t('zdjęcie z {d}', { d: formatDatePl(s.date) })}</span> : undefined}
      >
        {!s ? (
          <p className="text-sm text-text-muted">{t('Brak zdjęcia satelitarnego')}</p>
        ) : s.status === 'pending' ? (
          <p className="flex items-center gap-2 text-sm text-text-muted" role="status">
            <Loader2 className="size-4 animate-spin text-pp-brand" aria-hidden /> {t('Pobieram zdjęcie satelitarne…')}
          </p>
        ) : s.status !== 'ok' ? (
          <p className="text-sm leading-5 text-text-muted">{t(s.sentence ?? s.warning ?? 'Brak bezchmurnego zdjęcia przed tą datą – reszta wyniku jest pełna')}</p>
        ) : (
          <div className="space-y-3">
            {s.sentence && <p className="text-base leading-6 font-medium">{t(s.sentence)}</p>}
            {/* F31: tryb Doradca – nota z typowym zakresem zieleni (NDVI) dla uprawy i miesiąca (A25) */}
            {settings.mode === 'doradca' && s.note && <p className="text-sm leading-5 text-text-muted">{t(s.note)}</p>}
            <div className="grid gap-3 sm:grid-cols-2">
              <Tile
                title={t('Kondycja upraw')}
                value={t(ind.crop_health.label ?? s.ndvi_label ?? 'brak danych')}
                lastYear={s.trend ? `${t(TREND_LABEL[s.trend])}${s.last_year?.date ? ` · ${formatDatePl(s.last_year.date)}` : ''}` : s.last_year ? null : t('rok temu: brak zdjęcia do porównania')}
              />
              <Tile
                title={t('Wilgotność roślin')}
                value={t(ind.plant_moisture.label ?? s.ndmi_label ?? 'oceniamy od kwietnia do września, gdy łan jest gęsty')}
                muted={!s.ndmi_label}
                lastYear={s.last_year?.date ? t('rok temu: zdjęcie z {d}', { d: formatDatePl(s.last_year.date) }) : null}
              />
            </div>
            {s.warning && <p className="rounded-lg bg-warn-soft px-3 py-2 text-sm leading-5">{t(s.warning)}</p>}
            {series.length > 1 && (
              <div>
                <p className="text-xs leading-4 font-medium text-text-muted">{t('Zieleń w ostatnich 12 miesiącach')}</p>
                <div className="mt-1.5 flex h-16 items-end gap-[3px]" role="img" aria-label={t('Zieleń w ostatnich 12 miesiącach')}>
                  {series.map((p) => (
                    <span
                      key={p.date}
                      title={formatDatePl(p.date)}
                      className="min-w-0 flex-1 rounded-t-sm bg-pp-ok"
                      style={{ height: `${Math.max(4, ((p.ndvi ?? 0) / maxNdvi) * 100)}%`, opacity: p.valid_pct < 50 ? 0.45 : 1 }}
                    />
                  ))}
                </div>
                <div className="mt-1 flex justify-between text-xs leading-4 text-text-muted">
                  <span>{formatDatePl(series[0].date)}</span>
                  <span>{formatDatePl(series[series.length - 1].date)}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </PassportCard>
      {s && settings.mode === 'doradca' && (
        <div>
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-pp-brand">
            {t('Szczegóły')} <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
          </button>
          {open && <SatelliteCard satellite={s} passport chartWidth={chartWidth} />}
        </div>
      )}
    </div>
  )
}
