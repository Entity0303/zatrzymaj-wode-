import type { ErrorInfo } from '@/api/client'
import { ErrorNotice } from '@/components/ErrorNotice'
import { ReportButtons } from '@/features/reports/ReportButtons'
import type { ReportType } from '@/features/reports/useReportDownload'
import { useLang } from '@/lib/i18n'

/** Pobieranie raportu z panelu: rodzaj raportu wprost (bez formularza) – z tą samą uprawą, okresem i datą siewu co analiza. */
export type PanelReport = {
  download: () => void
  /** F-MASTER A3: pobranie od razu wybranego rodzaju */
  downloadType?: (type: ReportType) => void
  /** F25: ten sam rodzaj jeszcze raz („Spróbuj ponownie”) */
  retry?: () => void
  busy: boolean
  /** F25: który rodzaj się generuje – stan na klikniętym przycisku */
  busyType?: ReportType | null
  error: ErrorInfo | null
}

/**
 * F25: sekcja „Raport dla tej działki” pod formularzem „Twoja działka” – trzy przyciski pełnej szerokości, jeden pod
 * drugim: raport skrócony (główny), raport pełny, paszport wodny; każdy z tytułem i jednolinijkowym opisem.
 */
export function ReportActions({ report, onOpenPassport }: { report?: PanelReport; onOpenPassport?: () => void }) {
  const { t } = useLang()
  if (!report && !onOpenPassport) return null
  const get = (type: ReportType) => (report?.downloadType ? report.downloadType(type) : report?.download())
  return (
    <section aria-label={t('Raport dla tej działki')} className="space-y-2">
      <h3 className="text-sm leading-5 font-semibold text-text-muted">{t('Raport dla tej działki')}</h3>
      {report?.error && <ErrorNotice {...report.error} onRetry={report.error.retryable ? (report.retry ?? (() => get('short'))) : undefined} />}
      <ReportButtons onDownload={report ? get : undefined} busyType={report?.busyType ?? (report?.busy ? 'short' : null)} onOpenPassport={onOpenPassport} />
    </section>
  )
}
