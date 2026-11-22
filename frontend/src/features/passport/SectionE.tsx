import { CircleAlert, CircleCheck, CircleX, ShieldCheck } from 'lucide-react'
import type { AnalysisResponse, Confidence, SourceAvailability, SourceStatus } from '@/api/types'
import { formatDatePl } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'
import { PassportSection } from './PassportSection'
import { PrecipSourceNote } from '@/features/parcel-panel/PrecipSourceNote'

const CONFIDENCE: Record<Confidence, { label: string; cls: string }> = {
  wysoka: { label: 'Wysoka', cls: 'bg-ok-soft text-brand' },
  srednia: { label: 'Średnia', cls: 'bg-amber-soft text-[#875a12]' },
  ograniczona: { label: 'Ograniczone dane', cls: 'bg-danger-soft text-danger' },
}

const AVAIL: Record<SourceAvailability, { label: string; icon: typeof CircleCheck; cls: string }> = {
  ok: { label: 'jest', icon: CircleCheck, cls: 'text-ok' },
  czesciowo: { label: 'częściowo', icon: CircleAlert, cls: 'text-amber' },
  brak: { label: 'brak', icon: CircleX, cls: 'text-danger' },
}

/** E. Wiarygodność danych (SPEC 7.E): pewność + powód, kompletność, tabela źródeł, ograniczenia. */
/**
 * F-MASTER B4: data źródła w karcie „Skąd dane”. Data późniejsza niż data analizy (np. granice z ULDK pobrane dziś
 * przy analizie z 2018) to data POBRANIA, nie danych – podpis „pobrano dd.mm.rrrr”. Backend dopisuje `fetched_at`
 * (A20) – gdy jest, bierzemy je wprost (pole opcjonalne, typ lokalny).
 */
type SourceFetched = SourceStatus & { fetched_at?: string | null }
function sourceDate(s: SourceStatus, analysisDate: string, t: (k: string, v?: Record<string, string | number>) => string) {
  const fetched = (s as SourceFetched).fetched_at?.slice(0, 10) ?? null
  const later = !!s.data_date && s.data_date > analysisDate
  if (later || (!s.data_date && fetched)) {
    const d = formatDatePl(fetched ?? s.data_date!)
    return { label: t('Pobrano'), text: d, cell: t('pobrano {d}', { d }) }
  }
  const d = s.data_date ? formatDatePl(s.data_date) : '—'
  return { label: t('Data danych'), text: d, cell: d }
}

export function SectionE({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const r = analysis.reliability
  const c = CONFIDENCE[r.confidence]
  const pct = r.completeness.total ? (r.completeness.available / r.completeness.total) * 100 : 0
  return (
    <PassportSection id="pass-e" letter="E" title={t('Skąd dane')}>
      <div className="flex flex-wrap items-start gap-4 rounded-xl bg-surface p-4 shadow-card">
        <div className="min-w-0 flex-1 basis-60 space-y-1.5">
          <p className="text-sm leading-5 text-text-muted">{t('Pewność wyniku')}</p>
          <span className={cn('inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-base font-semibold', c.cls)}>
            <ShieldCheck className="size-5" aria-hidden /> {t(c.label)}
          </span>
          <p className="text-sm leading-5">{t(r.reason)}</p>
        </div>
        <div className="w-full max-w-56 space-y-1.5">
          <p className="text-sm leading-5 text-text-muted">{t('Kompletność danych')}</p>
          <div className="h-2.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
            <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
          </div>
          <p className="tabular text-sm font-medium">
            {t('{a} z {n} źródeł', { a: r.completeness.available, n: r.completeness.total })}
          </p>
        </div>
      </div>

      {/* telefon: źródła jako lista (bez przewijania tabeli w poziomie) */}
      <ul className="space-y-2 sm:hidden">
        {r.sources.map((s) => {
          const a = AVAIL[s.status]
          const Icon = a.icon
          return (
            <li key={s.name} className="rounded-xl bg-surface p-3.5 text-sm leading-5 shadow-card">
              <div className="flex items-start gap-2">
                <span className="min-w-0 flex-1 font-semibold">{s.name}</span>
                <span className={cn('inline-flex shrink-0 items-center gap-1 font-medium', a.cls)}>
                  <Icon className="size-4" aria-hidden /> {t(a.label)}
                </span>
              </div>
              <p className="mt-1">{t(s.used_for)}</p>
              {s.resolution && <p className="text-xs leading-4 text-text-muted">{t(s.resolution)}</p>}
              {s.note && <p className="text-xs leading-4 text-text-muted">{t(s.note)}</p>}
              <p className="mt-1 text-xs leading-4 text-text-muted">
                {sourceDate(s, analysis.analysis_date, t).label}: <span className="tabular">{sourceDate(s, analysis.analysis_date, t).text}</span>
              </p>
            </li>
          )
        })}
      </ul>
      <div className="overflow-x-auto rounded-xl bg-surface shadow-card max-sm:hidden">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="text-text-muted">
            <tr className="border-b">
              <th className="px-4 py-2.5 font-medium">{t('Źródło')}</th>
              <th className="px-4 py-2.5 font-medium">{t('Co z niego bierzemy')}</th>
              <th className="px-4 py-2.5 font-medium">{t('Data danych')}</th>
              <th className="px-4 py-2.5 font-medium">{t('Stan')}</th>
            </tr>
          </thead>
          <tbody>
            {r.sources.map((s) => {
              const a = AVAIL[s.status]
              const Icon = a.icon
              return (
                <tr key={s.name} className="border-b last:border-0 align-top">
                  <td className="px-4 py-2.5 font-medium">{s.name}</td>
                  <td className="px-4 py-2.5">
                    {t(s.used_for)}
                    {s.resolution && <span className="block text-xs text-text-muted">{t(s.resolution)}</span>}
                    {s.note && <span className="block text-xs text-text-muted">{t(s.note)}</span>}
                  </td>
                  <td className="tabular px-4 py-2.5 whitespace-nowrap">{sourceDate(s, analysis.analysis_date, t).cell}</td>
                  <td className="px-4 py-2.5">
                    <span className={cn('inline-flex items-center gap-1 font-medium whitespace-nowrap', a.cls)}>
                      <Icon className="size-4" aria-hidden /> {t(a.label)}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {analysis.precip_sources && <PrecipSourceNote sources={analysis.precip_sources} />}

      {r.limitations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-base leading-6 font-semibold">{t('Co warto wiedzieć o tych danych')}</h4>
          <ul className="space-y-1.5">
            {r.limitations.map((l) => (
              <li key={l} className="flex gap-2 text-sm leading-5 text-text-muted">
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber" aria-hidden /> {t(l)}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs leading-4 text-text-muted">
        {t('Wynik ma charakter pomocniczy i opiera się na danych publicznych.')}
      </p>
    </PassportSection>
  )
}
