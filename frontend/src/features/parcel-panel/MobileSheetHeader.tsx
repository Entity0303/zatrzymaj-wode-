import { FileDown, Leaf, Loader2, X } from 'lucide-react'
import type { Parcel, StatusLevel } from '@/api/types'
import { LogoMark } from '@/components/LogoMark'
import { StatusBadge } from '@/components/StatusBadge'
import { BRAND_NAME, BRAND_TAGLINE } from '@/lib/brand'
import { formatHa, shortCounty } from '@/lib/format'
import { ParcelActions } from './ParcelActions'
import type { SearchPhase } from './types'
import { useLang } from '@/lib/i18n'
import { useParcelTitle } from './parcelTitle'

/** Zwinięta część szuflady: nazwa działki + status + „Raport” (SPEC 12). */
export function MobileSheetHeader({
  search,
  parcel,
  saved,
  onToggleSave,
  onCopied,
  status = 'no_data',
  onReport,
  reportBusy,
  onClose,
}: {
  /** zamyka działkę – powrót do mapy */
  onClose?: () => void
  status?: StatusLevel
  /** pobranie raportu PDF; brak = analiza jeszcze niegotowa */
  onReport?: () => void
  reportBusy?: boolean
  search: SearchPhase
  parcel: Parcel | null
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
}) {
  if (parcel)
    return (
      <ParcelHead
        parcel={parcel}
        saved={saved}
        onToggleSave={onToggleSave}
        onCopied={onCopied}
        status={status}
        onReport={onReport}
        reportBusy={reportBusy}
        onClose={onClose}
      />
    )
  return <EmptyHead search={search} />
}

function ParcelHead({
  parcel,
  saved,
  onToggleSave,
  onCopied,
  status,
  onReport,
  reportBusy,
  onClose,
}: {
  parcel: Parcel
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
  status: StatusLevel
  onReport?: () => void
  reportBusy?: boolean
  onClose?: () => void
}) {
  const { t } = useLang()
  const { approx, title } = useParcelTitle(parcel)
  return (
      <div className="space-y-1">
        <div className="flex items-center gap-2.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
            <Leaf className="size-5" aria-hidden />
          </span>
          <h2 className="font-name min-w-0 flex-1 truncate text-2xl leading-8 font-semibold">{title}</h2>
          <span
            className="tabular shrink-0 text-lg font-semibold"
            title={t(approx ? 'Kwadrat wokół wskazanego punktu – brak granic działki' : 'Pomiar – z granic działki w ewidencji (ULDK GUGiK)')}
          >
            {formatHa(parcel.powierzchnia_ha)} ha
          </span>
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
        <p className="truncate pl-[46px] text-sm leading-5 text-text-muted">
          {approx
            ? t('wokół wskazanego punktu')
            : `${t('gm. {gmina}, obręb {obreb}', { gmina: parcel.gmina, obreb: parcel.obreb })} · ${shortCounty(parcel.powiat)}`}
        </p>
        <div className="flex items-center gap-1 pl-[46px]">
          <StatusBadge status={status} size="sm" now={status !== 'no_data'} />
          <span className="flex-1" />
          <ParcelActions parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />
          <button
            type="button"
            disabled={!onReport || reportBusy}
            onClick={onReport}
            title={onReport ? t('Pobierz raport PDF') : t('Raport powstaje z gotowej analizy')}
            className="ml-1 flex h-11 items-center gap-1.5 rounded-md bg-brand-dark px-3 text-sm font-semibold text-white disabled:opacity-60"
          >
            {reportBusy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FileDown className="size-4" aria-hidden />} {t('Raport')}
          </button>
        </div>
      </div>
  )
}

function EmptyHead({ search }: { search: SearchPhase }) {
  const { t } = useLang()
  const title =
    search.phase === 'loading'
      ? t('Szukam działki…')
      : search.phase === 'error'
        ? t(search.error.title, search.error.vars)
        : search.phase === 'candidates'
          ? t('Znaleziono {n} działek', { n: search.total })
          : t('Znajdź swoją działkę')
  const sub =
    search.phase === 'candidates'
      ? t('Wybierz z listy pod wyszukiwarką lub kliknij numer na mapie')
      : search.phase === 'idle'
        ? t('Wpisz numer, kliknij pole albo użyj lokalizacji')
        : search.phase === 'error'
          ? t('Przesuń w górę, aby zobaczyć szczegóły')
          : t('Pobieram dane z ewidencji (ULDK GUGiK)')
  return (
    <div className="min-h-12">
      {/* nagłówek wersji mobilnej: nazwa produktu, dopóki nie wybrano działki */}
      {search.phase === 'idle' && (
        <p className="mb-2.5 flex items-center gap-2.5">
          <LogoMark className="size-9 shrink-0" />
          <span className="min-w-0">
            <span className="font-display block text-lg leading-5 font-bold text-brand">{BRAND_NAME}</span>
            <span className="block text-sm leading-5 text-text-muted">{t(BRAND_TAGLINE)}</span>
          </span>
        </p>
      )}
      <h2 className="font-display text-xl leading-7 font-semibold">{title}</h2>
      <p className="text-sm leading-5 text-text-muted">{sub}</p>
    </div>
  )
}
