import type { ReportMeta } from '@/api/types'
import { cropLabel } from '@/lib/crops'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'

/**
 * Karta raportu na ekranie „Raporty” (SPEC 10.1, 14 ReportCard) – SZKIELET.
 * TODO (osoba B): miniatura mapy działki, odznaka stanu, akcje Otwórz · PDF · Drukuj · Kopiuj link.
 */
export function ReportCard({ report }: { report: ReportMeta }) {
  const { t } = useLang()
  return (
    <div className="rounded-xl border bg-surface p-4 shadow-card">
      <p className="font-semibold">
        {t('Działka {numer}', { numer: report.parcel_id })} · {cropLabel(report.crop)}
      </p>
      <p className="text-sm text-text-muted">{t('Analiza na {date}', { date: formatDatePl(report.analysis_date) })}</p>
      <a className="text-sm font-medium text-brand hover:underline" href={report.pdf_url}>
        PDF
      </a>
    </div>
  )
}
