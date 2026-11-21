import { ChevronDown, Leaf, X } from 'lucide-react'
import type { Parcel, StatusLevel } from '@/api/types'
import { StatusBadge } from '@/components/StatusBadge'
import { useLang } from '@/lib/i18n'
import { useParcelTitle } from './parcelTitle'

/**
 * Zwinięty panel działki (komputer): sama belka z nazwą, stanem i ✕ – mapa zostaje odsłonięta.
 * Kliknięcie belki rozwija panel z powrotem.
 */
export function PanelCollapsed({ parcel, status, onExpand, onClose }: { parcel: Parcel; status: StatusLevel | null; onExpand: () => void; onClose: () => void }) {
  const { t } = useLang()
  const { title } = useParcelTitle(parcel)
  return (
    <div className="flex items-center gap-2 py-2 pr-2 pl-3">
      <button type="button" onClick={onExpand} aria-expanded={false} className="flex min-h-11 min-w-0 flex-1 items-center gap-2.5 rounded-lg text-left hover:bg-surface-2">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-ok-soft text-brand">
          <Leaf className="size-5" aria-hidden />
        </span>
        <span className="font-name min-w-0 flex-1 truncate text-lg leading-6 font-semibold">{title}</span>
        {status && <StatusBadge status={status} size="sm" />}
        <ChevronDown className="size-5 shrink-0 text-text-muted" aria-label={t('Rozwiń panel')} />
      </button>
      <button
        type="button"
        onClick={onClose}
        aria-label={t('Zamknij działkę i wróć do mapy')}
        className="flex size-10 shrink-0 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
      >
        <X className="size-5" />
      </button>
    </div>
  )
}
