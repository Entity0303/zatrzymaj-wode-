import { SourceTag } from '@/components/SourceTag'
import { useLang } from '@/lib/i18n'

/** Szare kreskowanie + „Brak danych” (SPEC 15.1) – nigdy zero ani wymyślona wartość. */
export function NoDataNote({ text = 'Brak danych – analiza w budowie' }: { text?: string }) {
  const { t } = useLang()
  return (
    <div className="hatch-nodata flex flex-1 flex-col items-start justify-center gap-1.5 rounded-lg px-3 py-2">
      <p className="text-sm leading-5 text-text-muted">{t(text)}</p>
      <SourceTag kind="brak_danych" />
    </div>
  )
}
