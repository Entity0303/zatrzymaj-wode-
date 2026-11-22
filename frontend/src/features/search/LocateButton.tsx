import { Loader2, LocateFixed } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useLang } from '@/lib/i18n'

/** „Moja lokalizacja” – działka, na której stoi rolnik. `inField` – ikona wewnątrz pola wyszukiwania. */
export function LocateButton({ locating, onClick, iconOnly, inField }: { locating: boolean; onClick: () => void; iconOnly?: boolean; inField?: boolean }) {
  const { t } = useLang()
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={locating}
      aria-label={t('Moja lokalizacja – znajdź działkę, na której stoisz')}
      title={inField ? t('Moja lokalizacja') : undefined}
      className={cn(
        'flex shrink-0 items-center justify-center gap-2 rounded-full font-medium text-text hover:bg-ok-soft disabled:opacity-70',
        inField ? 'size-10' : 'h-12 bg-surface shadow-float',
        !inField && (iconOnly ? 'w-12' : 'px-4 text-base'),
      )}
    >
      {locating ? <Loader2 className="size-5 animate-spin text-brand" /> : <LocateFixed className="size-5 text-brand" />}
      {!iconOnly && !inField && <span className="whitespace-nowrap">{t('Moja lokalizacja')}</span>}
    </button>
  )
}
