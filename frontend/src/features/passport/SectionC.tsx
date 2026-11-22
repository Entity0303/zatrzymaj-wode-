import { CloudRain, Layers, Mountain, Sprout, Sun, CircleHelp, type LucideIcon } from 'lucide-react'
import type { AnalysisResponse, CauseFactor } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatShare } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { PassportSection } from './PassportSection'

const FACTOR: Record<CauseFactor, { icon: LucideIcon; bar: string; chip: string }> = {
  opady: { icon: CloudRain, bar: 'bg-water', chip: 'bg-water-soft text-water' },
  parowanie: { icon: Sun, bar: 'bg-amber', chip: 'bg-amber-soft text-[#875a12]' },
  gleba: { icon: Layers, bar: 'bg-earth', chip: 'bg-surface-2 text-earth' },
  teren: { icon: Mountain, bar: 'bg-brand', chip: 'bg-sage-soft text-brand' },
  uprawa: { icon: Sprout, bar: 'bg-ok', chip: 'bg-ok-soft text-brand' },
  inne: { icon: CircleHelp, bar: 'bg-nodata', chip: 'bg-surface-2 text-text-muted' },
}

/** C. Dlaczego? (SPEC 7.C): czynniki od największego udziału, każdy z paskiem i liczbą. */
export function SectionC({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const causes = [...analysis.causes].sort((a, b) => b.share - a.share)
  return (
    <PassportSection id="pass-c" letter="C" title={t('Dlaczego?')}>
      {causes.length === 0 ? (
        <p className="text-sm text-text-muted">{t('Brakuje danych pogodowych albo o glebie')}</p>
      ) : (
        <ul className="space-y-3">
          {causes.map((c) => {
            const f = FACTOR[c.factor] ?? FACTOR.inne
            const Icon = f.icon
            return (
              <li key={c.factor + c.title} className="rounded-xl bg-surface p-4 shadow-card">
                <div className="flex items-center gap-3">
                  <span className={`flex size-9 shrink-0 items-center justify-center rounded-full ${f.chip}`}>
                    <Icon className="size-5" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1 text-base leading-6 font-semibold">{t(c.title)}</span>
                  <span className="tabular text-lg font-semibold">{formatShare(c.share)}</span>
                </div>
                <div className="mt-2.5 h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                  <div className={`h-full rounded-full ${f.bar}`} style={{ width: `${Math.max(0, Math.min(1, c.share)) * 100}%` }} />
                </div>
                <p className="mt-2 text-sm leading-5 text-text-muted">{t(c.description)}</p>
                <SourceTag kind={c.source_tag.kind} title={c.source_tag.source ?? undefined} className="mt-2" />
              </li>
            )
          })}
        </ul>
      )}
      <p className="text-xs leading-4 text-text-muted">{t('Procent = waga przyczyny w opisie.')}</p>
    </PassportSection>
  )
}
