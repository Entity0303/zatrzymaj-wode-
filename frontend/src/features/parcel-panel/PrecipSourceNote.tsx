import { ChevronDown, CircleAlert, CircleCheck, CircleDashed, CircleX, CloudRain, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import type { PrecipAgreement, PrecipSources } from '@/api/types'
import { formatDatePl, formatNum, formatSigned } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** Znaczek zgodności opadu ze stacji IMGW i z danych NASA (A7). */
const AGREEMENT: Record<PrecipAgreement, { label: string; icon: LucideIcon; cls: string }> = {
  zgodne: { label: 'źródła zgodne', icon: CircleCheck, cls: 'bg-ok-soft text-brand' },
  roznia_sie: { label: 'źródła różnią się', icon: CircleAlert, cls: 'bg-warn-soft text-[#875a12]' },
  mocno_sie_roznia: { label: 'źródła mocno się różnią', icon: CircleX, cls: 'bg-danger-soft text-danger' },
  brak_danych: { label: 'brak porównania', icon: CircleDashed, cls: 'border border-nodata/60 bg-nodata-soft text-text-muted' },
}

/** „stacja IMGW Burzyn · 27 km” / „stacje IMGW Szamotuły · 28 km i Krzyż · 29 km” / „model NASA – brak stacji w pobliżu”. */
function usePrecipLabel(ps: PrecipSources): string {
  const { t } = useLang()
  const st = ps.stations ?? []
  if (ps.main === 'nasa' || !st.length) return t('dane satelitarne NASA – brak stacji pogodowej w pobliżu')
  const one = (i: number) => `${st[i].name} · ${formatNum(st[i].distance_km, 0)} km`
  if (st.length === 1) return t('stacja IMGW {s}', { s: one(0) })
  return t('stacje IMGW {a} i {b}', { a: one(0), b: one(1) })
}

export function AgreementBadge({ agreement, className }: { agreement: PrecipAgreement; className?: string }) {
  const { t } = useLang()
  const a = AGREEMENT[agreement]
  const Icon = a.icon
  return (
    <span
      title={t('Porównanie opadu ze stacji IMGW z danymi satelitarno-modelowymi NASA')}
      className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs leading-4 font-medium whitespace-nowrap', a.cls, className)}
    >
      <Icon className="size-3.5" aria-hidden /> {t(a.label)}
    </span>
  )
}

/**
 * Skąd liczymy opady (A7): zdanie `precip_sources.sentence`, stacja z odległością i znaczek zgodności.
 * `compact` – pod pozycją „Opady” w werdykcie; pełna wersja (paszport, „Wiarygodność danych”) dodaje listę stacji
 * i – w szczegółach – porównanie sum IMGW i NASA.
 */
export function PrecipSourceNote({ sources: ps, compact, className }: { sources: PrecipSources; compact?: boolean; className?: string }) {
  const { t } = useLang()
  const label = usePrecipLabel(ps)
  const [open, setOpen] = useState(false)
  const stations = ps.stations ?? []
  const windows = ps.windows ?? []

  if (compact)
    return (
      <div className={cn('space-y-1', className)}>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs leading-4 font-medium text-text-muted">
          <span className="inline-flex items-center gap-1">
            <CloudRain className="size-3.5 text-water" aria-hidden /> {label}
          </span>
          <AgreementBadge agreement={ps.agreement} />
        </p>
        <p className="text-xs leading-4 text-text-muted">{t(ps.sentence)}</p>
      </div>
    )

  return (
    <div className={cn('space-y-3 rounded-xl bg-surface p-4 shadow-card', className)}>
      <div className="flex flex-wrap items-center gap-2">
        <CloudRain className="size-5 text-water" aria-hidden />
        <h4 className="text-base leading-6 font-semibold">{t('Skąd dane o opadach')}</h4>
        <AgreementBadge agreement={ps.agreement} className="ml-auto" />
      </div>
      <p className="text-sm leading-5 font-medium">{label}</p>
      <p className="text-sm leading-5">{t(ps.sentence)}</p>
      {ps.main === 'imgw_daleko' && (
        <p className="flex gap-2 rounded-lg bg-warn-soft px-3 py-2 text-sm leading-5">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-[#875a12]" aria-hidden />
          {t('Stacje dalej niż 30 km – opad mniej pewny.')}
        </p>
      )}
      {ps.main === 'nasa' && (
        <p className="flex gap-2 rounded-lg bg-warn-soft px-3 py-2 text-sm leading-5">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-[#875a12]" aria-hidden />
          {t('Brak stacji IMGW w pobliżu – opad z modelu NASA.')}
        </p>
      )}
      {stations.length > 0 && (
        <ul className="space-y-1 text-sm leading-5">
          {stations.map((s) => (
            <li key={s.code} className="flex flex-wrap gap-x-1.5">
              <span className="font-medium">{s.name}</span>
              <span className="text-text-muted">
                ({t(s.kind_label)}) · {formatNum(s.distance_km, 0)} km · {t('waga {w}%', { w: formatNum(s.weight * 100, 0) })}
              </span>
            </li>
          ))}
        </ul>
      )}
      {windows.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-brand hover:underline"
          >
            {t(open ? 'Ukryj porównanie' : 'Porównanie stacji IMGW i NASA')}
            <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
          </button>
          {open && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-left text-sm">
                <thead className="text-text-muted">
                  <tr className="border-b">
                    <th className="py-2 pr-3 font-medium">{t('Okres')}</th>
                    <th className="py-2 pr-3 text-right font-medium">IMGW</th>
                    <th className="py-2 pr-3 text-right font-medium">NASA</th>
                    <th className="py-2 pr-3 text-right font-medium">{t('Różnica')}</th>
                    <th className="py-2 font-medium">{t('Ocena')}</th>
                  </tr>
                </thead>
                <tbody>
                  {windows.map((w) => (
                    <tr key={w.key} className="border-b align-top last:border-0">
                      <td className="py-2 pr-3">
                        {t(w.label)}
                        <span className="block text-xs text-text-muted">
                          {formatDatePl(w.start)} – {formatDatePl(w.end)}
                        </span>
                      </td>
                      <td className="tabular py-2 pr-3 text-right">{w.imgw_mm != null ? `${formatNum(w.imgw_mm, 0)} mm` : '—'}</td>
                      <td className="tabular py-2 pr-3 text-right">{w.nasa_mm != null ? `${formatNum(w.nasa_mm, 0)} mm` : '—'}</td>
                      <td className="tabular py-2 pr-3 text-right">{w.difference_pct != null ? `${formatSigned(w.difference_pct, 0)}%` : '—'}</td>
                      <td className="py-2">
                        <AgreementBadge agreement={w.rating} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-xs leading-4 text-text-muted">{t('Różnica: o ile procent NASA pokazuje więcej (+) albo mniej (−) niż stacje.')}</p>
            </div>
          )}
        </>
      )}
      <p className="text-xs leading-4 text-text-muted">
        {ps.source_tag.source}
        {ps.source_tag.date ? ` · ${t('dane do {d}', { d: formatDatePl(ps.source_tag.date) })}` : ''}
      </p>
    </div>
  )
}
