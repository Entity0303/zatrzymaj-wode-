import { Calculator, CircleDashed, Cpu, Ruler, Satellite, TrendingUp, type LucideIcon } from 'lucide-react'
import type { SourceKind } from '@/api/types'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** Etykiety pochodzenia liczb (SPEC 15.2) – obowiązkowe przy każdej liczbie. */
export type { SourceKind }

const KINDS: Record<SourceKind, { label: string; icon: LucideIcon; cls: string }> = {
  pomiar: { label: 'Pomiar', icon: Ruler, cls: 'bg-surface-2 text-text-muted' },
  satelita: { label: 'Z satelity', icon: Satellite, cls: 'bg-ok-soft text-brand' },
  obliczenia: { label: 'Obliczenia z danych', icon: Calculator, cls: 'bg-surface-2 text-text-muted' },
  szacunek_modelu: { label: 'Szacunek modelu', icon: Cpu, cls: 'bg-water-soft text-[#1d5d96]' },
  prognoza: { label: 'Prognoza', icon: TrendingUp, cls: 'bg-water-soft text-[#1d5d96]' },
  brak_danych: { label: 'Brak danych', icon: CircleDashed, cls: 'border border-nodata/60 bg-nodata-soft text-text-muted' },
}

export function SourceTag({
  kind,
  date,
  title,
  className,
}: {
  kind: SourceKind
  /** data zdjęcia satelitarnego / danych, np. „12.06.2026” */
  date?: string
  /** pełna nazwa źródła w dymku */
  title?: string
  className?: string
}) {
  const { t } = useLang()
  const k = KINDS[kind]
  const Icon = k.icon
  return (
    <span
      title={title}
      className={cn(
        'inline-flex max-w-full items-start gap-1 rounded-[10px] px-2 py-0.5 text-xs leading-4 font-medium',
        k.cls,
        className,
      )}
    >
      <Icon className="mt-0.5 size-3 shrink-0" aria-hidden />
      <span className="min-w-0 [overflow-wrap:anywhere]">
        {t(k.label)}
        {date ? ` · ${date}` : ''}
      </span>
    </span>
  )
}
