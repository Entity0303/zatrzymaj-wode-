import { BookOpenText, FileDown, Loader2 } from 'lucide-react'
import type { ErrorInfo } from '@/api/client'
import { ErrorNotice } from '@/components/ErrorNotice'
import { useLang } from '@/lib/i18n'

/** Pobieranie raportu z panelu: rodzaj raportu wprost (bez formularza) – z tą samą uprawą i okresem co analiza. */
export type PanelReport = {
  download: () => void
  /** F-MASTER A3: pobranie od razu wybranego rodzaju (domyślnie skrócony) */
  downloadType?: (type: 'short' | 'full') => void
  busy: boolean
  error: ErrorInfo | null
}

/**
 * Przyciski pod formularzem „Twoja działka” (F-MASTER A3): [Pobierz raport PDF] – główny, kolor marki (skrócony,
 * obok mały wybór „pełny”), [Otwórz paszport wodny] – drugorzędny, obramowany. Komputer obok siebie,
 * telefon jeden pod drugim.
 */
export function ReportActions({ report, onOpenPassport }: { report?: PanelReport; onOpenPassport?: () => void }) {
  const { t } = useLang()
  if (!report && !onOpenPassport) return null
  const get = (type: 'short' | 'full') => (report?.downloadType ? report.downloadType(type) : report?.download())
  return (
    <div className="space-y-2">
      {report?.error && <ErrorNotice {...report.error} onRetry={report.error.retryable ? () => get('short') : undefined} />}
      <div className="grid gap-2 sm:grid-cols-2">
        {report && (
          <div className="flex min-w-0 flex-col gap-1">
            <button
              type="button"
              onClick={() => get('short')}
              disabled={report.busy}
              className="flex h-12 items-center justify-center gap-2 rounded-md bg-brand-dark px-3 text-base font-semibold text-white hover:bg-brand disabled:opacity-60"
            >
              {report.busy ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <FileDown className="size-5" aria-hidden />}
              {t(report.busy ? 'Przygotowuję raport…' : 'Pobierz raport PDF')}
            </button>
            {report.downloadType && (
              <button
                type="button"
                onClick={() => get('full')}
                disabled={report.busy}
                className="self-center text-sm font-medium text-brand underline-offset-2 hover:underline disabled:opacity-60"
              >
                {t('albo pełny (szczegółowy)')}
              </button>
            )}
          </div>
        )}
        {onOpenPassport && (
          <button
            type="button"
            onClick={onOpenPassport}
            className="flex h-12 items-center justify-center gap-2 rounded-md border border-brand/50 bg-surface px-3 text-base font-semibold text-brand-dark hover:bg-sage-soft"
          >
            <BookOpenText className="size-5 text-brand" aria-hidden /> {t('Otwórz paszport wodny')}
          </button>
        )}
      </div>
    </div>
  )
}
