import { Leaf } from 'lucide-react'
import type { Parcel } from '@/api/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatHa, shortCounty } from '@/lib/format'
import { ParcelActions } from './ParcelActions'
import { useLang } from '@/lib/i18n'

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
  const { t } = useLang()
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
          <Leaf className="size-5" aria-hidden />
        </span>
        <h2 className="font-display min-w-0 flex-1 text-2xl leading-8 font-semibold break-words">{t('Działka {numer}', { numer: parcel.numer })}</h2>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="tabular shrink-0 text-base leading-6 font-medium text-text-muted">
              {formatHa(parcel.powierzchnia_ha)} ha
            </span>
          </TooltipTrigger>
          <TooltipContent>{t('Pomiar – policzone z granic działki w ewidencji (ULDK GUGiK)')}</TooltipContent>
        </Tooltip>
      </div>
      <div className="flex items-start gap-2 pl-[52px]">
        <p className="min-w-0 flex-1 pt-1 text-sm leading-5 text-text-muted">
          {t('gm. {gmina}, obręb {obreb}', { gmina: parcel.gmina, obreb: parcel.obreb })} · {shortCounty(parcel.powiat)}
        </p>
        <div className="-mt-1 -mr-2 flex shrink-0">
          <ParcelActions parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />
        </div>
      </div>
    </div>
  )
}
