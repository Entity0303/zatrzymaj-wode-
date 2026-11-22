import { CalendarDays } from 'lucide-react'
import { useRef, useState } from 'react'
import { minAnalysisIso, todayIso } from '@/lib/dates'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** RRRR-MM-DD → dd.mm.rrrr (zawsze, niezależnie od języka przeglądarki). */
const toPl = (iso: string) => {
  const [y, m, d] = iso.split('-')
  return y && m && d ? `${d}.${m}.${y}` : ''
}

/** „22.11.2026”, „22-11-2026”, „22/11/2026”, „22 11 2026” → RRRR-MM-DD albo null, gdy nie ma takiego dnia. */
function fromPl(text: string): string | null {
  const m = text.trim().match(/^(\d{1,2})[.\-/ ](\d{1,2})[.\-/ ](\d{4})$/)
  if (!m) return null
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const dt = new Date(Date.UTC(y, mo - 1, d))
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null
  return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

/**
 * „📅 Data analizy” – zakres dziś − 10 lat … dziś (SPEC 4.2). F18: zawsze dd.mm.rrrr – własne pole tekstowe
 * (wpisanie + Enter / wyjście z pola), kalendarz z ukrytego `input type=date` pod ikoną (format kalendarza zależy
 * od przeglądarki, ale pokazywana data – nie). Data spoza zakresu albo błędna – wraca poprzednia.
 */
export function DateField({
  value,
  onChange,
  compact,
  bare,
  field,
  label,
  min: minProp,
  max: maxProp,
  optional,
}: {
  /** F34: inna data niż data analizy (np. „Data siewu”) – nazwa pola dla czytników i w podpowiedzi przycisku */
  label?: string
  /** własny zakres (RRRR-MM-DD); domyślnie dziś − 10 lat … dziś */
  min?: string
  max?: string
  /** pole może być puste – wyczyszczenie tekstu oddaje '' */
  optional?: boolean
  value: string
  onChange: (v: string) => void
  compact?: boolean
  /** F14: pole formularza na karcie startowej – 48 px, ramka 1 px, bez cienia (jak wyszukiwarka obok) */
  field?: boolean
  /** bez własnego tła i cienia – w grupie górnego paska */
  bare?: boolean
}) {
  const { t } = useLang()
  const picker = useRef<HTMLInputElement>(null)
  const [text, setText] = useState(toPl(value))
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    setSeen(value)
    setText(toPl(value))
  }
  const min = minProp ?? minAnalysisIso()
  const max = maxProp ?? todayIso()
  const name = label ?? 'Data analizy'
  const commit = () => {
    if (optional && !text.trim()) {
      if (value) onChange('')
      return
    }
    const iso = fromPl(text)
    if (iso && iso >= min && iso <= max) {
      setText(toPl(iso))
      if (iso !== value) onChange(iso)
    } else setText(toPl(value))
  }
  const openPicker = () => {
    const el = picker.current
    if (!el) return
    try {
      el.showPicker()
    } catch {
      el.focus()
      el.click()
    }
  }
  return (
    <div
      className={cn(
        'relative flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface px-4 shadow-float',
        compact && 'h-11 w-full rounded-md border shadow-none',
        bare && 'rounded-none bg-transparent shadow-none',
        field && 'h-12 w-full rounded-xl border border-line px-3 shadow-none focus-within:border-brand',
      )}
    >
      <button
        type="button"
        onClick={openPicker}
        aria-label={label ? t('{pole} – wybierz z kalendarza', { pole: t(label) }) : t('Wybierz datę analizy z kalendarza')}
        title={label ? t('{pole} – wybierz z kalendarza', { pole: t(label) }) : t('Wybierz datę analizy z kalendarza')}
        className="-ml-1 flex size-8 shrink-0 items-center justify-center rounded-full hover:bg-surface-2"
      >
        <CalendarDays className="size-5 text-amber" aria-hidden />
      </button>
      {/* F26: na karcie startowej (`field`) etykieta jest NAD polem – w polu sama data, zawsze w całości */}
      {!field && !label && (
        <span className={cn('text-sm whitespace-nowrap text-text-muted', compact ? 'max-[419px]:hidden' : 'hidden 2xl:inline')}>
          {t('Data analizy')}
        </span>
      )}
      <input
        type="text"
        inputMode="numeric"
        placeholder="dd.mm.rrrr"
        aria-label={label ? `${t(name)} (dd.mm.rrrr)` : t('Data analizy (dd.mm.rrrr)')}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
        className={cn('tabular bg-transparent text-base font-semibold outline-none', compact ? 'min-w-0 flex-1' : field ? 'w-[6.5rem] min-w-[6.5rem] flex-1' : 'w-[6.5rem] shrink-0')}
      />
      {/* kalendarz przeglądarki – ukryty, otwierany ikoną */}
      <input
        ref={picker}
        type="date"
        tabIndex={-1}
        aria-hidden
        value={value}
        min={min}
        max={max}
        onChange={(e) => (e.target.value ? e.target.value >= min && e.target.value <= max && onChange(e.target.value) : optional && onChange(''))}
        className="pointer-events-none absolute bottom-0 left-3 h-0 w-0 opacity-0"
      />
    </div>
  )
}
