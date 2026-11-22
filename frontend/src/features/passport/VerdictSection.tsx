import type { AnalysisResponse, VerdictKind } from '@/api/types'
import { StatusRows } from '@/components/StatusRows'
import { HYDRO_KIND, formatDistance } from '@/lib/hydro'
import { balanceText, formatDatePl, formatNum } from '@/lib/format'
import { seasonBalance } from '@/lib/seasonBalance'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { LevelDot } from './LevelDot'
import { PassportCard } from './PassportCard'
import { PassportSection } from './PassportSection'

/** Kolejność i nazwy punktów werdyktu (gleba, opady, teren, rośliny – jak w raporcie). */
const KIND_ORDER: VerdictKind[] = ['gleba', 'opady', 'teren', 'rosliny']
const KIND_LABEL: Partial<Record<VerdictKind, string>> = { gleba: 'Gleba', opady: 'Opady', teren: 'Teren', rosliny: 'Rośliny (z satelity)' }

const GAUGE_STATE: Record<'niski' | 'sredni' | 'wysoki', string> = { niski: 'stan niski', sredni: 'stan średni', wysoki: 'stan wysoki' }

/** Kafel obok werdyktu (1/3 szerokości). */
function Tile({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-[18px] border border-paper-line bg-surface p-4">
      <p className="text-sm leading-5 font-semibold text-text-muted">{title}</p>
      <div className="mt-1.5 space-y-1.5">{children}</div>
    </div>
  )
}

/**
 * 1. Werdykt (F6): 2/3 – „Teraz / W dniu analizy” i „Na dłuższą metę”, duży nagłówek werdyktu, 3–4 punkty
 * (gleba, opady, teren, rośliny) z kółkiem poziomu, „Siej:” i „Unikaj:” z chipami. 1/3 – trzy kafle: zapas wody
 * w glebie (% pełnego, pasek, porównanie z tą samą porą w 10 latach), bilans okresu vs zwykle („zabrakło X mm”),
 * woda w okolicy (rowy i zbiorniki w 500 m + wodowskaz).
 */
export function VerdictSection({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const v = analysis.verdict
  const ind = analysis.indicators
  const statements = v
    ? [...v.statements.filter((s) => KIND_ORDER.includes(s.kind))].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind)).slice(0, 4)
    : []

  // kafel 1: zapas wody w glebie
  const water = ind.soil_water_pct.value
  const rank = analysis.soil_water?.rank
  // kafel 2: bilans okresu (wybrany okres albo od początku sezonu)
  const p = analysis.period
  const season = seasonBalance(analysis)
  const bal = p ? p.balance_mm : season.mm
  const diff = p ? p.balance_mm - p.normal_balance_mm : analysis.history.balance_deviation_mm
  const balLabel = p ? t(p.label) : t('od {d}', { d: formatDatePl(season.from) })
  // kafel 3: woda w okolicy
  const h = analysis.hydro
  const near = [...(h?.features ?? [])].sort((a, b) => a.distance_m - b.distance_m)

  return (
    <PassportSection id="pp-werdykt" title={t('Werdykt')}>
      <div className="grid gap-4 lg:grid-cols-3">
        <PassportCard className="lg:col-span-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <StatusRows now={analysis.status.level} longTerm={v?.level} historical={analysis.historical} />
            {analysis.status.score != null && (
              <span className="tabular rounded-full bg-surface-2 px-3 py-1 text-sm font-semibold" title={t('Ogólny stan wodny: 100 = dużo wody, 0 = bardzo mało wody.')}>
                {t('stan wodny {n}/100', { n: Math.round(analysis.status.score) })}
              </span>
            )}
          </div>
          <p className="mt-3 font-display text-2xl leading-8 font-bold text-text md:text-[28px] md:leading-9">{t(v?.headline ?? analysis.status.headline)}</p>
          {statements.length > 0 && (
            <ul className="mt-4 space-y-3">
              {statements.map((s) => (
                <li key={s.kind} className="flex gap-3">
                  <LevelDot level={s.level} className="mt-0.5" />
                  <p className="min-w-0 text-base leading-6">
                    <b className="font-semibold">{t(KIND_LABEL[s.kind] ?? s.kind)}:</b> {t(s.text)}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {v && ((v.crops_good?.length ?? 0) > 0 || (v.crops_bad?.length ?? 0) > 0) && (
            <div className="mt-4 space-y-2 border-t border-paper-line pt-4">
              {(v.crops_good?.length ?? 0) > 0 && (
                <p className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{t('Siej:')}</span>
                  {v.crops_good!.map((c) => (
                    <span key={c.crop_id} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-ok-soft px-3 text-sm font-medium text-pp-brand">
                      <LevelDot level="ok" size={16} /> {t(c.label)}
                    </span>
                  ))}
                </p>
              )}
              {(v.crops_bad?.length ?? 0) > 0 && (
                <p className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{t('Unikaj:')}</span>
                  {v.crops_bad!.map((c) => (
                    <span key={c.crop_id} title={c.reason ? t(c.reason) : undefined} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-danger-soft px-3 text-sm font-medium text-pp-bad">
                      <LevelDot level="bad" size={16} /> {t(c.label)}
                    </span>
                  ))}
                </p>
              )}
            </div>
          )}
        </PassportCard>

        <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
          <Tile title={t('Zapas wody w glebie')}>
            {water == null ? (
              <p className="text-sm text-text-muted">{t('Brak danych dla tej daty')}</p>
            ) : (
              <>
                <p className="tabular text-[28px] leading-8 font-bold">
                  {formatNum(water, 0)}
                  <span className="text-base font-semibold text-text-muted"> {t('% pełnego')}</span>
                </p>
                <div className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                  <div className="h-full rounded-full bg-pp-water" style={{ width: `${Math.max(0, Math.min(100, water))}%` }} />
                </div>
                {ind.soil_capacity.value != null && (
                  <p className="text-sm leading-5 text-text-muted">{t('pełny zapas tej gleby: ok. {n} mm', { n: formatNum(ind.soil_capacity.value, 0) })}</p>
                )}
                {rank && rank.of_years > 0 && (
                  <p className="text-sm leading-5 text-text-muted">
                    {rank.lower_years === 0
                      ? t('O tej porze roku mniej wody nie było w żadnym z {of} lat.', { of: rank.of_years })
                      : t('O tej porze roku mniej wody było w {n} z {of} lat.', { n: rank.lower_years, of: rank.of_years })}
                  </p>
                )}
              </>
            )}
            {(ind.risk_7d.label || ind.risk_7d.note) && (
              <p className="border-t border-paper-line pt-1.5 text-sm leading-5">
                <span className="font-semibold">{t('Ryzyko na 7 dni:')}</span> {t(ind.risk_7d.label ?? '—')}
                {ind.risk_7d.note && <span className="block text-text-muted">{t(ind.risk_7d.note)}</span>}
              </p>
            )}
          </Tile>

          <Tile title={t('Bilans wody (opad minus parowanie)')}>
            {bal == null ? (
              <p className="text-sm text-text-muted">{t('Brak danych dla tej daty')}</p>
            ) : (
              <>
                <p className={cn('tabular text-[28px] leading-8 font-bold', bal < 0 ? 'text-pp-bad' : 'text-pp-water')}>{t(...balanceText(bal))}</p>
                <p className="text-sm leading-5 text-text-muted">{balLabel}</p>
                {diff != null && Math.round(diff) !== 0 && (
                  <p className={cn('text-sm leading-5 font-medium', diff < 0 ? 'text-pp-bad' : 'text-pp-water')}>
                    {t(diff < 0 ? '{n} mm mniej niż zwykle' : '{n} mm więcej niż zwykle', { n: formatNum(Math.abs(diff), 0) })}
                  </p>
                )}
              </>
            )}
          </Tile>

          <Tile title={t('Woda w okolicy')}>
            {!h ? (
              <p className="text-sm text-text-muted">{t('Brak danych o wodzie w okolicy')}</p>
            ) : h.status === 'pending' ? (
              <p className="text-sm text-text-muted">{t('Szukam wody w okolicy…')}</p>
            ) : (
              <>
                <p className="text-base leading-6 font-semibold">
                  {near.length ? t('Rowy i zbiorniki w 500 m: {n}', { n: near.length }) : t('Brak rzek i rowów w promieniu 500 m')}
                </p>
                {near[0] && (
                  <p className="text-sm leading-5 text-text-muted">
                    {t('najbliżej: {kind} – {d}', { kind: t(HYDRO_KIND[near[0].kind]).toLowerCase(), d: near[0].distance_m < 5 ? t('przy samej działce') : formatDistance(near[0].distance_m) })}
                  </p>
                )}
                {h.gauge ? (
                  <p className="text-sm leading-5">
                    {t('Wodowskaz {name} ({river}): {state}', { name: h.gauge.name, river: h.gauge.river, state: t(GAUGE_STATE[h.gauge.state]) })}
                  </p>
                ) : (
                  analysis.historical && <p className="text-sm leading-5 text-text-muted">{t('Brak stanu wodowskazu z dnia analizy ({d})', { d: formatDatePl(analysis.analysis_date) })}</p>
                )}
              </>
            )}
          </Tile>
        </div>
      </div>
    </PassportSection>
  )
}
