import { Check, PenLine, Undo2, X } from 'lucide-react'
import { formatNum } from '@/lib/format'
import { drawProblem, ringAreaHa } from '@/lib/geoArea'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/**
 * „Narysuj swoje pole” (A5c, opcja dodatkowa): pływająca karta nad mapą – co robić, powierzchnia na żywo,
 * błąd obrysu po polsku, „Cofnij punkt”, „Anuluj”, „Gotowe”. Powierzchnia to podgląd; dokładną liczy serwer.
 */
export function DrawToolbar({
  points,
  onUndo,
  onCancel,
  onDone,
  className,
}: {
  points: [number, number][]
  onUndo: () => void
  onCancel: () => void
  onDone: () => void
  className?: string
}) {
  const { t } = useLang()
  const ha = ringAreaHa(points)
  const problem = drawProblem(points)
  const ready = points.length >= 3 && !problem
  return (
    <section
      aria-label={t('Narysuj swoje pole')}
      className={cn('w-[min(440px,calc(100vw-24px))] rounded-xl bg-surface p-3.5 shadow-float', className)}
    >
      <div className="flex items-start gap-2.5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-warn-soft text-[#875a12]">
          <PenLine className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base leading-6 font-semibold">{t('Narysuj swoje pole')}</h2>
          <p className="text-sm leading-5 text-text-muted" role="status">
            {t(
              points.length < 3
                ? 'Klikaj na mapie kolejne narożniki pola (najmniej 3).'
                : 'Dodaj kolejne narożniki albo kliknij „Gotowe” (lub pierwszy punkt).',
            )}
          </p>
        </div>
        <p className="shrink-0 text-right">
          <span className="block text-xs leading-4 text-text-muted">{t('Powierzchnia')}</span>
          <b className="tabular text-lg leading-6">{points.length >= 3 ? `${formatNum(ha, ha < 10 ? 2 : 1)} ha` : '—'}</b>
        </p>
      </div>
      {problem && <p className="mt-2 rounded-lg bg-danger-soft px-3 py-2 text-sm leading-5 text-danger">{t(problem)}</p>}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={onUndo}
          disabled={!points.length}
          className="flex h-11 items-center gap-1.5 rounded-md border px-3 text-sm font-medium hover:bg-surface-2 disabled:opacity-40"
        >
          <Undo2 className="size-4" aria-hidden /> <span className="max-[380px]:sr-only">{t('Cofnij punkt')}</span>
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex h-11 items-center gap-1.5 rounded-md border px-3 text-sm font-medium hover:bg-surface-2"
        >
          <X className="size-4" aria-hidden /> {t('Anuluj')}
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={!ready}
          className="ml-auto flex h-11 items-center gap-1.5 rounded-md bg-brand-dark px-4 text-sm font-semibold text-white hover:bg-brand disabled:opacity-40"
        >
          <Check className="size-4" aria-hidden /> {t('Gotowe')}
        </button>
      </div>
      <p className="mt-2 text-xs leading-4 text-text-muted">{t('Powierzchnia z rysunku jest przybliżona – dokładną policzymy z kształtu pola.')}</p>
    </section>
  )
}
