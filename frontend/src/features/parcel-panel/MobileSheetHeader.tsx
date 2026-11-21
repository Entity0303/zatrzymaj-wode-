import { FileDown, Leaf } from 'lucide-react'
import type { Parcel, StatusLevel } from '@/api/types'
import { StatusBadge } from '@/components/StatusBadge'
import { formatHa, shortCounty } from '@/lib/format'
import { ParcelActions } from './ParcelActions'
import type { SearchPhase } from './types'

/** Zwinięta część szuflady: nazwa działki + status + „Raport” (SPEC 12). */
export function MobileSheetHeader({
  search,
  parcel,
  saved,
  onToggleSave,
  onCopied,
  status = 'no_data',
}: {
  status?: StatusLevel
  search: SearchPhase
  parcel: Parcel | null
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
}) {
  if (parcel)
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
            <Leaf className="size-5" aria-hidden />
          </span>
          <h2 className="min-w-0 flex-1 truncate text-[22px] leading-7 font-semibold">Działka {parcel.numer}</h2>
          <span className="tabular shrink-0 text-lg font-semibold" title="Pomiar – z granic działki w ewidencji (ULDK GUGiK)">
            {formatHa(parcel.powierzchnia_ha)} ha
          </span>
        </div>
        <p className="truncate pl-[46px] text-sm leading-5 text-text-muted">
          gm. {parcel.gmina}, obręb {parcel.obreb} · {shortCounty(parcel.powiat)}
        </p>
        <div className="flex items-center gap-1 pl-[46px]">
          <StatusBadge status={status} size="sm" />
          <span className="flex-1" />
          <ParcelActions parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />
          <button
            type="button"
            disabled
            title="Raport PDF – w budowie"
            className="ml-1 flex h-11 items-center gap-1.5 rounded-md bg-brand-dark px-3 text-sm font-semibold text-white opacity-60"
          >
            <FileDown className="size-4" aria-hidden /> Raport
          </button>
        </div>
      </div>
    )
  const title =
    search.phase === 'loading'
      ? 'Szukam działki…'
      : search.phase === 'error'
        ? search.error.title
        : search.phase === 'candidates'
          ? `Znaleziono ${search.total} działek`
          : 'Znajdź swoją działkę'
  const sub =
    search.phase === 'candidates'
      ? 'Wybierz z listy pod wyszukiwarką lub kliknij numer na mapie'
      : search.phase === 'idle'
        ? 'Wpisz numer, kliknij pole albo użyj lokalizacji'
        : search.phase === 'error'
          ? 'Przesuń w górę, aby zobaczyć szczegóły'
          : 'Pobieram dane z ewidencji (ULDK GUGiK)'
  return (
    <div className="min-h-12">
      <h2 className="text-lg leading-6 font-semibold">{title}</h2>
      <p className="text-sm leading-5 text-text-muted">{sub}</p>
    </div>
  )
}
