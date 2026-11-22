import { fmtNumRange, fmtRisk, riskSpan } from '@/lib/ranges'
import { ChevronDown, PencilLine } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { AnalysisResponse, CropSuggestion, SuggestionCategory, VerdictStatementLevel } from '@/api/types'
import { RevenueCell, type RevenueExtras } from '@/features/parcel-panel/RevenueCell'
import { RankingCard } from '@/features/parcel-panel/RankingCard'
import { CropLine } from '@/features/parcel-panel/CropLine'
import { formatNum } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { priceSourceList } from '@/lib/revenue'
import { useSettings } from '@/lib/storage'
import { cn } from '@/lib/utils'
import { LevelDot } from './LevelDot'
import { PassportCard } from './PassportCard'
import { PassportSection } from './PassportSection'

const CAT_LEVEL: Record<SuggestionCategory, VerdictStatementLevel> = { polecane: 'ok', mozliwe: 'warn', odradzane: 'bad' }

/**
 * F6: zakres lat z dużą stratą, gdy backend go poda (pole opcjonalne – typ lokalny; dziś jest tylko liczba).
 * Przykład: [1, 3] → „1–3 na 10 lat”.
 */

/** Ryzyko suszy jako 10 kresek (wypełnione = lata ze stratą > 20%). */
/** 10 kresek: zamalowane do min, jaśniejsze (ten sam kolor, 40%) do max – F21 widełki ryzyka. */
function RiskTicks({ n, max = n, of }: { n: number; max?: number; of: number }) {
  const total = Math.max(1, Math.min(10, of || 10))
  const color = max >= 5 ? 'bg-pp-bad' : max >= 3 ? 'bg-pp-risk' : 'bg-pp-warn'
  return (
    <span className="flex gap-[3px]" aria-hidden>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={cn('h-3.5 w-1.5 rounded-sm', i < n ? color : i < max ? cn(color, 'opacity-40') : 'bg-paper-line')} />
      ))}
    </span>
  )
}

const num = (v: number | null | undefined, d = 1) => (v == null ? null : formatNum(v, d))

/**
 * 3. Co tu posiać (F6): TABELA rankingu – pierwsze 5 + „Pokaż wszystkie”. Kolumny: uprawa (kółko statusu + krótki
 * powód) | plon typowy t/ha (+ tony z pola) | słaby rok (+ który) | ryzyko suszy (10 kresek + „3 na 10 lat”) |
 * przychód z pola (typowy, pod spodem słaby rok; brak ceny – szary powód z API). Na telefonie każdy wiersz jako
 * karta (bez przewijania w bok). Pod tabelą jedno zdanie o źródle cen i „bez kosztów”. „Podaj, co rosło” – ten sam
 * formularz co w panelu działki. Tryb Doradca – „Szczegóły” z dotychczasową listą (płodozmian, uwagi, wieloletnie).
 */
export function CropTableSection({ analysis, refineForm }: { analysis: AnalysisResponse; refineForm?: ReactNode }) {
  const { t } = useLang()
  const [settings] = useSettings()
  const [all, setAll] = useState(false)
  const [form, setForm] = useState(false)
  const [details, setDetails] = useState(false)
  const s = analysis.suggestions
  if (!s) return null
  const items = s.groups.flatMap((g) => g.items)
  if (!items.length) return null
  const shown = all ? items : items.slice(0, 5)
  const sources = priceSourceList(shown, analysis.price_now, t)
  const seasons = s.seasons?.length ? `${Math.min(...s.seasons)}–${Math.max(...s.seasons)}` : null

  return (
    <PassportSection
      id="pp-posiac"
      title={t('Co tu posiać')}
      aside={
        refineForm && (
          <button
            type="button"
            aria-expanded={form}
            onClick={() => setForm((f) => !f)}
            className="inline-flex h-10 items-center gap-2 rounded-full border border-paper-line bg-surface px-4 text-sm font-semibold text-pp-brand hover:bg-sage-soft"
          >
            <PencilLine className="size-4" aria-hidden /> {t('Podaj, co rosło')}
          </button>
        )
      }
    >
      {form && refineForm}
      <PassportCard className="@container p-0 md:p-0">
        {/* nagłówki kolumn – kontener od 560 px (container query); węziej lista kart bez nagłówków */}
        <div className="hidden grid-cols-[minmax(0,2.2fr)_1fr_1fr_1.25fr_1.3fr] gap-4 border-b border-paper-line px-5 py-3 text-xs font-semibold tracking-wide text-text-muted uppercase @min-[560px]:grid">
          <span>{t('Uprawa')}</span>
          <span>{t('Plon typowy')}</span>
          <span>{t('Słaby rok')}</span>
          <span>{t('Ryzyko suszy')}</span>
          <span className="text-right">{t('Przychód z pola')}</span>
        </div>
        <ul className="divide-y divide-paper-line">
          {shown.map((it) => {
            // F21: zakresy z wariantów (A21) – gdy min = max, jedna liczba
            const rs = riskSpan(it)
            const risk = fmtRisk(it)
            const typ = fmtNumRange(it.yield_typical_range, it.yield_typical_t_ha)
            const weak = fmtNumRange(it.yield_weak_range, it.yield_weak_t_ha)
            return (
              <li key={it.crop_id} className="px-5 py-3.5">
                <div className="flex @min-[560px]:hidden">
                  <CropLine s={it} priceNow={analysis.price_now?.find((p) => p.crop_id === it.crop_id)} />
                </div>
                <div className="hidden grid-cols-[minmax(0,2.2fr)_1fr_1fr_1.25fr_1.3fr] items-start gap-4 @min-[560px]:grid">
                <div className="flex min-w-0 gap-2.5">
                  <LevelDot level={CAT_LEVEL[it.category]} className="mt-0.5" />
                  <div className="min-w-0">
                    <p className="text-base leading-6 font-semibold">{t(it.label)}</p>
                    <p className="text-sm leading-5 text-text-muted">{t(it.reason)}</p>
                  </div>
                </div>
                <div className="tabular text-sm leading-5">
                  
                  {typ ? <b className="font-semibold">{typ} t/ha</b> : <span className="text-text-muted">{t('brak danych')}</span>}
                  {it.total_typical_t != null && <span className="block text-text-muted">{t('≈ {t} t z pola', { t: num(it.total_typical_t) ?? '' })}</span>}
                </div>
                <div className="tabular text-sm leading-5">
                  
                  {weak ? <>{weak} t/ha</> : <span className="text-text-muted">—</span>}
                  {it.weak_year ? <span className="block text-text-muted">{t('({rok})', { rok: it.weak_year })}</span> : null}
                </div>
                <div className="text-sm leading-5">
                  
                  <span className="inline-flex flex-wrap items-center gap-2">
                    <RiskTicks n={rs.min} max={rs.max} of={it.years_simulated} />
                    <span className="tabular">{t('{n} na {of} lat', { n: risk, of: it.years_simulated || 10 })}</span>
                  </span>
                </div>
                <div className="text-right">
                  <RevenueCell
                    revenue={it.revenue}
                    note={(it as CropSuggestion & RevenueExtras).revenue_note}
                    priceSource={(it as CropSuggestion & RevenueExtras).price_source}
                    priceNow={analysis.price_now?.find((p) => p.crop_id === it.crop_id)}
                  />
                </div>
                </div>
              </li>
            )
          })}
        </ul>
        {items.length > 5 && (
          <button
            type="button"
            aria-expanded={all}
            onClick={() => setAll((a) => !a)}
            className="flex min-h-11 w-full items-center justify-center gap-1.5 border-t border-paper-line text-sm font-semibold text-pp-brand hover:bg-sage-soft"
          >
            {t(all ? 'Pokaż tylko 5 najlepszych' : 'Pokaż wszystkie ({n})', { n: items.length })}
            <ChevronDown className={cn('size-4 transition-transform', all && 'rotate-180')} aria-hidden />
          </button>
        )}
      </PassportCard>
      {s.not_recommended && s.not_recommended.length > 0 && (
        <p className="text-sm leading-5">
          <b className="text-pp-bad">{t('Nie siej:')}</b> {s.not_recommended.map((n) => `${t(n.label).toLowerCase()} (${t(n.reason)})`).join('; ')}
        </p>
      )}
      <p className="text-sm leading-5 text-text-muted">
        {sources.length > 0 && <>{t('Ceny: {src}.', { src: sources.join('; ') })} </>}
        {t('Przychód bez kosztów i dopłat.')} {seasons && t('Plony bez nawadniania, na pogodzie z sezonów {s}.', { s: seasons })}
      </p>
      {settings.mode === 'doradca' && (
        <div>
          <button type="button" aria-expanded={details} onClick={() => setDetails((d) => !d)} className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-pp-brand">
            {t('Szczegóły')} <ChevronDown className={cn('size-4 transition-transform', details && 'rotate-180')} aria-hidden />
          </button>
          {details && <RankingCard suggestions={s} priceNow={analysis.price_now} top={items.length} />}
        </div>
      )}
    </PassportSection>
  )
}
