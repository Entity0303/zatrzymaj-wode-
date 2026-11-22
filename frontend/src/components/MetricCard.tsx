import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { SourceTag, type SourceKind } from '@/components/SourceTag'
import { useLang } from '@/lib/i18n'

type Tone = 'water' | 'brand' | 'earth' | 'warn' | 'danger' | 'muted'

const TONE: Record<Tone, string> = {
  water: 'bg-water-soft text-water',
  brand: 'bg-ok-soft text-brand',
  earth: 'bg-surface-2 text-earth',
  warn: 'bg-warn-soft text-[#875a12]',
  danger: 'bg-danger-soft text-danger',
  muted: 'bg-surface-2 text-text-muted',
}

/**
 * Karta wskaźnika (SPEC 14): ikona, nazwa, duża liczba z jednostką, pasek/okrąg, SourceTag.
 * Bez wartości (value === null) pokazuje szare kreskowanie i „Brak danych” – nigdy zero.
 */
export function MetricCard({
  icon: Icon,
  title,
  value,
  unit,
  valuePrefix,
  tone = 'brand',
  source,
  sourceDate,
  sourceTitle,
  noDataText = 'Analiza w budowie',
  loading,
  children,
  className,
}: {
  icon: LucideIcon
  title: string
  value: string | null
  unit?: string
  /** np. strzałka ↓ przy ujemnym bilansie (ref-style) */
  valuePrefix?: ReactNode
  tone?: Tone
  source: SourceKind
  sourceDate?: string
  sourceTitle?: string
  noDataText?: string
  loading?: boolean
  /** pasek / okrąg / dodatkowy opis */
  children?: ReactNode
  className?: string
}) {
  const { t } = useLang()
  const noData = value === null && !loading
  // tekst zamiast liczby (np. „gęsta zieleń”, „Nie dotyczy”, „ocena tylko w sezonie…”) – zwykła wielkość, nie jak duża liczba
  const textual = value != null && value.length > 8 && !/^[\s\d,.%+−-]+$/.test(value)
  return (
    <div
      className={cn(
        'flex min-w-0 flex-col gap-2 rounded-xl border bg-surface p-3.5',
        noData && 'hatch-nodata',
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span className={cn('flex size-8 shrink-0 items-center justify-center rounded-full', noData ? TONE.muted : TONE[tone])}>
          <Icon className="size-[18px]" aria-hidden />
        </span>
        <span className="min-w-0 text-sm leading-5 font-medium">{t(title)}</span>
      </div>
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-20 bg-surface-2" />
          <Skeleton className="h-2 w-full bg-surface-2" />
        </div>
      ) : noData ? (
        <div>
          <p className="text-2xl leading-8 font-semibold text-text-muted" aria-hidden>—</p>
          <p className="text-sm leading-5 text-text-muted">{t(noDataText)}</p>
        </div>
      ) : textual ? (
        <p className={cn('text-lg leading-6 font-semibold', tone === 'muted' && 'text-base font-medium text-text-muted')}>{value}</p>
      ) : (
        <p className="tabular flex items-baseline gap-1 text-[32px] leading-10 font-semibold">
          {valuePrefix}
          {value}
          {unit && <span className="text-base font-medium text-text-muted">{unit}</span>}
        </p>
      )}
      {!loading && children}
      <div className="mt-auto pt-0.5">
        <SourceTag kind={noData ? 'brak_danych' : source} date={noData ? undefined : sourceDate} title={sourceTitle} />
      </div>
    </div>
  )
}
