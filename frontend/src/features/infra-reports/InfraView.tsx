import { ChevronDown, CircleCheck, MapPin, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import type { Hydro, InfraReport, InfraReportIn, Parcel } from '@/api/types'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { OBJECT, PROBLEM, TONE_HEX } from './infra'
import { InfraReportWizard } from './InfraReportWizard'
import { addMyReport, removeMyReport, useMyReports } from './myReports'

type Tab = 'zglos' | 'moje'

/**
 * Widok „Zgłoszenia” (F22): zakładki [Zgłoś problem] – kreator zgłoszenia, [Moje zgłoszenia] – lista wysłanych
 * w tej przeglądarce (localStorage, bez kont); zwijana karta „Co dalej z tym pomysłem”. Po wysłaniu – podziękowanie
 * i przejście do listy z nowym wpisem na górze.
 */
export function InfraView({
  parcel,
  point,
  hydro,
  onPickPoint,
  onClose,
  onSaved,
  onShow,
}: {
  parcel: Parcel | null
  point: [number, number] | null
  hydro?: Hydro | null
  onPickPoint: () => void
  onClose: () => void
  /** zgłoszenie zapisane na serwerze – odśwież pinezki */
  onSaved?: () => void
  /** „Pokaż na mapie” – wycentruj mapę na [lon, lat] */
  onShow: (p: [number, number]) => void
}) {
  const { t } = useLang()
  const [tab, setTab] = useState<Tab>('zglos')
  const [thanks, setThanks] = useState(false)
  const [ideaOpen, setIdeaOpen] = useState(false)
  // nowy kreator po wysłaniu (czyste pola)
  const [wizardKey, setWizardKey] = useState(0)
  const mine = useMyReports()

  function saved(sent: InfraReportIn, created: InfraReport | null) {
    addMyReport({
      id: created?.id ?? null,
      object_type: sent.object_type,
      problem: sent.problem,
      description: sent.description ?? null,
      lon: sent.lon,
      lat: sent.lat,
      created: created?.created_at ?? new Date().toISOString(),
    })
    onSaved?.()
    setThanks(true)
    setTab('moje')
    setWizardKey((k) => k + 1)
  }

  const tabBtn = (k: Tab, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={tab === k}
      onClick={() => {
        setTab(k)
        if (k === 'zglos') setThanks(false)
      }}
      className={cn(
        'h-11 flex-1 rounded-md px-3 text-sm font-semibold whitespace-nowrap transition-colors',
        tab === k ? 'bg-surface text-brand-dark shadow-sm' : 'text-text-muted hover:text-text',
      )}
    >
      {label}
    </button>
  )

  return (
    <section aria-label={t('Zgłoszenia')} className="flex max-h-full min-h-0 flex-col">
      <header className="space-y-3 border-b px-5 pt-4 pb-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display min-w-0 flex-1 text-xl leading-7 font-semibold">{t('Zgłoszenia')}</h2>
          <button type="button" onClick={onClose} aria-label={t('Zamknij')} className="flex size-11 items-center justify-center rounded-full hover:bg-surface-2">
            <X className="size-5" />
          </button>
        </div>
        <div role="tablist" aria-label={t('Zgłoszenia')} className="flex gap-1 rounded-lg bg-surface-2 p-1">
          {tabBtn('zglos', t('Zgłoś problem'))}
          {tabBtn('moje', mine.length ? t('Moje zgłoszenia ({n})', { n: mine.length }) : t('Moje zgłoszenia'))}
        </div>
        <div className="rounded-lg border">
          <button
            type="button"
            aria-expanded={ideaOpen}
            onClick={() => setIdeaOpen((o) => !o)}
            className="flex min-h-11 w-full items-center gap-2 px-3 text-left text-sm font-medium"
          >
            <span className="min-w-0 flex-1">{t('Co dalej z tym pomysłem')}</span>
            <ChevronDown className={cn('size-4 shrink-0 text-text-muted transition-transform', ideaOpen && 'rotate-180')} aria-hidden />
          </button>
          {ideaOpen && (
            <p className="px-3 pb-3 text-sm leading-5 text-text-muted">
              {t(
                'Dziś zgłoszenia pokazują stan rowów i zastawek na mapie. Docelowo mogłyby trafiać zbiorczo do gminnej spółki wodnej, Wód Polskich lub ODR, ze statusami: przyjęte, sprawdzone, naprawione.',
              )}
            </p>
          )}
        </div>
      </header>

      {tab === 'zglos' ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <InfraReportWizard key={wizardKey} embedded parcel={parcel} point={point} hydro={hydro} onPickPoint={onPickPoint} onClose={onClose} onSaved={saved} />
        </div>
      ) : (
        <div role="tabpanel" className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {thanks && (
            <p role="status" className="flex items-center gap-2 rounded-md bg-ok-soft px-3 py-2 text-sm leading-5 font-medium">
              <CircleCheck className="size-5 shrink-0 text-ok" aria-hidden /> {t('Dziękujemy – zgłoszenie przyjęte')}
            </p>
          )}
          {mine.length === 0 ? (
            <div className="space-y-3 rounded-xl bg-surface-2/60 p-4 text-center">
              <p className="text-base leading-6">{t('Nie wysłałeś jeszcze żadnego zgłoszenia.')}</p>
              <button type="button" onClick={() => setTab('zglos')} className="h-11 rounded-md bg-brand px-5 text-sm font-semibold text-white hover:bg-brand-dark">
                {t('Zgłoś problem')}
              </button>
            </div>
          ) : (
            <ul className="space-y-2">
              {mine.map((r) => (
                <li key={r.key} className="space-y-1.5 rounded-xl border bg-surface p-3">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-1.5 size-3 shrink-0 rounded-full" style={{ background: TONE_HEX[PROBLEM[r.problem]?.tone ?? 'warn'] }} aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-base leading-6 font-semibold">
                        {t(OBJECT[r.object_type]?.label ?? 'Zgłoszenie')} · {t(PROBLEM[r.problem]?.label ?? '')}
                      </p>
                      <p className="text-sm leading-5 text-text-muted">
                        {formatDatePl(r.created.slice(0, 10))} · {t('Status:')} <span className="font-medium text-text">{t('Przyjęte')}</span>
                      </p>
                      {r.description && <p className="mt-0.5 line-clamp-2 text-sm leading-5">{r.description}</p>}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 pl-[22px]">
                    <button
                      type="button"
                      onClick={() => onShow([r.lon, r.lat])}
                      className="flex h-11 items-center gap-1.5 rounded-md border bg-surface px-3 text-sm font-medium text-brand-dark hover:bg-surface-2"
                    >
                      <MapPin className="size-4 text-brand" aria-hidden /> {t('Pokaż na mapie')}
                    </button>
                    <button
                      type="button"
                      onClick={() => removeMyReport(r.key)}
                      className="flex h-11 items-center gap-1.5 rounded-md px-3 text-sm font-medium text-text-muted hover:bg-surface-2"
                    >
                      <Trash2 className="size-4" aria-hidden /> {t('Usuń z listy')}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs leading-4 text-text-muted">{t('Zgłoszenia są zapamiętane tylko w tej przeglądarce – nie zakładamy kont.')}</p>
        </div>
      )}
    </section>
  )
}
