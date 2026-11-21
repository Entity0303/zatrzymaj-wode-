import { CalendarDays } from 'lucide-react'
import { minAnalysisIso, todayIso } from '@/lib/dates'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** „📅 Data analizy” – zakres dziś − 10 lat … dziś (SPEC 4.2). */
export function DateField({
  value,
  onChange,
  compact,
  bare,
}: {
  value: string
  onChange: (v: string) => void
  compact?: boolean
  /** bez własnego tła i cienia – w grupie górnego paska */
  bare?: boolean
}) {
  const { t, lang } = useLang()
  return (
    <label
      className={cn(
        'flex h-12 shrink-0 items-center gap-2 rounded-full bg-surface px-4 shadow-float',
        compact && 'h-11 w-full rounded-md border shadow-none',
        bare && 'rounded-none bg-transparent shadow-none',
      )}
    >
      <CalendarDays className="size-5 shrink-0 text-brand" aria-hidden />
      <span className={cn('text-sm whitespace-nowrap text-text-muted', compact ? 'max-[419px]:hidden' : 'hidden xl:inline')}>
        {t('Data analizy')}
      </span>
      <input
        type="date"
        lang={lang === 'en' ? 'en-GB' : 'pl'}
        aria-label={t('Data analizy')}
        value={value}
        min={minAnalysisIso()}
        max={todayIso()}
        onChange={(e) => e.target.value && onChange(e.target.value)}
        className="tabular min-w-0 flex-1 bg-transparent text-base font-semibold outline-none"
      />
    </label>
  )
}
