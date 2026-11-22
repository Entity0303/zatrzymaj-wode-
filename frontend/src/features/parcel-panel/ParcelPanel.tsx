import { BookOpenText, ChevronDown, FileDown, ListChecks, Loader2, Waves } from 'lucide-react'
import type { ErrorInfo } from '@/api/client'
import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { FieldIllustration } from '@/components/FieldIllustration'
import { LoadingSteps, type Step } from '@/components/LoadingSteps'
import { SourceTag } from '@/components/SourceTag'
import { Button } from '@/components/ui/button'
import { WaveDivider } from '@/components/WaveDivider'
import { formatDatePl } from '@/lib/format'
import { irrigationPracticed, irrigationShown } from '@/lib/crops'
import { AnalysisLoading } from './AnalysisLoading'
import { ApproxAreaBanner } from './ApproxAreaBanner'
import { FieldOverview, type RefineProps } from './FieldOverview'
import { RiskSummary } from './RiskSummary'
import { CropSeasonCard } from './CropSeasonCard'
import { IrrigationCard } from './IrrigationCard'
import { KeyMetrics as Metrics } from './KeyMetrics'
import { NonAgriculturalCard } from './NonAgriculturalCard'
import { PanelEmpty } from './PanelEmpty'
import type { Example } from './examples'
import { ParcelHeader } from './ParcelHeader'
import { SectionTitle } from './SectionTitle'
import { SoilCard } from './SoilCard'
import { SoilWaterCard } from './SoilWaterCard'
import { TerrainCard } from './TerrainCard'
import { StatusCard } from './StatusCard'
import type { AnalysisRun, ForecastState, SearchPhase } from './types'
import { WhatToDo } from './WhatToDo'
import { useLang } from '@/lib/i18n'
import { useSettings, useUiPrefs } from '@/lib/storage'
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
  onReportInfra,
  onExample,
  onClose,
}: {
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
  report?: { download: () => void; busy: boolean; error: ErrorInfo | null }
  /** otwiera paszport wodny (gdy jest wynik analizy) */
  onOpenPassport?: () => void
  /** podświetla miejsce rekomendacji na mapie */
  onShowOnMap?: (g: GeoJSON.Geometry) => void
  /** zgłoszenie stanu rowu / zbiornika w okolicy (SPEC 11) */
  onReportInfra?: () => void
  /** pusty stan: przykładowe analizy jednym klikiem */
  onExample?: (e: Example) => void
  /** zamyka działkę – powrót do mapy */
  onClose?: () => void
}) {
  const { t } = useLang()
  const crop = refine.crop
  const [settings] = useSettings()
  const [ui, setUi] = useUiPrefs()
  // tryb doradcy: szczegóły zawsze rozwinięte
  const showDetails = ui.details || settings.mode === 'doradca'
  if (state.phase === 'idle') return <PanelEmpty onFocusSearch={onFocusSearch} onLocate={onLocate} onExample={onExample} />

  if (state.phase === 'loading')
    return (
      <div className="space-y-4">
        <LoadingSteps
          steps={[
            {
              label: state.kind === 'point' ? 'Szukam działki w tym miejscu (ULDK GUGiK)' : 'Szukam działki w ewidencji (ULDK GUGiK)',
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
        title={t('Znaleziono {n} działek', { n: state.total })}
        description="Ten numer jest w kilku miejscach. Wybierz swoją działkę z listy pod wyszukiwarką albo kliknij numer na mapie."
      />
    )

  const { parcel } = state
  const analysis = run.phase === 'done' ? run.analysis : null
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
    { label: 'Pogoda z 10 lat', state: 'pending', note: 'w budowie' },
    { label: 'Gleba', state: 'pending', note: 'w budowie' },
    { label: 'Teren', state: 'pending', note: 'w budowie' },
    { label: 'Zdjęcia satelitarne', state: 'pending', note: 'w budowie' },
    { label: 'Bilans wody', state: 'pending', note: 'w budowie' },
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
          <RiskSummary analysis={analysis} />
          <FieldOverview analysis={analysis} refine={refine} showNow={!crop} />
        </>
      )}
      {!nonAgri && analysis && crop && (
        <>
          <WaveDivider />
          <StatusCard crop={crop} analysis={analysis} onOpen={onOpenPassport} />
          <section className="space-y-3">
            <SectionTitle>{t('Co zrobić?')}</SectionTitle>
            <WhatToDo analysis={analysis} onShowOnMap={onShowOnMap} />
          </section>
        </>
      )}
      <div className="space-y-2">
        {report?.error && <ErrorNotice {...report.error} onRetry={report.error.retryable ? report.download : undefined} />}
        {analysis && onOpenPassport && (
          <Button onClick={onOpenPassport} className="h-12 w-full rounded-md bg-brand-dark text-base font-semibold text-white hover:bg-brand">
            <BookOpenText className="size-5" /> {t('Pełny raport')}
          </Button>
        )}
        {analysis && report && (
          <Button variant="outline" onClick={report.download} disabled={report.busy} className="h-11 w-full rounded-md bg-surface text-base font-medium">
            {report.busy ? <Loader2 className="size-5 animate-spin" /> : <FileDown className="size-5 text-brand" />}
            {t(report.busy ? 'Przygotowuję raport…' : 'Pobierz raport PDF')}
          </Button>
        )}
      </div>
      {analysis && (
        <section className="rounded-xl border bg-surface">
          <button
            type="button"
            aria-expanded={showDetails}
            onClick={() => setUi({ details: !ui.details })}
            className="flex min-h-12 w-full items-center gap-2 px-4 py-2.5 text-left"
          >
            <ListChecks className="size-5 shrink-0 text-brand" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block text-base leading-6 font-semibold">{t(showDetails ? 'Ukryj szczegóły' : 'Pokaż szczegóły')}</span>
              <span className="block text-sm leading-5 text-text-muted">
                {t(
                  nonAgri
                    ? 'Teren, postęp analizy'
                    : !crop
                      ? 'Liczby, woda w glebie, gleba, teren'
                      : irrigationPracticed(crop) && irrigationShown(analysis)
                        ? 'Liczby, faza uprawy, woda w glebie, nawadnianie, gleba, teren'
                        : 'Liczby, faza uprawy, woda w glebie, gleba, teren',
                )}
              </span>
            </span>
            <ChevronDown className={cn('size-5 shrink-0 text-text-muted transition-transform', showDetails && 'rotate-180')} aria-hidden />
          </button>
          {showDetails && (
            <div className="space-y-3 border-t p-3">
              {!nonAgri && <Metrics analysis={analysis} />}
              {analysis && !nonAgri && analysis.crop_season && <CropSeasonCard season={analysis.crop_season} analysisDate={analysis.analysis_date} />}
              {analysis && !nonAgri && <SoilWaterCard state={analysis.soil_water} />}
              {analysis && !nonAgri && analysis.irrigation && irrigationShown(analysis) && <IrrigationCard plan={analysis.irrigation} />}
              {analysis && !nonAgri && <SoilCard soil={analysis.soil} />}
              {analysis && <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} />}
              <div className="rounded-xl border bg-surface p-3.5">
                <p className="text-sm font-medium">{t('Postęp analizy')}</p>
                <LoadingSteps steps={steps} className="mt-3" />
              </div>
            </div>
          )}
        </section>
      )}
      {onReportInfra && (
        <button
          type="button"
          onClick={onReportInfra}
          className="flex min-h-11 w-full items-center justify-center gap-2 rounded-md text-sm font-medium text-brand hover:bg-sage-soft"
        >
          <Waves className="size-4" aria-hidden /> {t('Zgłoś stan rowu lub zbiornika w okolicy')}
        </button>
      )}
      <footer className="border-t pt-3 text-xs leading-4 text-text-muted">
        {t('Dane:')}{' '}
        {analysis
          ? analysis.reliability.sources.filter((s) => s.status !== 'brak').map((s) => s.name).join(', ')
          : `GUGiK (ULDK)${forecastState === 'ok' ? ', Open-Meteo' : ''}`}{' '}
        · {t('stan na')} {formatDatePl(asOf)}
        <div className="mt-1.5">
          <SourceTag kind="pomiar" title={t('Granice i powierzchnia z ewidencji (ULDK GUGiK)')} /> {t('granice i powierzchnia')}
        </div>
      </footer>
    </div>
  )
}
