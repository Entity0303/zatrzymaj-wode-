import { BookOpenText, FileDown, Link2, Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { ErrorNotice } from '@/components/ErrorNotice'
import { ScoreRing } from '@/components/ScoreRing'
import { StatusBadge } from '@/components/StatusBadge'
import { cropLabel } from '@/lib/crops'
import { startLink } from '@/lib/deepLink'
import { formatDatePl, formatArea } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { goTo } from '@/lib/router'
import type { AnalysisRecord } from '@/lib/storage'
import { STATUS } from '@/theme/status'
import { useReportDownload } from './useReportDownload'

/**
 * Karta raportu (SPEC 10.1, 14 ReportCard): stan, działka, uprawa, data analizy;
 * akcje: Otwórz paszport · PDF · Kopiuj link · Usuń z historii.
 */
export function ReportCard({ report, onRemove, onCopied }: { report: AnalysisRecord; onRemove: () => void; onCopied: (ok: boolean) => void }) {
  const { t } = useLang()
  const pdf = useReportDownload({ parcelId: report.parcel_id, numer: report.numer, crop: report.crop, date: report.date })
  const [confirm, setConfirm] = useState(false)
  const link = { dzialka: report.parcel_id, uprawa: report.crop, data: report.date, widok: 'paszport' as const }
  const s = STATUS[report.level]

  function copy() {
    const href = startLink(link)
    if (!navigator.clipboard) return onCopied(false)
    navigator.clipboard.writeText(href).then(
      () => onCopied(true),
      () => onCopied(false),
    )
  }

  return (
    <li className="flex flex-col gap-3 rounded-xl bg-surface p-5 shadow-card">
      <div className="flex items-start gap-4">
        <ScoreRing value={report.score} size={64} stroke={7} color={s.ring.color} track={s.ring.track} />
        <div className="min-w-0 flex-1 space-y-1">
          <StatusBadge status={report.level} size="sm" />
          <h2 className="font-name text-xl leading-7 font-bold">{t('Działka {numer}', { numer: report.numer })}</h2>
          <p className="text-sm leading-5 text-text-muted">
            {cropLabel(report.crop)} · {t('analiza na {date}', { date: formatDatePl(report.date) })}
            {report.historical && <> · {t('analiza historyczna')}</>}
          </p>
          <p className="text-xs leading-4 text-text-muted">
            {t('gm. {gmina}, obręb {obreb}', { gmina: report.gmina, obreb: report.obreb })} · {formatArea(report.powierzchnia_ha)}
          </p>
        </div>
      </div>
      <p className="text-sm leading-5">{t(report.headline)}</p>
      {pdf.error && <ErrorNotice {...pdf.error} onRetry={pdf.error.retryable ? () => pdf.download() : undefined} />}
      <div className="mt-auto flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => goTo('start', link)}
          className="flex h-11 items-center gap-2 rounded-md bg-brand-dark px-4 text-sm font-semibold text-white hover:bg-brand"
        >
          <BookOpenText className="size-4" /> {t('Otwórz paszport')}
        </button>
        <button
          type="button"
          onClick={() => pdf.download()}
          disabled={pdf.busy}
          className="flex h-11 items-center gap-2 rounded-md border bg-surface px-3 text-sm font-medium hover:bg-surface-2 disabled:opacity-60"
        >
          {pdf.busy ? <Loader2 className="size-4 animate-spin" /> : <FileDown className="size-4 text-brand" />} PDF
        </button>
        <button
          type="button"
          onClick={copy}
          className="flex h-11 items-center gap-2 rounded-md border bg-surface px-3 text-sm font-medium hover:bg-surface-2"
        >
          <Link2 className="size-4 text-brand" /> {t('Kopiuj link')}
        </button>
        {confirm ? (
          <button type="button" onClick={onRemove} className="ml-auto h-11 rounded-md bg-danger px-3 text-sm font-semibold text-white">
            {t('Na pewno usuń')}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setConfirm(true)}
            aria-label={t('Usuń z historii')}
            className="ml-auto flex size-11 items-center justify-center rounded-md border text-text-muted hover:bg-surface-2"
          >
            <Trash2 className="size-4" />
          </button>
        )}
      </div>
    </li>
  )
}
