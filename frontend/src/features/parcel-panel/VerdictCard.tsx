import { Check, CircleAlert, CircleCheck, CircleX, Droplet, X, type LucideIcon } from 'lucide-react'
import type { Verdict, VerdictStatementLevel } from '@/api/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useLang } from '@/lib/i18n'

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
 * Deterministyczny – liczy backend, bez AI.
 */
export function VerdictCard({ verdict, compact }: { verdict: Verdict; compact?: boolean }) {
  const { t } = useLang()
  const head = LEVEL[verdict.level]
  const HeadIcon = head.icon
  const good = verdict.crops_good ?? []
  const bad = verdict.crops_bad ?? []
  return (
    <section aria-label={t('Werdykt działki')} className="overflow-hidden rounded-xl border" style={{ borderColor: head.color }}>
      <header className="flex items-start gap-3 px-4 pt-4 pb-3" style={{ background: head.soft }}>
        <HeadIcon className="mt-0.5 size-7 shrink-0" style={{ color: head.color }} aria-hidden />
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Werdykt')}</p>
          <h3 className="font-display text-xl leading-7 font-semibold">{t(verdict.headline)}</h3>
        </div>
      </header>

      <ul className="space-y-2.5 px-4 py-3">
        {verdict.statements.map((s, i) => {
          const l = LEVEL[s.level]
          const Icon = l.icon
          return (
            <li key={`${s.kind}-${i}`} className="flex gap-2.5 text-sm leading-5">
              <Icon className="mt-px size-[18px] shrink-0" style={{ color: l.color }} aria-hidden />
              <span>
                <span className="sr-only">{t(l.label)}: </span>
                {t(s.text)}
              </span>
            </li>
          )
        })}
      </ul>

      {(good.length > 0 || bad.length > 0) && (
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

      {verdict.note && !compact && <p className="border-t px-4 py-2.5 text-xs leading-4 text-text-muted">{t(verdict.note)}</p>}
    </section>
  )
}
