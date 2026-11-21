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
 * „To nie jest grunt rolny” (SPEC 15.1) – gdy wg mapy gleb IUNG działka to las / woda / zabudowa itd.
 * Zastępuje kartę stanu; wskaźników i zaleceń suszy rolniczej wtedy nie pokazujemy.
 */
export function NonAgriculturalCard({ soil }: { soil: Soil }) {
  const { t } = useLang()
  const r = soil.non_agricultural_reason ? REASON[soil.non_agricultural_reason] : null
  const Icon = r?.icon ?? Trees
  const fallback = r
    ? t('Według mapy gleb IUNG ta działka to {what} – ocena suszy rolniczej nie ma tu zastosowania.', { what: t(r.word) })
    : t('Według mapy gleb IUNG to nie jest grunt rolny – ocena suszy rolniczej nie ma tu zastosowania.')
  return (
    <div role="status" className="hatch-nodata flex items-start gap-3.5 rounded-xl border border-nodata/50 p-4">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-surface text-text-muted">
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="font-display text-xl leading-7 font-semibold">{t('To nie jest grunt rolny')}</p>
        <p className="mt-0.5 text-sm leading-5">{soil.non_agricultural_note ? t(soil.non_agricultural_note) : fallback}</p>
        <p className="mt-2 text-sm leading-5 text-text-muted">
          {t('Możesz wyszukać inną działkę albo kliknąć pole uprawne na mapie.')}
        </p>
      </div>
    </div>
  )
}
