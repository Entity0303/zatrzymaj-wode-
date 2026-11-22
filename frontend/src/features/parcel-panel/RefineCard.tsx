import { ChevronDown, Plus, Sprout, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { CropId, CultivatedArea } from '@/api/types'
import { Select, SelectContent, SelectItem, SelectSeparator, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PeriodPicker } from '@/features/period/PeriodPicker'
import { HISTORY_CROPS, HISTORY_UNKNOWN, historyLabel } from '@/lib/crops'
import { formatArea, formatDatePl, formatDayMonth, formatHa } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useMediaQuery } from '@/lib/hooks'
import { CropField } from './CropField'

const YEARS = ['rok temu', '2 lata temu', '3 lata temu'] as const

/** Pole powierzchni: zatwierdzane po wyjściu z pola / Enter (każda zmiana to nowe przeliczenie). */
function AreaInput({ value, onCommit }: { value: number | null; onCommit: (ha: number | null) => void }) {
  const { t } = useLang()
  const [text, setText] = useState(value != null ? formatHa(value) : '')
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    setSeen(value)
    setText(value != null ? formatHa(value) : '')
  }
  const commit = () => {
    const v = parseFloat(text.replace(',', '.').replace(/\s/g, ''))
    const next = Number.isFinite(v) && v > 0 ? Math.round(v * 100) / 100 : null
    if (next !== value) onCommit(next)
    else setText(value != null ? formatHa(value) : '')
  }
  return (
    <label className="flex h-11 w-full items-center gap-2 rounded-md border bg-surface-2 px-3 focus-within:border-brand">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
        inputMode="decimal"
        aria-label={t('Powierzchnia uprawy w hektarach')}
        className="tabular min-w-0 flex-1 bg-transparent text-base outline-none"
      />
      <span className="text-sm text-text-muted">ha</span>
    </label>
  )
}

/** Etykieta NAD polem, pole na całą szerokość, podpowiedź pod nim. */
function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm leading-5 font-semibold">{label}</p>
      {children}
      {hint && <p className="text-xs leading-4 text-text-muted">{hint}</p>}
    </div>
  )
}

/** Wybór uprawy z listy historii (przedplon, 2–3 lata temu) – „Nie wiem” na górze. */
function HistorySelect({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  const { t } = useLang()
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={label} className="h-11 w-full min-w-0 rounded-md bg-surface-2 text-base data-[size=default]:h-11">
        <span className="min-w-0 truncate text-left">
          <SelectValue>{value === HISTORY_UNKNOWN ? t('Nie wiem') : historyLabel(value)}</SelectValue>
        </span>
      </SelectTrigger>
      <SelectContent className="z-[1500] max-h-80 rounded-xl" position="popper">
        <SelectItem value={HISTORY_UNKNOWN} className="min-h-11 text-base text-text-muted">
          {t('Nie wiem')}
        </SelectItem>
        <SelectSeparator />
        {HISTORY_CROPS.map((c) => (
          <SelectItem key={c.id} value={c.id} className="min-h-11 text-base">
            {t(c.label)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/**
 * „Twoja działka” (F-MASTER A2 – obowiązkowy krok KOWR: rolnik wybiera aktualną uprawę). Formularz OD RAZU
 * rozwinięty, etykiety nad polami, pola na całą szerokość: „Co rośnie teraz?” (uprawa), „Co rosło w poprzednim
 * sezonie?” (przedplon = historia pola rok temu), „Data siewu” (opcjonalnie – backend nie przyjmuje daty siewu,
 * więc ustawia okres „od siewu” od tej daty: `date_from`), „Okres analizy” (30 dni / od siewu / sezon / własny).
 * Drugorzędne (plan upraw, 2–3 lata temu, powierzchnia) – w zwijanej linii „Dodatkowe”. Bez uprawy karta wyróżniona
 * („Wybierz uprawę – wynik będzie dokładniejszy”). Karta nie zwija się sama i nie jest odmontowywana przy przeliczaniu
 * (F13) – pola nie tracą fokusu, zmiany liczone po ok. 400 ms.
 */
export function RefineCard({
  crop,
  onCropChange,
  history,
  onHistoryChange,
  area,
  onAreaChange,
  rotationHint,
  planned = [],
  onPlannedChange,
  planOptions = [],
  period = null,
  onPeriodChange,
  sowing = null,
  onSowingChange,
  typicalSowing = null,
  sowingNote = null,
  asOf,
  historical,
}: {
  /** A5e: „Co planujesz posiać?” – do 3 upraw lub grup */
  planned?: string[]
  onPlannedChange?: (p: string[]) => void
  /** uprawy z rankingu + grupy („Zboża ozime”) */
  planOptions?: { id: string; label: string }[]
  crop: CropId | null
  onCropChange: (c: CropId | null) => void
  /** indeks 0 = rok temu; 'nie_wiem' albo crop_id */
  history: string[]
  onHistoryChange: (h: string[]) => void
  /** powierzchnia z rankingu (wpisana albo oszacowana) */
  area: CultivatedArea | null
  onAreaChange: (ha: number | null) => void
  rotationHint?: string | null
  /** okres analizy (znacznik lib/period.ts) – ten sam wybór co w paszporcie */
  period?: string | null
  onPeriodChange?: (p: string | null) => void
  /** data siewu wpisana przez rolnika (RRRR-MM-DD) */
  sowing?: string | null
  onSowingChange?: (d: string | null) => void
  /** typowy początek sezonu uprawy z analizy (crop_season.season_start) – podpowiedź */
  typicalSowing?: string | null
  /** F21: uwaga z analizy o dacie siewu (crop_season.sowing_note), np. poza typowym zakresem */
  sowingNote?: string | null
  /** data analizy – granice pól daty, okres */
  asOf?: string
  /** data analizy w przeszłości – „Co rosło w dniu analizy?” */
  historical?: boolean
}) {
  const { t } = useLang()
  const [more, setMore] = useState(false)
  const phone = useMediaQuery('(max-width: 767.98px)')
  const extras = [
    planned.length ? t('plan: {n}', { n: planned.map((id) => planOptions.find((o) => o.id === id)?.label ?? id).map((l) => t(l)).join(', ') }) : null,
    history.slice(1).some((h) => h && h !== HISTORY_UNKNOWN) ? t('wcześniejsze lata') : null,
    area ? formatArea(area.value_ha) : null,
    phone && sowing ? t('siew {d}', { d: formatDatePl(sowing) }) : null,
    phone && period ? t('okres') : null,
  ].filter(Boolean)

  const setYear = (i: number, v: string) => {
    const next = [0, 1, 2].map((k) => history[k] || HISTORY_UNKNOWN)
    next[i] = v
    // bez końcowych „nie wiem”
    while (next.length && next[next.length - 1] === HISTORY_UNKNOWN) next.pop()
    onHistoryChange(next)
  }

  // F18: telefon – w formularzu tylko uprawa i przedplon; data siewu i okres w „Dodatkowe” (status + formularz + PDF
  // bez przewijania); komputer bez zmian
  const sowingAndPeriod = (
    <>
      {onSowingChange && (
        <Field
          label={t('Data siewu (opcjonalnie)')}
          hint={
            typicalSowing
              ? t('Typowo ok. {d}. Po wpisaniu liczymy okres „od siewu” od tej daty.', { d: formatDayMonth(typicalSowing) })
              : t('Po wpisaniu liczymy okres „od siewu” od tej daty.')
          }
        >
          <label className="flex h-11 w-full items-center gap-2 rounded-md border bg-surface-2 px-3 focus-within:border-brand">
            <input
              type="date"
              value={sowing ?? ''}
              max={asOf}
              onChange={(e) => onSowingChange(e.target.value || null)}
              aria-label={t('Data siewu')}
              className="tabular min-w-0 flex-1 bg-transparent text-base outline-none"
            />
            {sowing && (
              <button
                type="button"
                onClick={() => onSowingChange(null)}
                aria-label={t('Usuń datę siewu')}
                className="flex size-8 items-center justify-center rounded-full text-text-muted hover:bg-surface"
              >
                <X className="size-4" />
              </button>
            )}
          </label>
          {sowing && sowingNote && <p className="mt-1 text-sm leading-5 text-[#875a12]">{t(sowingNote)}</p>}
        </Field>
      )}

      {onPeriodChange && asOf && (
        <Field
          label={t('Okres analizy')}
          hint={sowing && period === 'od_siewu' ? t('od siewu {d}', { d: formatDatePl(sowing) }) : undefined}
        >
          <PeriodPicker
            value={period}
            onChange={onPeriodChange}
            hasCrop={!!crop}
            asOf={asOf}
            align="left"
            wide
            emptyLabel={t('od początku sezonu uprawy')}
          />
        </Field>
      )}
    </>
  )

  return (
    <section
      aria-label={t('Twoja działka')}
      className={cn('space-y-3.5 rounded-xl border bg-surface p-4', !crop && 'border-brand/60 bg-ok-soft/60 ring-1 ring-brand/20')}
    >
      <h3 className="flex items-center gap-2 text-base leading-6 font-semibold">
        <Sprout className="size-5 shrink-0 text-brand" aria-hidden /> {t('Twoja działka')}
      </h3>
      {!crop && <p className="-mt-2 text-sm leading-5 font-medium text-brand-dark">{t('Wybierz uprawę – wynik będzie dokładniejszy')}</p>}

      <Field label={t(historical ? 'Co rosło w dniu analizy?' : 'Co rośnie teraz?')}>
        <CropField crop={crop} onChange={onCropChange} optional />
      </Field>

      <Field label={t('Co rosło w poprzednim sezonie?')} hint={!history[0] && rotationHint ? t(rotationHint) : undefined}>
        <HistorySelect value={history[0] || HISTORY_UNKNOWN} onChange={(v) => setYear(0, v)} label={t('Co rosło w poprzednim sezonie?')} />
      </Field>

      {!phone && sowingAndPeriod}

      {/* drugorzędne – jedna zwijana linia na dole karty */}
      <div className="border-t pt-2">
        <button
          type="button"
          aria-expanded={more}
          onClick={() => setMore((o) => !o)}
          className="flex min-h-11 w-full items-center gap-2 text-left text-sm font-semibold text-brand"
        >
          <span className="shrink-0">{t('Dodatkowe')}</span>
          <span className="min-w-0 flex-1 truncate font-normal text-text-muted">
            {extras.length ? extras.join(' · ') : t(phone ? 'data siewu, okres, plan, wcześniejsze lata, powierzchnia' : 'plan upraw, wcześniejsze lata, powierzchnia')}
          </span>
          <ChevronDown className={cn('size-4 shrink-0 transition-transform', more && 'rotate-180')} aria-hidden />
        </button>
        {more && (
          <div className="space-y-4 pt-2">
            {phone && sowingAndPeriod}
            {onPlannedChange && planOptions.length > 0 && (
              <Field label={t('Co planujesz posiać?')} hint={t('Ocenimy Twój wybór i podpowiemy lepsze możliwości.')}>
                <div className="flex flex-wrap gap-1.5">
                  {planned.map((id) => (
                    <span key={id} className="inline-flex h-9 items-center gap-1 rounded-full bg-sage-soft pr-1 pl-3 text-sm font-medium text-brand-dark">
                      {t(planOptions.find((o) => o.id === id)?.label ?? id)}
                      <button
                        type="button"
                        onClick={() => onPlannedChange(planned.filter((x) => x !== id))}
                        aria-label={t('Usuń {name}', { name: t(planOptions.find((o) => o.id === id)?.label ?? id) })}
                        className="flex size-7 items-center justify-center rounded-full hover:bg-white/70"
                      >
                        <X className="size-4" />
                      </button>
                    </span>
                  ))}
                  {planned.length < 3 && (
                    <Select value="" onValueChange={(v) => v && onPlannedChange([...planned, v])}>
                      <SelectTrigger
                        aria-label={t('Dodaj uprawę do planu')}
                        className="h-9 w-auto rounded-full border-dashed bg-surface px-3 text-sm data-[size=default]:h-9"
                      >
                        <Plus className="size-4 text-brand" aria-hidden />
                        <span>{t(planned.length ? 'Dodaj' : 'Wybierz do 3 upraw')}</span>
                      </SelectTrigger>
                      <SelectContent className="z-[1500] max-h-80 rounded-xl" position="popper">
                        {planOptions
                          .filter((o) => !planned.includes(o.id))
                          .map((o) => (
                            <SelectItem key={o.id} value={o.id} className="min-h-11 text-base">
                              {t(o.label)}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>
              </Field>
            )}

            {([1, 2] as const).map((i) => (
              <Field key={YEARS[i]} label={t('Co rosło {kiedy}?', { kiedy: t(YEARS[i]) })}>
                <HistorySelect value={history[i] || HISTORY_UNKNOWN} onChange={(v) => setYear(i, v)} label={t('Uprawa {kiedy}', { kiedy: t(YEARS[i]) })} />
              </Field>
            ))}

            <Field
              label={t('Ile hektarów obsiewasz?')}
              hint={area?.estimated ? t('Oszacowanie z granic działki – popraw, jeśli uprawiasz mniej lub więcej.') : undefined}
            >
              <AreaInput value={area?.value_ha ?? null} onCommit={onAreaChange} />
            </Field>
          </div>
        )}
      </div>
    </section>
  )
}
