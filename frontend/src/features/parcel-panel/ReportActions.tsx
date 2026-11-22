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
 * Przyciski pod formularzem „Twoja działka” (F-MASTER A3): [Raport PDF] – główny, kolor marki (skrócony, pod nim
 * mały link „albo pełny raport”), [Paszport wodny] – drugorzędny, obramowany. Dopisek: container query na kontenerze –
 * węższy niż ok. 440 px = jeden pod drugim na całą szerokość, szerszy – obok siebie po 50%; etykiety w jednej linii.
 */
export function ReportActions({ report, onOpenPassport }: { report?: PanelReport; onOpenPassport?: () => void }) {
  const { t } = useLang()
  if (!report && !onOpenPassport) return null
  const get = (type: 'short' | 'full') => (report?.downloadType ? report.downloadType(type) : report?.download())
  return (
    <div className="space-y-2">
      {report?.error && <ErrorNotice {...report.error} onRetry={report.error.retryable ? () => get('short') : undefined} />}
      <div className="@container">
      <div className="grid gap-2 @min-[440px]:grid-cols-2">
        {report && (
          <div className="flex min-w-0 flex-col gap-1">
            <button
              type="button"
              onClick={() => get('short')}
              disabled={report.busy}
              className="flex h-12 items-center justify-center gap-2 rounded-md bg-brand-dark px-3 text-base font-semibold whitespace-nowrap text-white hover:bg-brand disabled:opacity-60"
            >
              {report.busy ? <Loader2 className="size-5 shrink-0 animate-spin" aria-hidden /> : <FileDown className="size-5 shrink-0" aria-hidden />}
              {t(report.busy ? 'Przygotowuję…' : 'Raport PDF')}
            </button>
            {report.downloadType && (
              <button
                type="button"
                onClick={() => get('full')}
                disabled={report.busy}
                className="self-start text-sm font-medium whitespace-nowrap text-brand underline-offset-2 hover:underline disabled:opacity-60"
              >
                {t('albo pełny raport')}
              </button>
            )}
          </div>
        )}
        {onOpenPassport && (
          <button
            type="button"
            onClick={onOpenPassport}
            className="flex h-12 items-center justify-center gap-2 rounded-md border border-brand/50 bg-surface px-3 text-base font-semibold whitespace-nowrap text-brand-dark hover:bg-sage-soft"
          >
            <BookOpenText className="size-5 shrink-0 text-brand" aria-hidden /> {t('Paszport wodny')}
          </button>
        )}
      </div>
      </div>
    </div>
  )
}
