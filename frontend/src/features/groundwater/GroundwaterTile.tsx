import { Droplet, Waves } from 'lucide-react'
import type { AnalysisResponse, InfiltrationLevel } from '@/api/types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useGroundwater } from './useGroundwater'

/** Kolor poziomu wsiąkania: kropka w kolorze poziomu, napis w ciemniejszym odcieniu (czytelność). */
const LEVEL_STYLE: Record<InfiltrationLevel, { dot: string; text: string }> = {
  dobre: { dot: 'bg-pp-ok', text: 'text-ok' },
  slabe: { dot: 'bg-pp-risk', text: 'text-risk' },
  bardzo_slabe: { dot: 'bg-pp-bad', text: 'text-pp-bad' },
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/**
 * A27: kafel „Wody gruntowe i wsiąkanie” – poziom wsiąkania (ile wody z opadu zostaje w glebie dla roślin; liczone
 * z opadu, parowania, kategorii gleby i spadku terenu) ze zdaniem dla rolnika, obok – czy działka leży na obszarze
 * zagrożonym podtopieniami (PIG-PIB). Przy płytkiej wodzie gruntowej ikona kropli i dopisek „susza może być mniejsza
 * niż z bilansu”. Brak odpowiedzi = kafel ukryty; nic nie policzono = szary kafel z notą. `passport` – wersja szeroka.
 */
export function GroundwaterTile({ analysis, passport }: { analysis: AnalysisResponse; passport?: boolean }) {
  const { t } = useLang()
  const ctx = useGroundwater(analysis)
  if (!ctx) return null
  const title = t('Wody gruntowe i wsiąkanie')
  const box = cn('min-w-0 bg-surface', passport ? 'rounded-[18px] border border-paper-line p-4 md:p-5' : 'rounded-xl border p-3.5')
  const head = (
    <p className="flex items-center gap-2 text-sm leading-5 font-semibold text-text-muted">
      <Waves className="size-4 shrink-0" aria-hidden /> {title}
    </p>
  )

  if (ctx.unavailable)
    return (
      <section aria-label={title} className={cn(box, 'bg-surface-2')}>
        {head}
        <p className="mt-1.5 text-sm leading-5 text-text-muted">{t(ctx.note_pl ?? 'Brak danych')}</p>
      </section>
    )

  const inf = ctx.infiltration
  const style = inf ? LEVEL_STYLE[inf.level] : null
  return (
    <section aria-label={title} className={box}>
      {head}
      <div className={cn('mt-1.5', passport && 'grid gap-x-6 gap-y-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]')}>
        <div className="space-y-1">
          {inf && style ? (
            <>
              <p className={cn('flex items-center gap-2 font-bold', style.text, passport ? 'text-[24px] leading-8' : 'text-xl leading-7')}>
                <span className={cn('size-3 shrink-0 rounded-full', style.dot)} aria-hidden />
                {cap(t(inf.label_pl))}
              </p>
              <p className="text-sm leading-5">{t(inf.sentence_pl)}</p>
            </>
          ) : (
            <p className="text-sm leading-5 text-text-muted">{t('Brak danych pogodowych z ostatnich 30 dni – wsiąkania nie liczymy.')}</p>
          )}
        </div>
        <div className={cn('space-y-1.5', !passport && 'mt-2 border-t pt-2')}>
          {ctx.source_pig.unavailable ? (
            <p className="text-sm leading-5 text-text-muted">{t('Obszary zagrożone podtopieniami: brak danych ({note}).', { note: t(ctx.source_pig.note_pl ?? 'usługa PIG niedostępna') })}</p>
          ) : (
            ctx.interpretation_pl && <p className="text-sm leading-5">{t(ctx.interpretation_pl)}</p>
          )}
          {ctx.may_reduce_drought && (
            <p className="flex items-center gap-1.5 text-sm leading-5 font-semibold text-pp-water">
              <Droplet className="size-4 shrink-0" aria-hidden /> {t('susza może być mniejsza niż z bilansu')}
            </p>
          )}
          <p className="text-xs leading-4 text-text-muted">
            {t(ctx.limitation_pl)} {!ctx.source_pig.unavailable && ctx.source_pig.note_pl ? `${t(ctx.source_pig.note_pl)} ` : ''}
            {t('Źródło:')} {ctx.source}.
          </p>
        </div>
      </div>
    </section>
  )
}
