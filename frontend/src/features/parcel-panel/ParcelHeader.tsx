import { Leaf } from 'lucide-react'
import type { Parcel } from '@/api/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatHa, shortCounty } from '@/lib/format'
import { ParcelActions } from './ParcelActions'

/** 1. Nagłówek panelu (SPEC 6.1). */
export function ParcelHeader({
  parcel,
  saved,
  onToggleSave,
  onCopied,
}: {
  parcel: Parcel
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
          <Leaf className="size-5" aria-hidden />
        </span>
        <h2 className="min-w-0 flex-1 text-[22px] leading-7 font-semibold break-words">Działka {parcel.numer}</h2>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="tabular shrink-0 text-lg leading-6 font-semibold">
              {formatHa(parcel.powierzchnia_ha)} ha
            </span>
          </TooltipTrigger>
          <TooltipContent>Pomiar – policzone z granic działki w ewidencji (ULDK GUGiK)</TooltipContent>
        </Tooltip>
      </div>
      <div className="flex items-start gap-2 pl-[52px]">
        <p className="min-w-0 flex-1 pt-1 text-sm leading-5 text-text-muted">
          gm. {parcel.gmina}, obręb {parcel.obreb} · {shortCounty(parcel.powiat)}
        </p>
        <div className="-mt-1 -mr-2 flex shrink-0">
          <ParcelActions parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />
        </div>
      </div>
    </div>
  )
}
