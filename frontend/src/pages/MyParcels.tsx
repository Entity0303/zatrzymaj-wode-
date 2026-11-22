import { Map as MapIcon, Star, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { EmptyState } from '@/components/EmptyState'
import { FieldIllustration } from '@/components/FieldIllustration'
import { StatusBadge } from '@/components/StatusBadge'
import { PageHeader } from '@/layout/PageShell'
import { cropLabel } from '@/lib/crops'
import { formatDatePl, formatHa } from '@/lib/format'
import { useSavedParcels } from '@/lib/hooks'
import { useLang } from '@/lib/i18n'
import { goTo } from '@/lib/router'
import { useHistory } from '@/lib/storage'

/**
 * „Moje działki” (SPEC 3, 10): zapisane gwiazdką działki z tej przeglądarki, ostatni znany stan
 * (z historii analiz), szybkie przejście na mapę z ostatnią uprawą i datą.
 */
export default function MyParcels() {
  const { t } = useLang()
  const { saved, remove } = useSavedParcels()
  const [history] = useHistory()
  const [confirm, setConfirm] = useState<string | null>(null)

  return (
    <>
      <PageHeader title={t('Moje działki')} description={t('Działki zapisane gwiazdką w tej przeglądarce. Kliknij, aby wrócić do nich na mapie.')} />
      {saved.length === 0 ? (
        <div className="rounded-xl bg-surface p-8 shadow-card">
          <EmptyState
            illustration={<FieldIllustration className="w-48 rounded-xl" />}
            title="Nie masz jeszcze zapisanych działek"
            description={
              <>
                {t('Znajdź działkę na mapie i kliknij')} <Star className="inline size-4 align-[-2px] text-amber" aria-hidden />{' '}
                {t('w panelu działki.')}
              </>
            }
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
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {saved.map((p) => {
            const last = history.find((h) => h.parcel_id === p.id)
            return (
              <li key={p.id} className="flex flex-col gap-3 rounded-xl bg-surface p-5 shadow-card">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h2 className="font-name text-xl leading-7 font-semibold">{t('Działka {numer}', { numer: p.numer })}</h2>
                    <p className="text-sm leading-5 text-text-muted">
                      {t('gm. {gmina}, obręb {obreb}', { gmina: p.gmina, obreb: p.obreb })} · {formatHa(p.powierzchnia_ha)} ha
                    </p>
                  </div>
                  <Star className="size-5 shrink-0 fill-amber text-amber" aria-hidden />
                </div>
                {last ? (
                  <div className="space-y-1.5 rounded-lg bg-surface-2/60 p-3">
                    <StatusBadge status={last.level} size="sm" />
                    <p className="text-sm leading-5 font-medium">{t(last.headline)}</p>
                    <p className="text-xs leading-4 text-text-muted">
                      {cropLabel(last.crop)} · {t('analiza na {date}', { date: formatDatePl(last.date) })}
                    </p>
                  </div>
                ) : (
                  <p className="hatch-nodata rounded-lg p-3 text-sm leading-5 text-text-muted">{t('Jeszcze bez analizy – wybierz uprawę na mapie.')}</p>
                )}
                <div className="mt-auto flex gap-2">
                  <button
                    type="button"
                    onClick={() => goTo('start', { dzialka: p.id, uprawa: last?.crop ?? null, data: last?.date ?? null, widok: null })}
                    className="flex h-11 flex-1 items-center justify-center gap-2 rounded-md bg-brand-dark px-3 text-sm font-semibold text-white hover:bg-brand"
                  >
                    <MapIcon className="size-4" /> {t('Pokaż na mapie')}
                  </button>
                  {confirm === p.id ? (
                    <button
                      type="button"
                      onClick={() => {
                        remove(p.id)
                        setConfirm(null)
                      }}
                      className="h-11 rounded-md bg-danger px-3 text-sm font-semibold text-white"
                    >
                      {t('Na pewno usuń')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirm(p.id)}
                      aria-label={t('Usuń z moich działek')}
                      className="flex size-11 items-center justify-center rounded-md border text-text-muted hover:bg-surface-2"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}
