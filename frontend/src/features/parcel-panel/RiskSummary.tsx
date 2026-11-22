import type { AnalysisResponse, StatusLevel, VerdictLevel } from '@/api/types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { LONG_TERM_LABEL, NOW_LABEL, STATUS } from '@/theme/status'

type Risk = 'niskie' | 'srednie' | 'wysokie'

/** Kolory stanu – tylko tu i w ikonach stanu (czerwony = prawdziwe zagrożenie suszą). */
const RISK: Record<Risk, { label: string; bar: string; soft: string }> = {
  niskie: { label: 'Ryzyko suszy: niskie', bar: 'bg-ok', soft: 'bg-ok-soft' },
  srednie: { label: 'Ryzyko suszy: średnie', bar: 'bg-amber', soft: 'bg-amber-soft' },
  wysokie: { label: 'Ryzyko suszy: wysokie', bar: 'bg-danger', soft: 'bg-danger-soft' },
}

const FROM_VERDICT: Record<VerdictLevel, Risk> = { ok: 'niskie', warn: 'srednie', bad: 'wysokie' }
const FROM_STATUS: Partial<Record<StatusLevel, Risk>> = { ok: 'niskie', warn: 'srednie', risk: 'wysokie', danger: 'wysokie' }

/**
 * Podsumowanie na górze panelu (przeprojektowanie): „Teraz: woda w normie · Na dłuższą metę: wysokie ryzyko suszy”
 * (stan dziś + ryzyko na lata z werdyktu, kolor paska = ryzyko na lata) i jedno zdanie wyjaśnienia (nagłówek werdyktu). Akcent: pasek po lewej, bez tła w paski.
 * Z werdyktu działki (gleba, opady, 10 lat), a bez werdyktu – z oceny stanu wody.
 */
export function RiskSummary({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const v = analysis.verdict
  const risk = v ? FROM_VERDICT[v.level] : FROM_STATUS[analysis.status.level]
  const sentence = v?.headline ?? analysis.status.headline
  const now = analysis.status.level
  const NowIcon = STATUS[now].icon
  if (!risk)
    return (
      <div className="rounded-xl border bg-surface px-4 py-3">
        <p className="text-sm font-semibold text-text-muted">{t('Ryzyko suszy: brak oceny')}</p>
        <p className="text-base leading-6">{t(sentence)}</p>
      </div>
    )
  const r = RISK[risk]
  return (
    <div className={cn('flex overflow-hidden rounded-xl', r.soft)} role="status">
      <span className={cn('w-1.5 shrink-0', r.bar)} aria-hidden />
      <div className="min-w-0 px-4 py-3">
        {v ? (
          // dziś (status) i na lata (werdykt) w jednej linii – żeby „woda w normie” obok „wysokie ryzyko” nie wyglądało na sprzeczność
          <p className="flex flex-wrap items-center gap-x-1.5 text-sm leading-5 text-text">
            {now !== 'no_data' && (
              <span className="flex items-center gap-1.5">
                <NowIcon className={cn('size-4 shrink-0', STATUS[now].fg)} aria-hidden />
                <span>
                  <b className="font-semibold">{t('Teraz:')}</b> {t(NOW_LABEL[now])}
                </span>
                <span className="text-text-muted" aria-hidden>
                  ·
                </span>
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <span className={cn('size-2.5 shrink-0 rounded-full', r.bar)} aria-hidden />
              <span>
                <b className="font-semibold">{t('Na dłuższą metę:')}</b> {t(LONG_TERM_LABEL[v.level])}
              </span>
            </span>
          </p>
        ) : (
          <p className="flex items-center gap-1.5 text-sm leading-5 font-semibold text-text">
            <span className={cn('size-2.5 rounded-full', r.bar)} aria-hidden />
            {t(r.label)}
          </p>
        )}
        <p className="text-base leading-6 font-semibold text-text">{t(sentence)}</p>
      </div>
    </div>
  )
}
