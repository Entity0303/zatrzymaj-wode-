import { FileDown, Link2, Loader2 } from 'lucide-react'
import type { ErrorInfo } from '@/api/client'
import type { CropId } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorNotice } from '@/components/ErrorNotice'
import { FieldIllustration } from '@/components/FieldIllustration'
import { LoadingSteps, type Step } from '@/components/LoadingSteps'
import { SourceTag } from '@/components/SourceTag'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatDatePl } from '@/lib/format'
import { AnalysisLoading } from './AnalysisLoading'
import { CropField } from './CropField'
import { CropSeasonCard } from './CropSeasonCard'
import { IrrigationCard } from './IrrigationCard'
import { KeyMetrics as Metrics } from './KeyMetrics'
import { NonAgriculturalCard } from './NonAgriculturalCard'
import { PanelEmpty } from './PanelEmpty'
import { ParcelHeader } from './ParcelHeader'
import { SectionTitle } from './SectionTitle'
import { SoilCard } from './SoilCard'
import { SoilWaterCard } from './SoilWaterCard'
import { StatusCard } from './StatusCard'
import type { AnalysisRun, ForecastState, SearchPhase } from './types'
import { WhatToDo } from './WhatToDo'
import { useLang } from '@/lib/i18n'

/** Panel działki (SPEC 6) – prawa karta na komputerze, treść szuflady na telefonie. */
export function ParcelPanel({
  state,
  crop,
  onCropChange,
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
  onCopyLink,
}: {
  state: SearchPhase
  crop: CropId | null
  onCropChange: (c: CropId) => void
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
  /** kopiuje link z działką, uprawą i datą */
  onCopyLink?: () => void
}) {
  const { t } = useLang()
  if (state.phase === 'idle') return <PanelEmpty onFocusSearch={onFocusSearch} onLocate={onLocate} />

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
      {!hideHeader && <ParcelHeader parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />}
      <CropField crop={crop} onChange={onCropChange} />
    </>
  )

  // ekran ładowania analizy: mapa już pokazuje działkę, w panelu kroki i szkielety (SPEC 15.1)
  if (run.phase === 'loading' && crop)
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
      {nonAgri ? <NonAgriculturalCard soil={analysis!.soil} /> : <StatusCard crop={crop} analysis={analysis} />}
      {analysis && !nonAgri && <CropSeasonCard season={analysis.crop_season} analysisDate={analysis.analysis_date} />}
      {crop && (
        <details className="group rounded-xl border bg-surface p-3.5">
          <summary className="flex min-h-6 cursor-pointer list-none items-center justify-between text-sm font-medium">
            {t('Postęp analizy')}
            <span className="text-text-muted group-open:hidden">{t('pokaż')}</span>
            <span className="hidden text-text-muted group-open:inline">{t('ukryj')}</span>
          </summary>
          <LoadingSteps steps={steps} className="mt-3" />
        </details>
      )}
      {!nonAgri && (
        <>
          <section className="space-y-3">
            <SectionTitle>{t('Kluczowe wskaźniki')}</SectionTitle>
            <Metrics analysis={analysis} />
            {analysis && <SoilWaterCard state={analysis.soil_water} />}
          </section>
          <section className="space-y-3">
            <SectionTitle>{t('Co zrobić?')}</SectionTitle>
            <WhatToDo analysis={analysis} />
            {analysis && <IrrigationCard plan={analysis.irrigation} />}
          </section>
        </>
      )}
      {analysis && (
        <section className="space-y-3">
          <SectionTitle>{t('Gleba')}</SectionTitle>
          <SoilCard soil={analysis.soil} />
        </section>
      )}
      <div className="space-y-2">
        {report?.error && <ErrorNotice {...report.error} onRetry={report.error.retryable ? report.download : undefined} />}
        {analysis && report ? (
          <Button
            onClick={report.download}
            disabled={report.busy}
            className="h-12 w-full rounded-md bg-brand-dark text-base font-semibold text-white hover:bg-brand"
          >
            {report.busy ? <Loader2 className="size-5 animate-spin" /> : <FileDown className="size-5" />}
            {t(report.busy ? 'Przygotowuję raport…' : 'Pobierz raport PDF')}
          </Button>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0} className="block">
                <Button
                  disabled
                  className="pointer-events-none h-12 w-full rounded-md bg-brand-dark text-base font-semibold text-white disabled:opacity-60"
                >
                  <FileDown className="size-5" /> {t('Pobierz raport PDF')}
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>{t(crop ? 'Raport powstaje z gotowej analizy' : 'Najpierw wybierz uprawę – raport powstaje z analizy')}</TooltipContent>
          </Tooltip>
        )}
        {onCopyLink && (
          <Button variant="outline" onClick={onCopyLink} className="h-11 w-full rounded-md bg-surface text-base font-medium">
            <Link2 className="size-5 text-brand" /> {t('Kopiuj link do tej analizy')}
          </Button>
        )}
        <p className="text-center">
          <span className="text-sm text-text-muted" aria-disabled>
            {t('Zobacz pełny paszport wodny')} <span className="text-xs">({t('wkrótce')})</span>
          </span>
        </p>
      </div>
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
