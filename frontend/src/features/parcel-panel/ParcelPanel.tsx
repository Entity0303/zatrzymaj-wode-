import { Loader2 } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { FieldIllustration } from '@/components/FieldIllustration'
import { LoadingSteps, type Step } from '@/components/LoadingSteps'
import { SourceTag } from '@/components/SourceTag'
import { formatDatePl, plForm } from '@/lib/format'
import { AnalysisLoading } from './AnalysisLoading'
import { ApproxAreaBanner } from './ApproxAreaBanner'
import { FieldOverview, type RefineProps } from './FieldOverview'
import { RiskSummary } from './RiskSummary'
import { ReportActions, type PanelReport } from './ReportActions'
import { KeyMetrics as Metrics } from './KeyMetrics'
import { NonAgriculturalCard } from './NonAgriculturalCard'
import { PanelEmpty } from './PanelEmpty'
import type { Example } from './examples'
import type { DemoExamples } from '@/features/intro/useDemoExamples'
import { ParcelHeader } from './ParcelHeader'
import { TerrainCard } from './TerrainCard'
import type { AnalysisRun, ForecastState, SearchPhase } from './types'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'

/** Panel działki (SPEC 6) – prawa karta na komputerze, treść szuflady na telefonie. */
export function ParcelPanel({
  state,
  refine,
  asOf,
  forecastState,
  run = { phase: 'idle' },
  onRetryAnalysis,
  saved,
  onToggleSave,
  onCopied,
  onRetry,
  onFocusSearch,
  onLocate,
  hideHeader,
  report,
  onOpenPassport,
  onShowOnMap,
  onExample,
  examples,
  onClose,
}: {
  /** przykłady z /api/demo/examples (pusty panel) */
  examples?: DemoExamples
  state: SearchPhase
  /** uprawa (opcjonalna), historia pola, powierzchnia – „Doprecyzuj” */
  refine: RefineProps
  asOf: string
  forecastState: ForecastState
  /** przebieg analizy (useAnalysis) */
  run?: AnalysisRun
  onRetryAnalysis?: () => void
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
  onRetry: () => void
  onFocusSearch: () => void
  onLocate: () => void
  /** na telefonie nagłówek jest w zwiniętej części szuflady */
  hideHeader?: boolean
  /** pobieranie raportu PDF (useReportDownload) */
  report?: PanelReport
  /** otwiera paszport wodny (gdy jest wynik analizy) */
  onOpenPassport?: () => void
  /** podświetla miejsce rekomendacji na mapie */
  onShowOnMap?: (g: GeoJSON.Geometry) => void
  /** pusty stan: przykładowe analizy jednym klikiem */
  onExample?: (e: Example) => void
  /** zamyka działkę – powrót do mapy */
  onClose?: () => void
}) {
  const { t } = useLang()
  const crop = refine.crop
  if (state.phase === 'idle') return <PanelEmpty onFocusSearch={onFocusSearch} onLocate={onLocate} onExample={onExample} examples={examples} />

  if (state.phase === 'loading')
    return (
      <div className="space-y-4">
        <LoadingSteps
          steps={[
            {
              label: state.kind === 'point' ? 'Szukam działki w tym miejscu' : 'Szukam działki w ewidencji gruntów',
              state: 'active',
            },
          ]}
        />
        <Metrics loading />
      </div>
    )

  if (state.phase === 'error')
    return (
      <div className="space-y-5">
        <ErrorNotice {...state.error} onRetry={state.error.retryable ? onRetry : undefined} />
        <PanelEmpty onFocusSearch={onFocusSearch} onLocate={onLocate} />
      </div>
    )

  if (state.phase === 'candidates')
    return (
      <EmptyState
        illustration={<FieldIllustration className="w-32" />}
        title={t(plForm(state.total, 'Znaleziono {n} działkę', 'Znaleziono {n} działki', 'Znaleziono {n} działek'), { n: state.total })}
        description="Ten numer jest w kilku miejscach. Wybierz swoją działkę z listy pod wyszukiwarką albo kliknij numer na mapie."
      />
    )

  const { parcel } = state
  const analysis = run.phase === 'done' ? run.analysis : null
  const recalc = run.phase === 'done' && !!run.recalculating
  const nonAgri = !!analysis?.soil.non_agricultural
  const steps: Step[] = analysis
    ? analysis.steps.map((s) => ({ label: s.label, state: s.state, note: s.note ?? undefined }))
    : [
    { label: 'Szukam działki (ULDK GUGiK)', state: 'done' },
    {
      label: 'Pobieram prognozę pogody (Open-Meteo)',
      state: forecastState === 'ok' ? 'done' : forecastState === 'error' ? 'error' : 'active',
      note: forecastState === 'error' ? 'Prognoza niedostępna – reszta działa dalej' : undefined,
    },
    { label: 'Pogoda z 10 lat', state: 'pending' },
    { label: 'Gleba', state: 'pending' },
    { label: 'Teren', state: 'pending' },
    { label: 'Zdjęcia satelitarne', state: 'pending' },
    { label: 'Bilans wody', state: 'pending' },
  ]

  const header = (
    <>
      {!hideHeader && <ParcelHeader parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} onClose={onClose} />}
      {(parcel.source === 'approximate' || analysis?.approximate_area) && <ApproxAreaBanner />}
    </>
  )

  // ekran ładowania analizy: mapa już pokazuje działkę, w panelu kroki i szkielety (SPEC 15.1)
  if (run.phase === 'loading')
    return (
      <div className="space-y-5">
        {header}
        <AnalysisLoading key={run.key} steps={run.steps} crop={crop} asOf={asOf} />
      </div>
    )

  return (
    <div className="space-y-5">
      {header}
      {run.phase === 'error' && (
        <ErrorNotice {...run.error} onRetry={run.error.retryable ? onRetryAnalysis : undefined} />
      )}
      {/* SPEC 15.1: grunt nierolny – zamiast oceny suszy komunikat, bez wskaźników i zaleceń */}
      {nonAgri && analysis && <NonAgriculturalCard soil={analysis.soil} onPickOther={onClose} />}
      {!nonAgri && analysis && (
        <>
          {/* F13: przeliczanie – poprzedni wynik przyciemniony, ta sama struktura (scroll i fokus zostają) */}
          {recalc && (
          <p role="status" className="sticky top-2 z-10 mx-auto flex w-fit items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-medium shadow-float">
            <Loader2 className="size-4 animate-spin text-brand" aria-hidden /> {t('Przeliczam…')}
          </p>
          )}
          <div className={cn('transition-opacity', recalc && 'opacity-50')}>
            <RiskSummary analysis={analysis} />
          </div>
          {/* F-MASTER A1: status → formularz „Twoja działka” → przyciski raportu → szczegóły (zwijane) */}
          <FieldOverview
            analysis={analysis}
            refine={refine}
            onShowOnMap={onShowOnMap}
            recalculating={recalc}
            actions={<ReportActions report={report} onOpenPassport={onOpenPassport} />}
            full
            steps={steps}
            onOpenPassport={onOpenPassport}
          />
        </>
      )}
      {nonAgri && analysis && (
        <>
          <ReportActions report={report} onOpenPassport={onOpenPassport} />
          <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} />
          <div className="rounded-xl border bg-surface p-3.5">
            <p className="text-sm font-medium">{t('Postęp analizy')}</p>
            <LoadingSteps steps={steps} className="mt-3" />
          </div>
        </>
      )}
      <footer className="border-t pt-3 text-xs leading-4 text-text-muted">
        {t('Dane:')}{' '}
        {analysis
          ? analysis.reliability.sources.filter((s) => s.status !== 'brak').map((s) => s.name).join(', ')
          : `GUGiK (ULDK)${forecastState === 'ok' ? ', Open-Meteo' : ''}`}{' '}
        · {t('stan na')} {formatDatePl(asOf)}
        <div className="mt-1.5">
          {parcel.source === 'drawn' ? (
            <>
              <SourceTag kind="obliczenia" title={t('Z Twojego rysunku – powierzchnia przybliżona')} /> {t('Z Twojego rysunku – powierzchnia przybliżona')}
            </>
          ) : (
            <>
              <SourceTag kind="pomiar" title={t('Granice i powierzchnia z ewidencji (ULDK GUGiK)')} /> {t('granice i powierzchnia')}
            </>
          )}
        </div>
      </footer>
    </div>
  )
}
