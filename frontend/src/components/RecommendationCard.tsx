import { ChevronDown, MapPinned } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import type { RecommendationCategory as RecCategory } from '@/api/types'
import { cn } from '@/lib/utils'
import { REC_CATEGORY } from '@/theme/recommendations'
import { SourceTag } from '@/components/SourceTag'
import { useLang } from '@/lib/i18n'
import { useSettings } from '@/lib/storage'

/**
 * Karta rekomendacji (SPEC 14): ikona kategorii, tytuł, zdanie, rozwijane „Dlaczego?”,
 * opcjonalnie „Pokaż na mapie”. noData = karta-zaślepka bez treści udającej wynik.
 */
export function RecommendationCard({
  category,
  title,
  text,
  why,
  noData,
  onShowOnMap,
}: {
  category: RecCategory
  title: string
  text: string
  why: ReactNode
  noData?: boolean
  onShowOnMap?: () => void
}) {
  const { t } = useLang()
  const [settings] = useSettings()
  // tryb doradcy: „Dlaczego?” rozwinięte od razu (SPEC 3)
  const [open, setOpen] = useState(settings.mode === 'doradca' && !noData)
  const id = useId()
  const c = REC_CATEGORY[category]
  const Icon = c.icon
  return (
    <div className={cn('rounded-xl border bg-surface p-3.5', noData && 'hatch-nodata')}>
      <div className="flex gap-3">
        <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-lg', noData ? 'bg-surface-2 text-text-muted' : c.cls)}>
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs leading-4 font-medium tracking-wide text-text-muted uppercase">{t(c.label)}</p>
          <p className="text-base leading-6 font-semibold">{t(title)}</p>
          <p className="text-sm leading-5 text-text-muted">{t(text)}</p>
          {noData && <SourceTag kind="brak_danych" className="mt-2" />}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 pl-12">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen((o) => !o)}
          className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-brand hover:underline"
        >
          {t('Dlaczego?')}
          <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
        </button>
        {onShowOnMap && (
          <button
            type="button"
            onClick={onShowOnMap}
            className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-brand hover:underline"
          >
            <MapPinned className="size-4" aria-hidden /> {t('Pokaż na mapie')}
          </button>
        )}
      </div>
      {open && (
        <div id={id} className="mt-1 ml-12 rounded-lg bg-surface-2/70 p-3 text-sm leading-5 text-text">
          {typeof why === 'string' ? t(why) : why}
        </div>
      )}
    </div>
  )
}
