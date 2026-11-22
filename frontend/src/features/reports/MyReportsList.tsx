import { FileDown, Loader2, Trash2 } from 'lucide-react'
import { ErrorNotice } from '@/components/ErrorNotice'
import { cropLabel } from '@/lib/crops'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { removeMyPdfReport, useMyPdfReports, type MyPdfReport } from './myReports'
import { useReportDownload } from './useReportDownload'

/** Jeden raport z listy: działka, data analizy, rodzaj, uprawa, kiedy wygenerowano; „Pobierz ponownie”, „Usuń z listy”. */
function Row({ r }: { r: MyPdfReport }) {
  const { t } = useLang()
  const pdf = useReportDownload({ ...r.params, numer: r.numer, obreb: r.obreb, gmina: r.gmina })
  const when = new Date(r.generated)
  const time = Number.isNaN(when.getTime()) ? '' : `${formatDatePl(r.generated.slice(0, 10))}, ${when.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })}`
  return (
    <li className="space-y-2 rounded-xl bg-surface p-4 shadow-card">
      <div className="min-w-0">
        <p className="font-name text-lg leading-6 font-bold">
          {t('Działka {numer}', { numer: r.numer })}
          {r.obreb && <span className="text-base font-medium text-text-muted"> · {t('obręb {obreb}', { obreb: r.obreb })}</span>}
        </p>
        <p className="text-sm leading-5">
          {t(r.type === 'full' ? 'Raport pełny' : 'Raport skrócony')} · {t('analiza na {date}', { date: formatDatePl(r.params.date) })} ·{' '}
          {r.params.crop ? cropLabel(r.params.crop) : t('bez wybranej uprawy')}
        </p>
        {time && <p className="text-xs leading-4 text-text-muted">{t('wygenerowano {when}', { when: time })}</p>}
      </div>
      {pdf.error && <ErrorNotice {...pdf.error} onRetry={pdf.error.retryable ? pdf.retry : undefined} />}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => pdf.download(r.type)}
          disabled={pdf.busy}
          className="flex h-11 items-center gap-2 rounded-md border border-brand/50 bg-surface px-3 text-sm font-semibold whitespace-nowrap text-brand-dark hover:bg-sage-soft disabled:opacity-60"
        >
          {pdf.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FileDown className="size-4 text-brand" aria-hidden />}
          {t(pdf.busy ? 'Generuję raport… (do ok. 30 s)' : 'Pobierz ponownie')}
        </button>
        <button
          type="button"
          onClick={() => removeMyPdfReport(r.key)}
          className="flex h-11 items-center gap-1.5 rounded-md px-3 text-sm font-medium whitespace-nowrap text-text-muted hover:bg-surface-2"
        >
          <Trash2 className="size-4" aria-hidden /> {t('Usuń z listy')}
        </button>
      </div>
    </li>
  )
}

/**
 * F25: „Moje raporty” – raporty PDF wygenerowane w tej przeglądarce (localStorage). „Pobierz ponownie” generuje ten
 * sam raport od nowa z tymi samymi parametrami; plików nie przechowujemy.
 */
export function MyReportsList() {
  const { t } = useLang()
  const list = useMyPdfReports()
  return (
    <section aria-label={t('Moje raporty')} className="space-y-3">
      <h2 className="font-display text-xl leading-7 font-semibold">{t('Moje raporty')}</h2>
      {list.length === 0 ? (
        <p className="rounded-xl bg-surface p-5 text-base leading-6 text-text-muted shadow-card">
          {t('Nie wygenerowałeś jeszcze raportu w tej przeglądarce. Każdy pobrany raport pojawi się tutaj.')}
        </p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {list.map((r) => (
            <Row key={r.key} r={r} />
          ))}
        </ul>
      )}
      <p className="text-sm leading-5 text-text-muted">{t('Raporty generujemy z aktualnych danych przy każdym pobraniu – nie przechowujemy ich na serwerze.')}</p>
    </section>
  )
}
