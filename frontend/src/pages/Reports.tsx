import { Map as MapIcon, Search } from 'lucide-react'
import { useState } from 'react'
import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'
import { ErrorNotice } from '@/components/ErrorNotice'
import { MyReportsList } from '@/features/reports/MyReportsList'
import { ReportButtons } from '@/features/reports/ReportButtons'
import { ReportCard } from '@/features/reports/ReportCard'
import { useReportDownload } from '@/features/reports/useReportDownload'
import { cropLabel } from '@/lib/crops'
import { formatDatePl } from '@/lib/format'
import { PageHeader } from '@/layout/PageShell'
import { useLang } from '@/lib/i18n'
import { goTo } from '@/lib/router'
import { useHistory } from '@/lib/storage'

/**
 * „Raporty” (SPEC 10.1): poprzednie paszporty wodne z tej przeglądarki, najnowsze na górze.
 * Każdy można otworzyć ponownie (link przelicza analizę), pobrać jako PDF albo skopiować link.
 */
export default function Reports() {
  const { t } = useLang()
  const [history, setHistory] = useHistory()
  const [toast, setToast] = useState<string | null>(null)
  const [confirmAll, setConfirmAll] = useState(false)
  // F25: „wybrana działka” na tej stronie = ostatnio analizowana (historia w tej przeglądarce)
  const last = history[0] ?? null
  const pdf = useReportDownload(last ? { parcelId: last.parcel_id, numer: last.numer, obreb: last.obreb, gmina: last.gmina, crop: last.crop, date: last.date } : null)

  const flash = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }

  return (
    <>
      <PageHeader
        title={t('Raporty')}
        description={t('Twoje poprzednie paszporty wodne zapisane w tej przeglądarce. Otwórz ponownie, pobierz PDF albo wyślij link.')}
        actions={
          history.length > 0 &&
          (confirmAll ? (
            <button
              type="button"
              onClick={() => {
                setHistory([])
                setConfirmAll(false)
              }}
              className="h-11 rounded-md bg-danger px-4 text-sm font-semibold text-white"
            >
              {t('Na pewno wyczyść historię')}
            </button>
          ) : (
            <button type="button" onClick={() => setConfirmAll(true)} className="h-11 rounded-md border bg-surface px-4 text-sm font-medium hover:bg-surface-2">
              {t('Wyczyść historię')}
            </button>
          ))
        }
      />
      <div className="mb-6 space-y-6">
        <section aria-label={t('Raport dla tej działki')} className="rounded-xl bg-surface p-5 shadow-card">
          {last ? (
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] md:items-center">
              <div className="min-w-0">
                <p className="text-sm leading-5 text-text-muted">{t('Ostatnio analizowana działka')}</p>
                <p className="font-name text-xl leading-7 font-bold">{t('Działka {numer}', { numer: last.numer })}</p>
                <p className="text-sm leading-5 text-text-muted">
                  {t('gm. {gmina}, obręb {obreb}', { gmina: last.gmina, obreb: last.obreb })} · {cropLabel(last.crop)} · {t('analiza na {date}', { date: formatDatePl(last.date) })}
                </p>
              </div>
              <div className="space-y-2">
                {pdf.error && <ErrorNotice {...pdf.error} onRetry={pdf.error.retryable ? pdf.retry : undefined} />}
                <ReportButtons onDownload={(type) => void pdf.download(type)} busyType={pdf.busyType} />
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <p className="min-w-0 flex-1 text-base leading-6">{t('Wybierz działkę na mapie albo wpisz jej numer')}</p>
              <button
                type="button"
                onClick={() => goTo('start')}
                className="flex h-12 items-center gap-2 rounded-md bg-brand-dark px-5 text-base font-semibold whitespace-nowrap text-white hover:bg-brand"
              >
                <Search className="size-5" aria-hidden /> {t('Szukaj działki')}
              </button>
            </div>
          )}
        </section>
        <MyReportsList />
        {history.length > 0 && <h2 className="font-display text-xl leading-7 font-semibold">{t('Poprzednie analizy')}</h2>}
      </div>
      {history.length === 0 ? (
        <div className="rounded-xl bg-surface p-8 shadow-card">
          <EmptyState
            illustration={<FieldIllustration className="w-48 rounded-xl" />}
            title="Nie masz jeszcze raportów"
            description="Wykonaj analizę działki – wybierz działkę i uprawę na mapie. Każdy wynik pojawi się tutaj."
          >
            <button
              type="button"
              onClick={() => goTo('start')}
              className="mx-auto flex h-12 items-center gap-2 rounded-md bg-brand-dark px-5 text-base font-semibold text-white hover:bg-brand"
            >
              <MapIcon className="size-5" /> {t('Przejdź do mapy')}
            </button>
          </EmptyState>
        </div>
      ) : (
        <ul className="grid gap-4 lg:grid-cols-2">
          {history.map((r) => (
            <ReportCard
              key={`${r.parcel_id}|${r.crop}|${r.date}`}
              report={r}
              onRemove={() => setHistory(history.filter((h) => h !== r))}
              onCopied={(ok) => flash(ok ? t('Skopiowano link do tej analizy') : t('Nie udało się skopiować – otwórz paszport i skopiuj adres z paska'))}
            />
          ))}
        </ul>
      )}
      {toast && (
        <div role="status" className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-full bg-text px-4 py-2 text-sm text-white shadow-float md:bottom-6">
          {toast}
        </div>
      )}
    </>
  )
}
