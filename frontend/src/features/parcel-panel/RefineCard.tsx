import { ChevronDown, Plus, SlidersHorizontal, Sprout, X } from 'lucide-react'
import { useState } from 'react'
import type { CropId, CultivatedArea } from '@/api/types'
import { Select, SelectContent, SelectItem, SelectSeparator, SelectTrigger, SelectValue } from '@/components/ui/select'
import { HISTORY_CROPS, HISTORY_UNKNOWN, cropLabel, historyLabel } from '@/lib/crops'
import { formatHa, formatArea } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
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

/**
 * „Co rośnie na tej działce?” (F13 – obowiązkowy krok KOWR: rolnik wybiera aktualną uprawę) – na górze panelu,
 * zaraz pod stanem „Teraz / Na dłuższą metę”. Pole uprawy widoczne od razu; bez uprawy karta wyróżniona
 * („Wybierz uprawę – wynik będzie dokładniejszy”), po wyborze jedna linia „Uprawa: pszenica ozima · zmień”.
 * Pod „Więcej szczegółów”: plan upraw, historia pola z 3 lat z „Nie wiem” (`crop_history` → płodozmian,
 * `rotation_hint`) i powierzchnia uprawy (wstępnie z działki, `suggestions.area`) → tony z pola w rankingu.
 * Karta nie jest odmontowywana przy przeliczaniu (F13) – pola nie tracą fokusu.
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
}) {
  const { t } = useLang()
  const known = history.filter((h) => h && h !== HISTORY_UNKNOWN)
  const [open, setOpen] = useState(false)
  // „zmień” przy wybranej uprawie – pole wyboru znów widoczne; po wyborze karta wraca do jednej linii
  const [editing, setEditing] = useState(false)
  const summary = [
    planned.length ? t('plan: {n}', { n: planned.map((id) => planOptions.find((o) => o.id === id)?.label ?? id).map((l) => t(l)).join(', ') }) : null,
    known.length ? t('historia: {n} z 3 lat', { n: known.length }) : null,
    area ? formatArea(area.value_ha) : null,
  ].filter(Boolean)

  const setYear = (i: number, v: string) => {
    const next = [0, 1, 2].map((k) => history[k] || HISTORY_UNKNOWN)
    next[i] = v
    // bez końcowych „nie wiem”
    while (next.length && next[next.length - 1] === HISTORY_UNKNOWN) next.pop()
    onHistoryChange(next)
  }

  const details = (
    <button
      type="button"
      aria-expanded={open}
      onClick={() => setOpen((o) => !o)}
      className="flex min-h-11 shrink-0 items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-brand hover:bg-sage-soft"
    >
      <SlidersHorizontal className="size-4" aria-hidden />
      {t('Więcej szczegółów')}
      <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
    </button>
  )

  return (
    <section
      aria-label={t('Co rośnie na tej działce?')}
      className={cn('rounded-xl border bg-surface', !crop && 'border-brand/60 bg-ok-soft/60 ring-1 ring-brand/20')}
    >
      {crop && !editing ? (
        // po wyborze – jedna linia
        <div className="flex min-h-12 flex-wrap items-center gap-x-2 gap-y-1 py-1.5 pr-2 pl-4">
          <Sprout className="size-5 shrink-0 text-brand" aria-hidden />
          <p className="min-w-0 flex-1 text-base leading-6">
            <span className="text-text-muted">{t('Uprawa:')}</span> <b className="font-semibold">{t(cropLabel(crop) ?? '')}</b>
            <span className="text-text-muted"> · </span>
            <button type="button" onClick={() => setEditing(true)} className="font-semibold text-brand underline-offset-2 hover:underline">
              {t('zmień')}
            </button>
          </p>
          {details}
        </div>
      ) : (
        <div className="space-y-2 px-4 pt-3.5 pb-2">
          <h3 className="flex items-center gap-2 text-base leading-6 font-semibold">
            <Sprout className="size-5 shrink-0 text-brand" aria-hidden /> {t('Co rośnie na tej działce?')}
          </h3>
          <CropField
            crop={crop}
            onChange={(c) => {
              onCropChange(c)
              setEditing(false)
            }}
            optional
          />
          {!crop && <p className="text-sm leading-5 font-medium text-brand-dark">{t('Wybierz uprawę – wynik będzie dokładniejszy')}</p>}
          <div className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-sm text-text-muted">{summary.join(' · ')}</span>
            {details}
          </div>
        </div>
      )}

      {open && (
        <div className="space-y-4 border-t px-4 py-3.5">
          {onPlannedChange && planOptions.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-sm font-semibold">{t('Co planujesz posiać?')}</p>
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
              <p className="text-xs leading-4 text-text-muted">{t('Ocenimy Twój wybór i podpowiemy lepsze możliwości.')}</p>
            </div>
          )}

          <div className="space-y-1.5">
            <p className="text-sm font-semibold">{t('Co rosło tu wcześniej?')}</p>
            <div className="grid gap-2">
              {YEARS.map((label, i) => {
                const v = history[i] || HISTORY_UNKNOWN
                return (
                  <div key={label} className="grid grid-cols-[6.5rem_1fr] items-center gap-2">
                    <span className="text-sm text-text-muted">{t(label)}</span>
                    <Select value={v} onValueChange={(x) => setYear(i, x)}>
                      <SelectTrigger
                        aria-label={t('Uprawa {kiedy}', { kiedy: t(label) })}
                        className="h-11 w-full min-w-0 rounded-md bg-surface-2 text-base data-[size=default]:h-11"
                      >
                        <span className="min-w-0 truncate text-left">
                          <SelectValue>{v === HISTORY_UNKNOWN ? t('Nie wiem') : historyLabel(v)}</SelectValue>
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
                  </div>
                )
              })}
            </div>
            {rotationHint && !known.length && <p className="text-xs leading-4 text-text-muted">{t(rotationHint)}</p>}
          </div>

          <div className="space-y-1.5">
            <p className="text-sm font-semibold">{t('Ile hektarów obsiewasz?')}</p>
            <AreaInput value={area?.value_ha ?? null} onCommit={onAreaChange} />
            {area?.estimated && <p className="text-xs leading-4 text-text-muted">{t('Oszacowanie z granic działki – popraw, jeśli uprawiasz mniej lub więcej.')}</p>}
          </div>
        </div>
      )}
    </section>
  )
}
