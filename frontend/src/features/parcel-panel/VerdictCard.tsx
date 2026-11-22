import { ChevronDown, Check, CircleAlert, CircleCheck, CircleX, Droplet, Sprout, X, type LucideIcon } from 'lucide-react'
import type { PrecipSources, Verdict, VerdictStatementLevel } from '@/api/types'
import { useState } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useLang } from '@/lib/i18n'
import { PrecipSourceNote } from './PrecipSourceNote'

/** Kolory werdyktu z kontraktu (A5b-2b) – te same co w raporcie PDF. */
const LEVEL: Record<VerdictStatementLevel, { icon: LucideIcon; color: string; soft: string; label: string }> = {
  ok: { icon: CircleCheck, color: '#5BB37F', soft: 'rgb(91 179 127 / 0.12)', label: 'dobrze' },
  warn: { icon: CircleAlert, color: '#E8B931', soft: 'rgb(232 185 49 / 0.16)', label: 'uwaga' },
  bad: { icon: CircleX, color: '#C8453B', soft: 'rgb(200 69 59 / 0.12)', label: 'źle' },
  info: { icon: Droplet, color: '#2F80C9', soft: 'rgb(47 128 201 / 0.10)', label: 'co zrobić' },
}

/**
 * Werdykt działki „w 10 sekund” (B3, kontrakt `verdict`): nagłówek w kolorze oceny, 4–6 zdań z ikoną poziomu
 * (ok / uwaga / źle / niebieska kropla = co zrobić z wodą), chipy „Siej ✓” i „Nie siej ✕” (powód w dymku), uwaga.
 * Deterministyczny – liczy backend, bez AI. Pod „Opady” – skąd opad (stacja IMGW, zgodność z NASA; A7);
 * „Rośliny” (A11, z satelity) – własna ikona kiełka w kolorze poziomu.
 */
export function VerdictCard({
  verdict,
  compact,
  limit,
  hideCrops,
  bare,
  precip,
}: {
  /** A7: źródła opadu – drobnym tekstem pod pozycją „Opady” */
  precip?: PrecipSources | null
  /** bez nagłówka i ramki – same zdania (nagłówek pokazuje RiskSummary nad zakładkami) */
  bare?: boolean
  verdict: Verdict
  compact?: boolean
  /** ile zdań pokazać od razu (reszta pod „Pokaż wszystko”) */
  limit?: number
  /** bez chipów „Siej / Nie siej” – gdy obok jest ranking „Co tu posiać?” */
  hideCrops?: boolean
}) {
  const { t } = useLang()
  const [all, setAll] = useState(false)
  // przy rankingu obok zdanie o uprawach go powtarza – pomijamy je w skrócie
  const statements = hideCrops ? verdict.statements.filter((s) => s.kind !== 'uprawy') : verdict.statements
  const shown = limit && !all ? statements.slice(0, limit) : statements
  const head = LEVEL[verdict.level]
  const HeadIcon = head.icon
  const good = verdict.crops_good ?? []
  const bad = verdict.crops_bad ?? []
  return (
    <section
      aria-label={t('Werdykt działki')}
      className={bare ? 'rounded-xl border bg-surface' : 'overflow-hidden rounded-xl border'}
      style={bare ? undefined : { borderColor: head.color }}
    >
      {!bare && (
        <header className="flex items-start gap-3 px-4 pt-4 pb-3" style={{ background: head.soft }}>
          <HeadIcon className="mt-0.5 size-7 shrink-0" style={{ color: head.color }} aria-hidden />
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Werdykt')}</p>
            <h3 className="font-display text-xl leading-7 font-bold">{t(verdict.headline)}</h3>
          </div>
        </header>
      )}

      <ul className="space-y-2.5 px-4 py-3">
        {shown.map((s, i) => {
          const l = LEVEL[s.level]
          const Icon = s.kind === 'rosliny' ? Sprout : l.icon
          return (
            <li key={`${s.kind}-${i}`} className="flex gap-2.5 text-sm leading-5">
              <Icon className="mt-px size-[18px] shrink-0" style={{ color: l.color }} aria-hidden />
              <span className="min-w-0">
                <span className="sr-only">{t(l.label)}: </span>
                {s.kind === 'rosliny' && <span className="font-semibold">{t('Rośliny (z satelity):')} </span>}
                {t(s.text)}
                {s.kind === 'opady' && precip && <PrecipSourceNote sources={precip} compact className="mt-1.5" />}
              </span>
            </li>
          )
        })}
      </ul>
      {limit != null && statements.length > limit && (
        <button
          type="button"
          aria-expanded={all}
          onClick={() => setAll((a) => !a)}
          className="-mt-1 flex min-h-10 items-center gap-1 px-4 pb-2 text-sm font-semibold text-brand hover:underline"
        >
          {all ? t('Pokaż mniej') : t('Pokaż wszystko ({n})', { n: statements.length })}
          <ChevronDown className={`size-4 transition-transform ${all ? 'rotate-180' : ''}`} aria-hidden />
        </button>
      )}

      {!hideCrops && (good.length > 0 || bad.length > 0) && (
        <div className="space-y-2 border-t px-4 py-3">
          {good.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-0.5 text-sm font-semibold" style={{ color: LEVEL.ok.color }}>
                {t('Siej')}
              </span>
              {good.map((c) => (
                <span
                  key={c.crop_id}
                  className="inline-flex h-8 items-center gap-1 rounded-full px-3 text-sm font-medium"
                  style={{ background: LEVEL.ok.soft, color: '#2E5B3F' }}
                >
                  <Check className="size-3.5" style={{ color: LEVEL.ok.color }} aria-hidden /> {t(c.label)}
                </span>
              ))}
            </div>
          )}
          {bad.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-0.5 text-sm font-semibold" style={{ color: LEVEL.bad.color }}>
                {t('Nie siej')}
              </span>
              {bad.map((c) => (
                <Tooltip key={c.crop_id}>
                  <TooltipTrigger asChild>
                    <span
                      tabIndex={0}
                      className="inline-flex h-8 items-center gap-1 rounded-full px-3 text-sm font-medium"
                      style={{ background: LEVEL.bad.soft, color: '#8f2f27' }}
                    >
                      <X className="size-3.5" aria-hidden /> {t(c.label)}
                    </span>
                  </TooltipTrigger>
                  {c.reason && <TooltipContent className="max-w-64">{t(c.reason)}</TooltipContent>}
                </Tooltip>
              ))}
            </div>
          )}
        </div>
      )}

      {verdict.note && !compact && !bare && <p className="border-t px-4 py-2.5 text-xs leading-4 text-text-muted">{t(verdict.note)}</p>}
    </section>
  )
}
