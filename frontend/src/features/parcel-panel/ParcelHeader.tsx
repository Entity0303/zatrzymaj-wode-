import { Info, Leaf, X } from 'lucide-react'
import type { Parcel } from '@/api/types'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatHa, shortCounty } from '@/lib/format'
import { ParcelActions } from './ParcelActions'
import { useLang } from '@/lib/i18n'
import { useParcelTitle } from './parcelTitle'

/** 1. Nagłówek panelu (SPEC 6.1). */
export function ParcelHeader({
  parcel,
  saved,
  onToggleSave,
  onCopied,
  onClose,
}: {
  parcel: Parcel
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
  /** zamyka działkę – powrót do mapy */
  onClose?: () => void
}) {
  const { t } = useLang()
  const { approx, drawn, title } = useParcelTitle(parcel)
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
          <Leaf className="size-5" aria-hidden />
        </span>
        <h2 className="font-name min-w-0 flex-1 text-2xl leading-8 font-bold break-words">{title}</h2>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="tabular flex shrink-0 items-center gap-1 text-base leading-6 font-medium text-text-muted">
              {formatHa(parcel.powierzchnia_ha)} ha
              {approx && <Info className="size-4 text-amber" aria-label={t('Obszar przybliżony')} />}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {t(
              approx
                ? 'Obszar przybliżony – brak dokładnych granic działki. Liczymy kwadrat wokół wskazanego punktu.'
                : 'Pomiar – policzone z granic działki w ewidencji (ULDK GUGiK)',
            )}
          </TooltipContent>
        </Tooltip>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t('Zamknij działkę i wróć do mapy')}
            className="-mr-2 flex size-10 shrink-0 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
          >
            <X className="size-5" />
          </button>
        )}
      </div>
      <div className="flex items-start gap-2 pl-[52px]">
        <p className="min-w-0 flex-1 pt-1 text-sm leading-5 text-text-muted">
          {drawn
            ? t('obrys narysowany na mapie')
            : approx
            ? t('wokół wskazanego punktu')
            : `${t('gm. {gmina}, obręb {obreb}', { gmina: parcel.gmina, obreb: parcel.obreb })} · ${shortCounty(parcel.powiat)}`}
        </p>
        <div className="-mt-1 -mr-2 flex shrink-0">
          <ParcelActions parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />
        </div>
      </div>
    </div>
  )
}
