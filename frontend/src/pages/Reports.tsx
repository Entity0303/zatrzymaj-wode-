import { Map as MapIcon } from 'lucide-react'
import { useState } from 'react'
import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'
import { ReportCard } from '@/features/reports/ReportCard'
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
