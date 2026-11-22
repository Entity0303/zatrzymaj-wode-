import { CircleAlert, CircleCheck, CircleX, TreeDeciduous, type LucideIcon } from 'lucide-react'
import type { ChoiceItem, CropSuggestions, SuggestionCategory } from '@/api/types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const CAT: Record<SuggestionCategory, { icon: LucideIcon; cls: string }> = {
  polecane: { icon: CircleCheck, cls: 'bg-ok-soft text-ok' },
  mozliwe: { icon: CircleAlert, cls: 'bg-amber-soft text-[#875a12]' },
  odradzane: { icon: CircleX, cls: 'bg-danger-soft text-danger' },
}

const num = (v: number | null | undefined) => (v == null ? null : v.toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 }))

function Choice({ c }: { c: ChoiceItem }) {
  const { t } = useLang()
  const cat = c.category ? CAT[c.category] : null
  const Icon = cat?.icon ?? TreeDeciduous
  // płodozmian: nie powtarzaj, gdy `why` już o nim mówi
  const rotation = (c.rotation?.notes ?? []).filter(() => !/po sobie|przerwy|rosła tu/i.test(c.why))
  return (
    <li className="space-y-1.5 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-base leading-6 font-semibold">{t(c.label)}</span>
        <span className={cn('inline-flex h-6 items-center gap-1 rounded-full px-2 text-xs font-semibold', cat?.cls ?? 'bg-surface-2 text-text-muted')}>
          <Icon className="size-3.5" aria-hidden />
          {t(c.category_label ?? (c.perennial ? 'uprawa wieloletnia' : ''))}
        </span>
      </div>
      {c.group_note && <p className="text-sm leading-5 text-text-muted">{t(c.group_note)}</p>}
      <ul className="space-y-0.5 text-sm leading-5">
        {c.yield_typical_t_ha != null && (
          <li>
            {t('Typowo')} <b className="tabular">{num(c.yield_typical_t_ha)} t/ha</b>
            {c.total_typical_t != null && <span className="text-text-muted"> · {t('≈ {t} t z pola', { t: num(c.total_typical_t) ?? '' })}</span>}
          </li>
        )}
        {c.yield_weak_t_ha != null && c.weak_year != null && (
          <li className="text-text-muted">{t('w słabym roku ({rok}): {t} t/ha', { rok: c.weak_year, t: num(c.yield_weak_t_ha) ?? '' })}</li>
        )}
        <li className="text-text-muted">{t('susza obniża plon o ponad 20% w {n} z {of} lat', { n: c.drought_risk_years, of: c.years_simulated })}</li>
      </ul>
      <p className="text-sm leading-5">{t(c.why)}</p>
      {rotation.map((n) => (
        <p key={n} className={cn('text-sm leading-5', c.rotation.status === 'naruszenie' ? 'text-danger' : 'text-text-muted')}>
          {t('Płodozmian:')} {t(n)}
        </p>
      ))}
    </li>
  )
}

/**
 * „Twój wybór” (A5e): ocena upraw, które rolnik planuje posiać (`planned_crops`) – jedno zdanie oceny,
 * karta na każdą uprawę (kategoria, plon, słaby rok, ryzyko, jedno zdanie „dlaczego”, płodozmian),
 * a pod spodem „Lepsze możliwości” (tylko gdy są). Bez wyboru – nic (wtedy ranking „Co tu posiać?”).
 */
export function ChoiceCard({ suggestions }: { suggestions: CropSuggestions }) {
  const { t } = useLang()
  const choice = suggestions.choice ?? []
  const alt = suggestions.alternatives ?? []
  if (!choice.length && !suggestions.choice_notes?.length) return null
  return (
    <section aria-label={t('Twój wybór')} className="space-y-3 rounded-xl border bg-surface p-4">
      <header>
        <h3 className="text-lg leading-6 font-semibold">{t('Twój wybór')}</h3>
        {suggestions.choice_summary && <p className="text-base leading-6 font-semibold text-brand-dark">{t(suggestions.choice_summary)}</p>}
      </header>
      <ul className="space-y-2">
        {choice.map((c) => (
          <Choice key={`${c.requested_id ?? ''}-${c.crop_id}`} c={c} />
        ))}
      </ul>
      {suggestions.choice_notes?.map((n) => (
        <p key={n} className="text-xs leading-4 text-text-muted">
          {t(n)}
        </p>
      ))}
      {alt.length > 0 && (
        <div className="space-y-2 border-t pt-3">
          <h4 className="text-sm font-semibold">{t('Lepsze możliwości')}</h4>
          <ul className="space-y-2">
            {alt.map((a) => (
              <li key={a.crop_id} className="text-sm leading-5">
                <span className="flex flex-wrap items-center gap-2">
                  <span className={cn('rounded-full px-2 text-xs font-semibold', a.relation === 'lepsza' ? 'bg-ok-soft text-ok' : 'bg-sage-soft text-brand-dark')}>
                    {t(a.relation)}
                  </span>
                  <b>{t(a.label)}</b>
                  {a.yield_typical_t_ha != null && <span className="text-text-muted">{t('typowo')} {num(a.yield_typical_t_ha)} t/ha</span>}
                  <span className="text-text-muted">· {t('strata w {n} z {of} lat', { n: a.drought_risk_years, of: a.years_simulated })}</span>
                </span>
                <span className="block text-text-muted">{t(a.why)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
