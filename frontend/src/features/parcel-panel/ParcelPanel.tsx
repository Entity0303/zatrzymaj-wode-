import { FileDown } from 'lucide-react'
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
import { KeyMetrics as Metrics } from './KeyMetrics'
import { PanelEmpty } from './PanelEmpty'
import { ParcelHeader } from './ParcelHeader'
import { SectionTitle } from './SectionTitle'
import { StatusCard } from './StatusCard'
import type { AnalysisRun, ForecastState, SearchPhase } from './types'
import { WhatToDo } from './WhatToDo'

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
}) {
  if (state.phase === 'idle') return <PanelEmpty onFocusSearch={onFocusSearch} onLocate={onLocate} />

  if (state.phase === 'loading')
    return (
      <div className="space-y-4">
        <LoadingSteps
          steps={[
            { label: state.kind === 'point' ? 'Szukam działki w tym miejscu (ULDK GUGiK)' : 'Szukam działki w ewidencji (ULDK GUGiK)', state: 'active' },
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
        title={`Znaleziono ${state.total} działek`}
        description="Ten numer jest w kilku miejscach. Wybierz swoją działkę z listy pod wyszukiwarką albo kliknij numer na mapie."
      />
    )

  const { parcel } = state
  const analysis = run.phase === 'done' ? run.analysis : null
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
      <StatusCard crop={crop} analysis={analysis} />
      {crop && (
        <details className="group rounded-xl border bg-surface p-3.5">
          <summary className="flex min-h-6 cursor-pointer list-none items-center justify-between text-sm font-medium">
            Postęp analizy
            <span className="text-text-muted group-open:hidden">pokaż</span>
            <span className="hidden text-text-muted group-open:inline">ukryj</span>
          </summary>
          <LoadingSteps steps={steps} className="mt-3" />
        </details>
      )}
      <section className="space-y-3">
        <SectionTitle>Kluczowe wskaźniki</SectionTitle>
        <Metrics analysis={analysis} />
      </section>
      <section className="space-y-3">
        <SectionTitle>Co zrobić?</SectionTitle>
        <WhatToDo analysis={analysis} />
      </section>
      <div className="space-y-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="block">
              <Button
                disabled
                className="pointer-events-none h-12 w-full rounded-md bg-brand-dark text-base font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
              >
                <FileDown className="size-5" /> Pobierz raport
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>Raport PDF – w budowie (najpierw analiza)</TooltipContent>
        </Tooltip>
        <p className="text-center">
          <span className="text-sm text-text-muted" aria-disabled>
            Zobacz pełny paszport wodny <span className="text-xs">(wkrótce)</span>
          </span>
        </p>
      </div>
      <footer className="border-t pt-3 text-xs leading-4 text-text-muted">
        Dane:{' '}
        {analysis
          ? analysis.reliability.sources.filter((s) => s.status !== 'brak').map((s) => s.name).join(', ')
          : `GUGiK (ULDK)${forecastState === 'ok' ? ', Open-Meteo' : ''}`}{' '}
        · stan na {formatDatePl(asOf)}
        <div className="mt-1.5">
          <SourceTag kind="pomiar" title="Granice i powierzchnia z ewidencji (ULDK GUGiK)" /> granice i powierzchnia
        </div>
      </footer>
    </div>
  )
}
