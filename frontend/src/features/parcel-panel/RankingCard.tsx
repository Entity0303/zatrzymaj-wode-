import { ChevronDown, CircleAlert, CircleCheck, CircleX, TreeDeciduous, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import type { CropSuggestion, CropSuggestions, PerennialSuggestion, PriceNow, SuggestionCategory } from '@/api/types'
import { RevenueCell, type RevenueExtras } from './RevenueCell'
import { hasRevenue, priceNowSource } from '@/lib/revenue'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, formatHa, formatNum } from '@/lib/format'
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

/** „10–16.11.2026” → „10–16.11” */
const shortWeek = (w: string) => w.replace(/\.\d{4}$/, '')

/** Szczegóły jednej uprawy: słaby rok, ryzyko, płodozmian, uwagi; cena za tonę (przychód – kolumna obok). */
function Details({ s, priceNow }: { s: CropSuggestion | PerennialSuggestion; priceNow?: PriceNow | null }) {
  const { t } = useLang()
  const rot = 'rotation' in s ? s.rotation : null
  const notes = 'notes' in s ? (s.notes ?? []) : []
  const rev = 'revenue' in s && hasRevenue(s.revenue) ? s.revenue : null
  return (
    <ul className="mt-1.5 space-y-1 text-sm leading-5 text-text-muted">
      {rev && Number.isFinite(rev.price_zl_t) && rev.price_zl_t > 0 && (
        <li>
          {t('przychód: {p} zł/t × plon z {area} ha (bez kosztów i dopłat)', { p: formatNum(rev.price_zl_t, 0), area: formatHa(rev.for_area_ha) })}
          {priceNow && ` · ${t('cena teraz: {p} zł/t ({src}, {week})', { p: formatNum(priceNow.zl_t, 0), src: priceNow.source.split(' ')[0], week: shortWeek(priceNow.week) })}`}
        </li>
      )}
      {s.yield_weak_t_ha != null && (
        <li>
          {t('w słabym roku ({rok}): {t} t/ha', { rok: s.weak_year, t: num(s.yield_weak_t_ha) ?? '' })}
          {s.total_weak_t != null && ` · ${t('≈ {t} t z pola', { t: num(s.total_weak_t) ?? '' })}`}
        </li>
      )}
      <li>{t('susza obniża plon o ponad 20% w {n} z {of} lat', { n: s.drought_risk_years, of: s.years_simulated })}</li>
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

function Row({ s, area, priceNow }: { s: CropSuggestion; area: number | null; priceNow?: PriceNow | null }) {
  const { t } = useLang()
  const [open, setOpen] = useState(false)
  const c = CAT[s.category]
  const Icon = c.icon
  return (
    <li className="py-2.5">
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-2.5 text-left">
        <Icon className="mt-0.5 size-5 shrink-0" style={{ color: c.color }} aria-hidden />
        <span className="min-w-0 flex-1">
          {/* F8: kolumny „uprawa i plon” | „przychód z pola”; na telefonie przychód pod plonem */}
          <span className="block sm:grid sm:grid-cols-[minmax(0,1fr)_8.5rem] sm:gap-3">
            <span className="block min-w-0">
              <span className="block text-base leading-6 font-semibold">
                <span className="sr-only">{t(c.label)}: </span>
                {t(s.label)}
              </span>
              <span className="block text-sm leading-5">
                <YieldLine s={s} area={area} />
              </span>
            </span>
            <RevenueCell
              revenue={s.revenue}
              note={(s as CropSuggestion & RevenueExtras).revenue_note}
              priceSource={(s as CropSuggestion & RevenueExtras).price_source}
              priceNow={priceNow}
              className="mt-0.5 sm:mt-0 sm:pt-0.5 sm:text-right" />
          </span>
          {open && <span className="mt-1 block text-sm leading-5 text-text-muted">{t(s.reason)}</span>}
          {open && <Details s={s} priceNow={priceNow} />}
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
export function RankingCard({ suggestions, top = 3, priceNow }: { suggestions: CropSuggestions; top?: number; /** F3: ceny bieżące */ priceNow?: PriceNow[] | null }) {
  const { t } = useLang()
  const [all, setAll] = useState(false)
  const [perennialsOpen, setPerennialsOpen] = useState(false)
  const items = suggestions.groups.flatMap((g) => g.items)
  const shown = all ? items : items.slice(0, top)
  const area = suggestions.area?.value_ha ?? null
  const per = suggestions.perennials
  const counts = (['polecane', 'mozliwe', 'odradzane'] as const).map((k) => [k, items.filter((i) => i.category === k).length] as const)
  // F8: źródło cen (np. „GUS – ceny skupu, woj. podlaskie, 2023–2025”) – bez powtórzeń; brak pola = nic
  const priceSources = [...new Set(shown.map((s) => (hasRevenue(s.revenue) ? s.revenue.price_source?.trim() : '')).filter(Boolean))]
  // cena bieżąca ZSRIR dla upraw bez ceny GUS w tabeli: „rzepak – cena z lipca 2026 (ZSRIR)”
  const nowSources = shown
    .filter((s) => !hasRevenue(s.revenue))
    .flatMap((s) => {
      // F9: podpis z API (pozycja rankingu albo cena bieżąca), a bez niego – składany z tygodnia i źródła
      const api = (s as CropSuggestion & RevenueExtras).price_source?.trim()
      const p = priceNow?.find((x) => x.crop_id === s.crop_id)
      const src = api ? t(api) : p ? priceNowSource(p, t) : null
      return src ? [`${t(s.label).toLowerCase()} – ${src}`] : []
    })
  const allSources = [...priceSources.map((x) => t(x)), ...nowSources]

  return (
    <section aria-label={t('Co tu posiać?')} className="tabular rounded-xl border bg-surface">
      <header className="px-4 pt-3.5">
        <h3 className="font-display text-lg leading-6 font-semibold">{t('Co tu posiać?')}</h3>
        <p className="text-sm leading-5 text-text-muted">{all ? t('Wszystkie uprawy polowe, od najlepszej') : t('Najlepsze dla tej ziemi i pogody z 10 lat')}</p>
      </header>

      {/* nagłówki kolumn – tylko obok siebie (od 640 px) */}
      <p aria-hidden className="mt-2 hidden grid-cols-[minmax(0,1fr)_8.5rem] gap-3 pr-[42px] pl-[46px] text-xs leading-4 font-semibold tracking-wide text-text-muted uppercase sm:grid">
        <span>{t('Uprawa i plon')}</span>
        <span className="text-right">{t('Przychód z pola')}</span>
      </p>
      <ul className="divide-y px-4">
        {shown.map((s) => (
          <Row key={s.crop_id} s={s} area={area} priceNow={priceNow?.find((p) => p.crop_id === s.crop_id)} />
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
        {allSources.length > 0 && <p>{t('Ceny: {src}. Przychód bez kosztów i dopłat.', { src: allSources.join('; ') })}</p>}
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
