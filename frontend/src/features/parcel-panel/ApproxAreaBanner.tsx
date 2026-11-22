import { MapPinned } from 'lucide-react'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * Obszar przybliżony (A5b-2b): wyraźny żółty pasek nad wynikiem – w karcie działki i w paszporcie.
 * Stały, prosty tekst; techniczny powód (`approximate_area.reason`, np. „ponowna próba za 49 s”) – nie pokazujemy.
 */
export function ApproxAreaBanner({ className }: { className?: string }) {
  const { t } = useLang()
  return (
    <div role="note" className={cn('flex gap-3 rounded-xl border border-warn bg-warn-soft px-4 py-3', className)}>
      <MapPinned className="mt-0.5 size-5 shrink-0 text-[#875a12]" aria-hidden />
      <p className="text-sm leading-5 text-text">
        <b className="block text-base leading-6">{t('Obszar przybliżony – brak dokładnych granic działki.')}</b>
        {t('Wynik dla kwadratu ok. 1 ha wokół wskazanego punktu.')} {t('Wpisz numer działki albo narysuj pole.')}
      </p>
    </div>
  )
}
