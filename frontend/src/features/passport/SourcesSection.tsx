import { CircleAlert, CircleCheck, CircleX, ShieldCheck } from 'lucide-react'
import type { AnalysisResponse, Confidence, SourceAvailability, SourceStatus } from '@/api/types'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { PassportCard } from './PassportCard'
import { PassportSection } from './PassportSection'

const CONFIDENCE: Record<Confidence, { label: string; cls: string }> = {
  wysoka: { label: 'Wysoka', cls: 'bg-ok-soft text-pp-brand' },
  srednia: { label: 'Średnia', cls: 'bg-amber-soft text-[#875a12]' },
  ograniczona: { label: 'Ograniczone dane', cls: 'bg-danger-soft text-pp-bad' },
}

const AVAIL: Record<SourceAvailability, { label: string; icon: typeof CircleCheck; cls: string }> = {
  ok: { label: 'jest', icon: CircleCheck, cls: 'text-pp-ok' },
  czesciowo: { label: 'częściowo', icon: CircleAlert, cls: 'text-[#875a12]' },
  brak: { label: 'brak', icon: CircleX, cls: 'text-pp-bad' },
}

/** Ograniczenia, które dotyczą każdej analizy (zawsze prawdziwe dla tej metody) – dopisywane, gdy API ich nie podało. */
const STANDARD_LIMITS: { key: RegExp; text: string }[] = [
  { key: /gruntow/i, text: 'Nie znamy poziomu wód gruntowych – model liczy wodę z opadów i parowania w strefie korzeni.' },
  { key: /teren\w* nie zmienia|nie zmienia bilansu/i, text: 'Teren opisujemy z modelu GUGiK; nie zmienia on obliczonego bilansu wody w glebie.' },
  { key: /typow\w* plon|nie jest prognoz/i, text: 'Typowy plon to wynik symulacji na pogodzie z 10 lat – nie prognoza tegorocznych zbiorów.' },
]

/**
 * F-MASTER B4 / A20: data źródła. `fetched_at` (A20) albo data danych późniejsza niż data analizy = data POBRANIA
 * („pobrano dd.mm.rrrr”), nie danych (pole `fetched_at` czytane opcjonalnie – typ lokalny).
 */
function dates(s: SourceStatus, analysisDate: string, t: (k: string, v?: Record<string, string | number>) => string): string {
  const fetched = (s as SourceStatus & { fetched_at?: string | null }).fetched_at?.slice(0, 10) ?? (s.data_date && s.data_date > analysisDate ? s.data_date : null)
  const data = s.data_date && s.data_date <= analysisDate ? t('dane z {d}', { d: formatDatePl(s.data_date) }) : null
  return [data, fetched ? t('pobrano {d}', { d: formatDatePl(fetched) }) : null].filter(Boolean).join(' · ') || '—'
}

/**
 * 7. Skąd dane (F6): siatka kafli – źródło, do czego użyte, data („pobrano …” gdy po dacie analizy), stan;
 * pewność wyniku i kompletność; ograniczenia (z API + zawsze prawdziwe dla metody: wody gruntowe, teren nie zmienia
 * bilansu, typowy plon ≠ prognoza).
 */
export function SourcesSection({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const r = analysis.reliability
  const c = CONFIDENCE[r.confidence]
  const pct = r.completeness.total ? (r.completeness.available / r.completeness.total) * 100 : 0
  const limits = [...r.limitations, ...STANDARD_LIMITS.filter((l) => !r.limitations.some((x) => l.key.test(x))).map((l) => l.text)]
  return (
    <PassportSection id="pp-zrodla" title={t('Skąd dane')}>
      <PassportCard>
        <div className="flex flex-wrap items-start gap-5">
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
              <div className="h-full rounded-full bg-pp-brand" style={{ width: `${pct}%` }} />
            </div>
            <p className="tabular text-sm font-medium">{t('{a} z {n} źródeł', { a: r.completeness.available, n: r.completeness.total })}</p>
          </div>
        </div>
      </PassportCard>

      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {r.sources.map((s) => {
          const a = AVAIL[s.status]
          const Icon = a.icon
          return (
            <li key={s.name} className="min-w-0 rounded-[18px] border border-paper-line bg-surface p-4 text-sm leading-5">
              <div className="flex items-start gap-2">
                <span className="min-w-0 flex-1 font-bold">{s.name}</span>
                <span className={cn('inline-flex shrink-0 items-center gap-1 font-medium', a.cls)}>
                  <Icon className="size-4" aria-hidden /> {t(a.label)}
                </span>
              </div>
              <p className="mt-1">{t(s.used_for)}</p>
              {s.resolution && <p className="text-xs leading-4 text-text-muted">{t(s.resolution)}</p>}
              {s.note && <p className="text-xs leading-4 text-text-muted">{t(s.note)}</p>}
              <p className="tabular mt-1.5 text-xs leading-4 text-text-muted">{dates(s, analysis.analysis_date, t)}</p>
            </li>
          )
        })}
      </ul>

      <PassportCard title={t('Co warto wiedzieć o tych danych')}>
        <ul className="space-y-1.5">
          {limits.map((l) => (
            <li key={l} className="flex gap-2 text-sm leading-5 text-text-muted">
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-pp-warn" aria-hidden /> {t(l)}
            </li>
          ))}
        </ul>
      </PassportCard>
    </PassportSection>
  )
}
