import { Copy, ExternalLink, MoreHorizontal, Star } from 'lucide-react'
import type { Parcel } from '@/api/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

const geoportalUrl = (id: string) =>
  `https://mapy.geoportal.gov.pl/imap/Imgp_2.html?identifyParcel=${encodeURIComponent(id)}`

/** ☆ zapisz działkę · ⋯ (kopiuj identyfikator, otwórz w Geoportalu) – SPEC 6.1 */
export function ParcelActions({
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
    <>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-pressed={saved}
              aria-label={saved ? t('Usuń z moich działek') : t('Zapisz działkę')}
              onClick={onToggleSave}
              className="flex size-11 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
            >
              <Star className={cn('size-5', saved && 'fill-warn text-warn')} aria-hidden />
            </button>
          </TooltipTrigger>
          <TooltipContent>{saved ? t('Zapisana w tej przeglądarce') : t('Zapisz działkę')}</TooltipContent>
        </Tooltip>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={t('Więcej opcji')}
              className="flex size-11 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
            >
              <MoreHorizontal className="size-5" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="z-[1500] w-64 rounded-xl">
            <DropdownMenuItem
              className="min-h-11 text-sm"
              onSelect={() => {
                navigator.clipboard?.writeText(parcel.id).then(onCopied, () => undefined)
              }}
            >
              <Copy className="size-4" /> {t('Kopiuj identyfikator')}
              <span className="ml-auto max-w-24 truncate text-xs text-text-muted">{parcel.id}</span>
            </DropdownMenuItem>
            <DropdownMenuItem asChild className="min-h-11 text-sm">
              <a href={geoportalUrl(parcel.id)} target="_blank" rel="noreferrer">
                <ExternalLink className="size-4" /> {t('Otwórz w Geoportalu')}
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
    </>
  )
}
