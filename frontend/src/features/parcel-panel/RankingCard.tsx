import { ChevronDown, CircleAlert, CircleCheck, CircleX, TreeDeciduous, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import type { CropSuggestion, CropSuggestions, PerennialSuggestion, SuggestionCategory } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** ✅ / 🟡 / ❌ – te same kolory co werdykt i raport PDF. */
const CAT: Record<SuggestionCategory, { icon: LucideIcon; color: string; label: string }> = {
  polecane: { icon: CircleCheck, color: '#5BB37F', label: 'polecane' },
  mozliwe: { icon: CircleAlert, color: '#E8B931', label: 'możliwe' },
  odradzane: { icon: CircleX, color: '#C8453B', label: 'odradzane' },
}

const num = (v: number | null | undefined, digits = 1) =>
  v == null ? null : v.toLocaleString('pl-PL', { minimumFractionDigits: digits, maximumFractionDigits: digits })

/** „typowo 3,2 t/ha · ≈ 3,2 t z pola” – liczby z rankingu, bez nawadniania. */
function YieldLine({ s, area }: { s: CropSuggestion | PerennialSuggestion; area: number | null }) {
  const { t } = useLang()
  const typ = num(s.yield_typical_t_ha)
  if (!typ) return <span className="text-text-muted">{t('Brak danych o plonie')}</span>
  return (
    <span>
      {t('typowo')} <b className="tabular">{typ} t/ha</b>
      {s.total_typical_t != null && area != null && <span className="text-text-muted"> · {t('≈ {t} t z pola', { t: num(s.total_typical_t) ?? '' })}</span>}
    </span>
  )
}

/** Szczegóły jednej uprawy: słaby rok, ryzyko, płodozmian, uwagi. */
function Details({ s }: { s: CropSuggestion | PerennialSuggestion }) {
  const { t } = useLang()
  const rot = 'rotation' in s ? s.rotation : null
  const notes = 'notes' in s ? (s.notes ?? []) : []
  return (
    <ul className="mt-1.5 space-y-1 text-sm leading-5 text-text-muted">
      {s.yield_weak_t_ha != null && (
        <li>
          {t('w słabym roku ({rok}): {t} t/ha', { rok: s.weak_year, t: num(s.yield_weak_t_ha) ?? '' })}
          {s.total_weak_t != null && ` · ${t('≈ {t} t z pola', { t: num(s.total_weak_t) ?? '' })}`}
        </li>
      )}
      <li>{t('susza obniża plon o ponad 20% w {n} na {of} lat', { n: s.drought_risk_years, of: s.years_simulated })}</li>
      {rot?.notes?.map((n) => (
        <li key={n} className={cn(rot.status === 'naruszenie' && 'text-danger', rot.status === 'ostrzezenie' && 'text-[#875a12]')}>
          {t(n)}
        </li>
      ))}
      {notes.map((n) => (
        <li key={n}>{t(n)}</li>
      ))}
    </ul>
  )
}

function Row({ s, area }: { s: CropSuggestion; area: number | null }) {
  const { t } = useLang()
  const [open, setOpen] = useState(false)
  const c = CAT[s.category]
  const Icon = c.icon
  return (
    <li className="py-2.5">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-2.5 text-left">
        <Icon className="mt-0.5 size-5 shrink-0" style={{ color: c.color }} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block text-base leading-6 font-semibold">
            <span className="sr-only">{t(c.label)}: </span>
            {t(s.label)}
          </span>
          <span className="block text-sm leading-5">
            <YieldLine s={s} area={area} />
          </span>
          {open && <span className="mt-1 block text-sm leading-5 text-text-muted">{t(s.reason)}</span>}
          {open && <Details s={s} />}
        </span>
        <ChevronDown className={cn('mt-1 size-4 shrink-0 text-text-muted transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
    </li>
  )
}

/**
 * „Co tu posiać?” (B3, kontrakt `suggestions`): ranking upraw polowych ✅ / 🟡 / ❌ na pogodzie z 10 lat –
 * domyślnie 3 najlepsze, reszta pod „Pokaż cały ranking”. Każda: typowy plon t/ha i tony z pola, jedno zdanie
 * powodu; po kliknięciu słaby rok, „X na 10 lat”, płodozmian. Wieloletnie – osobno, zwinięte, bez ✅/❌.
 * Plony zawsze bez nawadniania – to orientacja, nie prognoza.
 */
export function RankingCard({ suggestions, top = 3 }: { suggestions: CropSuggestions; top?: number }) {
  const { t } = useLang()
  const [all, setAll] = useState(false)
  const [perennialsOpen, setPerennialsOpen] = useState(false)
  const items = suggestions.groups.flatMap((g) => g.items)
  const shown = all ? items : items.slice(0, top)
  const area = suggestions.area?.value_ha ?? null
  const per = suggestions.perennials
  const counts = (['polecane', 'mozliwe', 'odradzane'] as const).map((k) => [k, items.filter((i) => i.category === k).length] as const)

  return (
    <section aria-label={t('Co tu posiać?')} className="rounded-xl border bg-surface">
      <header className="px-4 pt-3.5">
        <h3 className="font-display text-lg leading-6 font-semibold">{t('Co tu posiać?')}</h3>
        <p className="text-sm leading-5 text-text-muted">{all ? t('Wszystkie uprawy polowe, od najlepszej') : t('Najlepsze dla tej ziemi i pogody z 10 lat')}</p>
      </header>

      <ul className="divide-y px-4">
        {shown.map((s) => (
          <Row key={s.crop_id} s={s} area={area} />
        ))}
      </ul>

      {suggestions.not_recommended && (
        <p className="border-t px-4 py-2.5 text-sm leading-5">
          <b className="text-danger">{t('Nie siej:')}</b>{' '}
          {suggestions.not_recommended.length
            ? suggestions.not_recommended.map((n) => `${t(n.label).toLowerCase()} (${t(n.reason)})`).join('; ')
            : t('żadna z popularnych upraw nie jest tu odradzana')}
        </p>
      )}

      {items.length > top && (
        <button
          type="button"
          aria-expanded={all}
          onClick={() => setAll((a) => !a)}
          className="flex min-h-11 w-full items-center justify-between gap-2 border-t px-4 text-sm font-semibold text-brand hover:bg-sage-soft"
        >
          <span>{all ? t('Pokaż tylko najlepsze') : t('Pokaż cały ranking ({n} upraw)', { n: items.length })}</span>
          {!all && (
            <span className="flex items-center gap-2 font-normal text-text-muted">
              {counts.map(([k, n]) => {
                const Icon = CAT[k].icon
                return n ? (
                  <span key={k} className="flex items-center gap-0.5" title={t(CAT[k].label)}>
                    <Icon className="size-3.5" style={{ color: CAT[k].color }} aria-hidden /> {n}
                  </span>
                ) : null
              })}
            </span>
          )}
        </button>
      )}

      {all && per && per.items.length > 0 && (
        <div className="border-t">
          <button
            type="button"
            aria-expanded={perennialsOpen}
            onClick={() => setPerennialsOpen((o) => !o)}
            className="flex min-h-11 w-full items-center gap-2 px-4 text-left text-sm font-semibold hover:bg-surface-2"
          >
            <TreeDeciduous className="size-4 text-brand" aria-hidden />
            <span className="flex-1">{t(per.label)}</span>
            <ChevronDown className={cn('size-4 text-text-muted transition-transform', perennialsOpen && 'rotate-180')} aria-hidden />
          </button>
          {perennialsOpen && (
            <div className="space-y-2 px-4 pb-3">
              <p className="text-sm leading-5 text-text-muted">{t(per.note)}</p>
              <ul className="divide-y">
                {per.items.map((p) => (
                  <li key={p.crop_id} className="py-2">
                    <p className="text-base leading-6 font-semibold">{t(p.label)}</p>
                    <p className="text-sm leading-5">
                      <YieldLine s={p} area={area} />
                    </p>
                    <p className="text-sm leading-5 text-text-muted">{t(p.note)}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <footer className="space-y-1.5 border-t px-4 py-2.5 text-xs leading-4 text-text-muted">
        <p>{t(suggestions.note)}</p>
        <SourceTag
          kind={suggestions.source_tag.kind}
          date={suggestions.source_tag.date ? formatDatePl(suggestions.source_tag.date) : undefined}
          title={suggestions.source_tag.source ?? undefined}
        />
      </footer>
    </section>
  )
}
