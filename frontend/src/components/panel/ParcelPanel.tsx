import {
  ChartNoAxesCombined,
  Copy,
  Droplets,
  ExternalLink,
  FileDown,
  Gauge,
  Leaf,
  LocateFixed,
  MousePointerClick,
  MoreHorizontal,
  Search,
  Sprout,
  Star,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { ErrorInfo, Parcel } from '@/api'
import { FieldIllustration } from '@/components/common/Art'
import { EmptyState, ErrorNotice } from '@/components/common/Feedback'
import { LoadingSteps, type Step } from '@/components/common/LoadingSteps'
import { MetricCard } from '@/components/common/MetricCard'
import { RecommendationCard } from '@/components/common/RecommendationCard'
import { ScoreRing } from '@/components/common/ScoreRing'
import { SourceTag } from '@/components/common/SourceTag'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { CROPS, type CropId } from '@/lib/crops'
import { formatDatePl, formatHa, shortCounty } from '@/lib/format'
import { STATUS } from '@/lib/status'
import { cn } from '@/lib/utils'

export type SearchPhase =
  | { phase: 'idle' }
  | { phase: 'loading'; kind: 'number' | 'point' }
  | { phase: 'error'; error: ErrorInfo }
  | { phase: 'candidates'; total: number }
  | { phase: 'parcel'; parcel: Parcel }

export type ForecastState = 'idle' | 'loading' | 'ok' | 'error'

const geoportalUrl = (id: string) =>
  `https://mapy.geoportal.gov.pl/imap/Imgp_2.html?identifyParcel=${encodeURIComponent(id)}`

function SectionTitle({ children, icon: Icon }: { children: ReactNode; icon?: LucideIcon }) {
  return (
    <h3 className="flex items-center gap-2 text-lg leading-6 font-semibold">
      {Icon && <Icon className="size-5 text-brand" aria-hidden />}
      {children}
    </h3>
  )
}

// ── 1. Nagłówek ──────────────────────────────────────────────────────────────────────────────

export function ParcelHeader({
  parcel,
  saved,
  onToggleSave,
  onCopied,
}: {
  parcel: Parcel
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-ok-soft text-brand">
          <Leaf className="size-5" aria-hidden />
        </span>
        <h2 className="min-w-0 flex-1 text-[22px] leading-7 font-semibold break-words">Działka {parcel.numer}</h2>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="tabular shrink-0 text-lg leading-6 font-semibold">
              {formatHa(parcel.powierzchnia_ha)} ha
            </span>
          </TooltipTrigger>
          <TooltipContent>Pomiar – policzone z granic działki w ewidencji (ULDK GUGiK)</TooltipContent>
        </Tooltip>
      </div>
      <div className="flex items-start gap-2 pl-[52px]">
        <p className="min-w-0 flex-1 pt-1 text-sm leading-5 text-text-muted">
          gm. {parcel.gmina}, obręb {parcel.obreb} · {shortCounty(parcel.powiat)}
        </p>
        <div className="-mt-1 -mr-2 flex shrink-0">
          <ParcelActions parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />
        </div>
      </div>
    </div>
  )
}

/** ☆ zapisz działkę · ⋯ (kopiuj identyfikator, otwórz w Geoportalu) – SPEC 6.1 */
export function ParcelActions({
  parcel,
  saved,
  onToggleSave,
  onCopied,
}: {
  parcel: Parcel
  saved: boolean
  onToggleSave: () => void
  onCopied: () => void
}) {
  return (
    <>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-pressed={saved}
              aria-label={saved ? 'Usuń z moich działek' : 'Zapisz działkę'}
              onClick={onToggleSave}
              className="flex size-11 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
            >
              <Star className={cn('size-5', saved && 'fill-warn text-warn')} aria-hidden />
            </button>
          </TooltipTrigger>
          <TooltipContent>{saved ? 'Zapisana w tej przeglądarce' : 'Zapisz działkę'}</TooltipContent>
        </Tooltip>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Więcej opcji"
              className="flex size-11 items-center justify-center rounded-full text-text-muted hover:bg-surface-2"
            >
              <MoreHorizontal className="size-5" aria-hidden />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="z-[1500] w-64 rounded-xl">
            <DropdownMenuItem
              className="min-h-11 text-sm"
              onSelect={() => {
                navigator.clipboard?.writeText(parcel.id).then(onCopied, () => undefined)
              }}
            >
              <Copy className="size-4" /> Kopiuj identyfikator
              <span className="ml-auto max-w-24 truncate text-xs text-text-muted">{parcel.id}</span>
            </DropdownMenuItem>
            <DropdownMenuItem asChild className="min-h-11 text-sm">
              <a href={geoportalUrl(parcel.id)} target="_blank" rel="noreferrer">
                <ExternalLink className="size-4" /> Otwórz w Geoportalu
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
    </>
  )
}

// ── 2. Uprawa ────────────────────────────────────────────────────────────────────────────────

function CropField({ crop, onChange }: { crop: CropId | null; onChange: (c: CropId) => void }) {
  return (
    <div>
      <Select value={crop ?? ''} onValueChange={(v) => onChange(v as CropId)}>
        <SelectTrigger
          aria-label="Uprawa"
          className={cn(
            'h-12 w-full rounded-md border bg-surface-2 px-3.5 text-base data-[size=default]:h-12 [&_svg:not([class*=size-])]:size-5',
            !crop && 'border-warn bg-warn-soft',
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            <Sprout className="size-5 shrink-0 text-brand" aria-hidden />
            <span className="text-text-muted">Uprawa:</span>
            <SelectValue placeholder="wybierz…" />
          </span>
        </SelectTrigger>
        <SelectContent className="z-[1500] max-h-80 rounded-xl" position="popper">
          {CROPS.map((c) => (
            <SelectItem key={c.id} value={c.id} className="min-h-11 text-base">
              {c.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {!crop && <p className="mt-1.5 text-sm text-[#7a5d00]">Wybierz, co rośnie na tej działce</p>}
    </div>
  )
}

// ── 3. Karta stanu ───────────────────────────────────────────────────────────────────────────

function StatusCard({ crop }: { crop: CropId | null }) {
  const s = STATUS.nodata
  const Icon = s.icon
  return (
    <div className={cn('flex gap-3 rounded-xl border border-nodata/50 p-4', s.bg)}>
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-surface text-text-muted">
        <Icon className="size-6" aria-hidden />
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-base leading-6 font-semibold">Brak danych – analiza w budowie</p>
        </div>
        <p className="mt-0.5 text-sm leading-5 text-text-muted">
          {crop
            ? 'Ocena sytuacji wodnej (pogoda z 10 lat, gleba, teren, zdjęcia satelitarne) nie jest jeszcze liczona.'
            : 'Wybierz uprawę – od niej zależy ocena. Sama ocena sytuacji wodnej nie jest jeszcze liczona.'}
        </p>
        <StatusBadge status="nodata" size="sm" className="mt-2" />
      </div>
    </div>
  )
}

// ── 4. Kluczowe wskaźniki (2×2) ──────────────────────────────────────────────────────────────

function Metrics({ loading }: { loading?: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <MetricCard icon={Droplets} title="Woda w glebie" value={null} unit="%" tone="water" source="model" loading={loading}>
        <div className="h-2 rounded-full bg-surface-2" aria-hidden />
      </MetricCard>
      <MetricCard icon={Gauge} title="Ryzyko na 7 dni" value={null} tone="warn" source="prognoza" loading={loading} />
      <MetricCard icon={Leaf} title="Kondycja upraw" value={null} tone="brand" source="satelita" loading={loading}>
        {!loading && <ScoreRing value={null} size={48} stroke={5} className="self-start" />}
      </MetricCard>
      <MetricCard
        icon={ChartNoAxesCombined}
        title="Bilans wody (sezon)"
        value={null}
        unit="mm"
        tone="water"
        source="obliczenia"
        loading={loading}
      />
    </div>
  )
}

// ── 5. Co zrobić? ────────────────────────────────────────────────────────────────────────────

function WhatToDo() {
  return (
    <div className="space-y-3">
      <RecommendationCard
        noData
        category="retencja"
        title="Brak danych – analiza w budowie"
        text="Np. gdzie zatrzymać wodę spływającą z pola."
        why={
          <>
            Te rekomendacje policzymy z ukształtowania terenu (NMT GUGiK), rowów i zbiorników w okolicy (BDOT10k)
            oraz bilansu wody. Dziś te dane nie są jeszcze analizowane, więc niczego nie zalecamy.
          </>
        }
      />
      <RecommendationCard
        noData
        category="agrotechnika"
        title="Brak danych – analiza w budowie"
        text="Np. zabiegi, które pomagają glebie trzymać wodę."
        why={<>Policzymy je z kategorii gleby (IUNG), wybranej uprawy i bilansu wody z ostatnich 10 lat.</>}
      />
      <RecommendationCard
        noData
        category="nawadnianie"
        title="Brak danych – analiza w budowie"
        text="Czy i kiedy nawadniać – po analizie wody w glebie."
        why={<>Termin i dawkę policzymy z modelu wody w glebie i prognozy pogody na 16 dni.</>}
      />
    </div>
  )
}

// ── Pusty stan ───────────────────────────────────────────────────────────────────────────────

export function PanelEmpty({ onFocusSearch, onLocate }: { onFocusSearch: () => void; onLocate: () => void }) {
  const ways = [
    { icon: Search, title: 'Wpisz numer działki', text: 'np. Szczytno 112/11', action: onFocusSearch },
    { icon: MousePointerClick, title: 'Kliknij swoje pole na mapie', text: 'przybliż mapę i kliknij w działkę' },
    { icon: LocateFixed, title: 'Moja lokalizacja', text: 'gdy stoisz na polu', action: onLocate },
  ]
  return (
    <EmptyState
      illustration={<FieldIllustration className="w-40" />}
      title="Znajdź swoją działkę"
      description="Pokażemy granice pola i jego stan wodny."
    >
      <ul className="space-y-2 text-left">
        {ways.map(({ icon: Icon, title, text, action }) => {
          const inner = (
            <>
              <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-ok-soft text-brand">
                <Icon className="size-5" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block text-base leading-6 font-medium">{title}</span>
                <span className="block text-sm leading-5 text-text-muted">{text}</span>
              </span>
            </>
          )
          return (
            <li key={title}>
              {action ? (
                <button
                  type="button"
                  onClick={action}
                  className="flex min-h-14 w-full items-center gap-3 rounded-xl border bg-surface p-2.5 text-left hover:border-brand/50 hover:bg-ok-soft"
                >
                  {inner}
                </button>
              ) : (
                <div className="flex min-h-14 items-center gap-3 rounded-xl border bg-surface p-2.5">{inner}</div>
              )}
            </li>
          )
        })}
      </ul>
    </EmptyState>
  )
}

// ── Cały panel ───────────────────────────────────────────────────────────────────────────────

export function ParcelPanelBody({
  state,
  crop,
  onCropChange,
  asOf,
  forecastState,
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
  const steps: Step[] = [
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

  return (
    <div className="space-y-5">
      {!hideHeader && <ParcelHeader parcel={parcel} saved={saved} onToggleSave={onToggleSave} onCopied={onCopied} />}
      <CropField crop={crop} onChange={onCropChange} />
      <StatusCard crop={crop} />
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
        <Metrics />
      </section>
      <section className="space-y-3">
        <SectionTitle>Co zrobić?</SectionTitle>
        <WhatToDo />
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
        Dane: GUGiK (ULDK){forecastState === 'ok' ? ', Open-Meteo' : ''} · stan na {formatDatePl(asOf)}
        <div className="mt-1.5">
          <SourceTag kind="pomiar" title="Granice i powierzchnia z ewidencji (ULDK GUGiK)" /> granice i powierzchnia
        </div>
      </footer>
    </div>
  )
}
