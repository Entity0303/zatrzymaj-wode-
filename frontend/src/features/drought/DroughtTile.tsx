import { Check, Globe, Info } from 'lucide-react'
import type { AnalysisResponse, CdiClass } from '@/api/types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { useDroughtContext } from './useDroughtContext'

/** Kolor klasy łącznego wskaźnika suszy: kropka w kolorze klasy, napis w ciemniejszym odcieniu (czytelność). */
const CDI_STYLE: Record<CdiClass, { dot: string; text: string }> = {
  brak: { dot: 'bg-pp-ok', text: 'text-ok' },
  obserwacja: { dot: 'bg-pp-warn', text: 'text-[#875a12]' },
  ostrzeżenie: { dot: 'bg-pp-risk', text: 'text-risk' },
  alarm: { dot: 'bg-pp-bad', text: 'text-pp-bad' },
  regeneracja: { dot: 'bg-pp-water', text: 'text-pp-water' },
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/**
 * F31: kafel „Tło suszowe w okolicy (EDO)” – niezależne potwierdzenie naszej oceny z Europejskiego Obserwatorium Suszy
 * (Copernicus): duża etykieta łącznego wskaźnika suszy w kolorze klasy, dekada, wilgotność gleby i ryzyko dla
 * rolnictwa w okolicy, zdanie porównujące z naszą oceną (✓ przy zgodności), małym drukiem rozdzielczość i źródło.
 * Brak odpowiedzi = kafel ukryty; usługa niedostępna = szary kafel z notą. `passport` – wersja szeroka do paszportu.
 */
export function DroughtTile({ analysis, passport }: { analysis: AnalysisResponse; passport?: boolean }) {
  const { t } = useLang()
  const ctx = useDroughtContext(analysis)
  if (!ctx) return null
  const title = t('Tło suszowe w okolicy (EDO)')
  const box = cn('min-w-0 bg-surface', passport ? 'rounded-[18px] border border-paper-line p-4 md:p-5' : 'rounded-xl border p-3.5')
  const head = (
    <p className="flex items-center gap-2 text-sm leading-5 font-semibold text-text-muted">
      <Globe className="size-4 shrink-0" aria-hidden /> {title}
    </p>
  )

  if (ctx.unavailable || !ctx.cdi)
    return (
      <section aria-label={title} className={cn(box, 'bg-surface-2')}>
        {head}
        <p className="mt-1.5 text-sm leading-5 text-text-muted">{t(ctx.note_pl ?? 'Brak danych')}</p>
      </section>
    )

  const style = CDI_STYLE[ctx.cdi.class] ?? CDI_STYLE.brak
  const sma = ctx.soil_moisture_anomaly
  const risk = ctx.agri_risk
  return (
    <section aria-label={title} className={box}>
      {head}
      <div className={cn('mt-1.5', passport && 'grid gap-x-6 gap-y-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]')}>
        <div className="space-y-1">
          <p className={cn('flex items-center gap-2 font-bold', style.text, passport ? 'text-[24px] leading-8' : 'text-xl leading-7')}>
            <span className={cn('size-3 shrink-0 rounded-full', style.dot)} aria-hidden />
            {cap(t(ctx.cdi.label_pl))}
          </p>
          <p className="text-sm leading-5 text-text-muted">{t(ctx.cdi.decade_label)}</p>
          {sma?.class && (
            <p className="text-sm leading-5">
              <span className="text-text-muted">{t('Wilgotność gleby w okolicy:')}</span> <b className="font-semibold">{t(sma.label_pl)}</b>
            </p>
          )}
          {risk && (
            <p className="text-sm leading-5">
              <span className="text-text-muted">{t('Ryzyko dla rolnictwa:')}</span> <b className="font-semibold">{t(risk.label_pl)}</b>
            </p>
          )}
        </div>
        <div className={cn('space-y-1.5', !passport && 'mt-2 border-t pt-2')}>
          {ctx.sentence && (
            <p className="flex gap-2 text-sm leading-5">
              {ctx.agrees ? (
                <Check className="mt-0.5 size-4 shrink-0 text-ok" strokeWidth={2.5} aria-label={t('zgodne z naszą oceną')} />
              ) : (
                <Info className="mt-0.5 size-4 shrink-0 text-text-muted" aria-hidden />
              )}
              <span>{t(ctx.sentence)}</span>
            </p>
          )}
          <p className="text-xs leading-4 text-text-muted">
            {t(ctx.resolution_note)} {t('Źródło:')} {ctx.source}.
          </p>
        </div>
      </div>
    </section>
  )
}
