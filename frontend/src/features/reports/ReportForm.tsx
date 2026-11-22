import { FileDown, FileText, Files, Loader2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

export type ReportType = 'short' | 'full'

const TYPES: { key: ReportType; icon: typeof FileText; title: string; text: string }[] = [
  { key: 'short', icon: FileText, title: 'Raport skrócony (2 strony)', text: 'Werdykt, co siać, stan wody i najważniejsze działania – do wydruku i pokazania.' },
  { key: 'full', icon: Files, title: 'Raport szczegółowy', text: 'Wszystko z paszportu: wykresy z 10 lat, gleba, teren, źródła danych.' },
]

/**
 * „Przygotuj raport” (A5e-2): mały formularz zamiast natychmiastowego pobierania – rodzaj raportu
 * (skrócony 2 strony / szczegółowy) i przypomnienie, co zostanie uwzględnione (plan, historia pola,
 * powierzchnia – zmienia się je w „Doprecyzuj”). Pełna analityka jest w aplikacji (paszport).
 */
export function ReportForm({
  open,
  onClose,
  onGenerate,
  busy,
  included,
}: {
  open: boolean
  onClose: () => void
  onGenerate: (type: ReportType) => void
  busy: boolean
  /** krótki opis, co jest w raporcie, np. „plan: żyto · historia: 2 z 3 lat · 0,58 ha” */
  included: string[]
}) {
  const { t } = useLang()
  const [type, setType] = useState<ReportType>('short')

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-[1800] flex items-end justify-center bg-text/30 p-3 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-form-title"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md space-y-4 rounded-xl bg-surface p-5 shadow-float"
      >
        <header className="flex items-start gap-3">
          <h2 id="report-form-title" className="flex-1 text-xl leading-7 font-semibold">
            {t('Przygotuj raport')}
          </h2>
          <button type="button" onClick={onClose} aria-label={t('Zamknij')} className="-mt-1 -mr-2 flex size-10 items-center justify-center rounded-full text-text-muted hover:bg-surface-2">
            <X className="size-5" />
          </button>
        </header>

        <div role="radiogroup" aria-label={t('Rodzaj raportu')} className="space-y-2">
          {TYPES.map((o) => {
            const on = type === o.key
            const Icon = o.icon
            return (
              <button
                key={o.key}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setType(o.key)}
                className={cn('flex w-full items-start gap-3 rounded-xl border p-3.5 text-left transition-colors', on ? 'border-brand bg-sage-soft' : 'hover:bg-surface-2')}
              >
                <span className={cn('mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border-2', on ? 'border-brand' : 'border-line')} aria-hidden>
                  {on && <span className="size-2.5 rounded-full bg-brand" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 text-base leading-6 font-semibold">
                    <Icon className="size-4 text-brand" aria-hidden /> {t(o.title)}
                  </span>
                  <span className="block text-sm leading-5 text-text-muted">{t(o.text)}</span>
                </span>
              </button>
            )
          })}
        </div>

        <p className="text-sm leading-5 text-text-muted">
          {included.length ? `${t('W raporcie:')} ${included.join(' · ')}` : t('Możesz dodać plan upraw, historię pola i powierzchnię w „Doprecyzuj”.')}
        </p>

        <button
          type="button"
          onClick={() => onGenerate(type)}
          disabled={busy}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-md bg-brand text-base font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <FileDown className="size-5" aria-hidden />}
          {t(busy ? 'Przygotowuję raport…' : 'Generuj raport PDF')}
        </button>
      </div>
    </div>
  )
}
