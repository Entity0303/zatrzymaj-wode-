import { Layers } from 'lucide-react'
import type { Soil } from '@/api/types'
import { SourceTag } from '@/components/SourceTag'
import { formatNum, formatShare } from '@/lib/format'
import { soilColor } from '@/theme/soil'
import { useLang } from '@/lib/i18n'

/**
 * Gleba działki (kontrakt `soil`, SPEC 15.3): kategoria podatności na suszę, ile wody zmieści gleba,
 * udziały kategorii w obrysie, klasy bonitacyjne (informacyjnie). Nic więcej – bez pH i składników.
 */
export function SoilCard({ soil }: { soil: Soil }) {
  const { t } = useLang()
  const shares = [...soil.shares].sort((a, b) => b.share - a.share)
  return (
    <section aria-label={t('Gleba')} className="rounded-xl border bg-surface p-3.5">
      <div className="flex items-start gap-3">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-earth">
          <Layers className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-5 text-text-muted">{t('Kategoria gleby (IUNG)')}</p>
          <p className="text-base leading-6 font-semibold">{soil.dominant_label ? t(soil.dominant_label) : t('Brak danych')}</p>
        </div>
      </div>

      <div className="mt-3 flex items-baseline justify-between gap-2">
        <span className="text-sm leading-5">{t('Ile wody zmieści gleba')}</span>
        <span className="tabular text-xl leading-7 font-semibold">
          {soil.wod_mm != null ? (
            <>
              {formatNum(soil.wod_mm, 0)} <span className="text-sm font-medium text-text-muted">mm</span>
            </>
          ) : (
            <span className="text-base text-text-muted">{t('Brak danych')}</span>
          )}
        </span>
      </div>

      {shares.length > 0 && (
        <div className="mt-3">
          <div className="flex h-2.5 overflow-hidden rounded-full" aria-hidden>
            {shares.map((s) => (
              <span key={s.code} style={{ width: `${s.share * 100}%`, background: soilColor(s.code) }} />
            ))}
          </div>
          <ul className="mt-2 space-y-1">
            {shares.map((s) => (
              <li key={s.code} className="flex items-center gap-2 text-sm leading-5">
                <span className="size-3 shrink-0 rounded-full" style={{ background: soilColor(s.code) }} aria-hidden />
                <span className="min-w-0 flex-1 truncate">{t(s.label)}</span>
                <span className="tabular font-medium">{formatShare(s.share)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-2 text-sm leading-5 text-text-muted">
        {soil.classes?.length
          ? t('Klasy bonitacyjne: {list}', { list: soil.classes.join(', ') })
          : soil.classes_note
            ? t(soil.classes_note)
            : t('Klasy bonitacyjne: brak danych')}
      </p>

      <div className="mt-2.5">
        <SourceTag kind={soil.source_tag.kind} title={soil.source_tag.source ?? 'IUNG-PIB'} />
      </div>
    </section>
  )
}
