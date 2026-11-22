import { Building2, Droplets, Route, Trees, Wheat, type LucideIcon } from 'lucide-react'
import type { NonAgriculturalReason, Soil } from '@/api/types'
import { useLang } from '@/lib/i18n'

const REASON: Record<NonAgriculturalReason, { word: string; icon: LucideIcon }> = {
  las: { word: 'las', icon: Trees },
  woda: { word: 'woda', icon: Droplets },
  zabudowa: { word: 'zabudowa', icon: Building2 },
  drogi: { word: 'drogi lub nieużytki', icon: Route },
  gleby_organiczne: { word: 'gleby organiczne', icon: Wheat },
}

/**
 * „To nie jest teren rolny” (SPEC 15.1) – gdy wg mapy gleb IUNG działka to las / woda / zabudowa itd.
 * JEDNA czysta karta: ikona, tytuł, jedno zdanie, „Wybierz inne pole”. Żadnych wskaźników suszy rolniczej.
 */
export function NonAgriculturalCard({ soil, onPickOther }: { soil: Soil; onPickOther?: () => void }) {
  const { t } = useLang()
  const r = soil.non_agricultural_reason ? REASON[soil.non_agricultural_reason] : null
  const Icon = r?.icon ?? Trees
  const sentence = r
    ? t('Według mapy gleb IUNG to {what} – ocena suszy rolniczej tu nie ma zastosowania.', { what: t(r.word) })
    : t('Według mapy gleb IUNG to nie jest grunt rolny – ocena suszy rolniczej tu nie ma zastosowania.')
  return (
    <div role="status" className="flex flex-col items-center gap-3 rounded-xl border bg-surface px-5 py-6 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-surface-2 text-text-muted">
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="space-y-1">
        <p className="text-xl leading-7 font-semibold">{t('To nie jest teren rolny')}</p>
        <p className="text-sm leading-5 text-text-muted">{sentence}</p>
      </div>
      {onPickOther && (
        <button
          type="button"
          onClick={onPickOther}
          className="mt-1 flex h-11 items-center justify-center rounded-md bg-brand px-5 text-sm font-semibold text-white hover:bg-brand-dark"
        >
          {t('Wybierz inne pole')}
        </button>
      )}
    </div>
  )
}
