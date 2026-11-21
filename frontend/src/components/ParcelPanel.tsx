import {
  AlertTriangle,
  Check,
  ChevronRight,
  Copy,
  Database,
  Loader2,
  MapPin,
  MousePointerClick,
  Search,
  LocateFixed,
} from 'lucide-react'
import { useState } from 'react'
import type { Parcel } from '@/api'
import { Badge } from '@/components/ui/badge'
import { formatDateTimePl } from '@/lib/dates'

const ha = (v: number) =>
  v.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: v < 1 ? 4 : 2 })

export type PanelState = {
  loading: boolean
  error: string | null
  parcel: Parcel | null
  candidates: Parcel[]
  totalCandidates: number
}

type Props = PanelState & {
  asOf: string
  onSelectCandidate: (p: Parcel) => void
}

function panelTitle(s: PanelState): string {
  if (s.loading) return 'Szukam działki…'
  if (s.parcel) return `Działka ${s.parcel.numer}`
  if (s.candidates.length) return `Znaleziono ${s.totalCandidates} działek`
  if (s.error) return 'Nie udało się'
  return 'Wybierz działkę'
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div role="alert" className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-red-600" />
      <p>{message}</p>
    </div>
  )
}

function HowToStart() {
  const steps = [
    { icon: Search, text: 'Wpisz numer działki – pełny identyfikator albo nazwę obrębu i numer.' },
    { icon: MousePointerClick, text: 'albo kliknij swoje pole na mapie,' },
    { icon: LocateFixed, text: 'albo stań na polu i naciśnij „Moja lokalizacja”.' },
  ]
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Pokażemy granice działki i jej dane z ewidencji. Wkrótce: ocena wody w glebie i rekomendacje.
      </p>
      <ul className="space-y-2">
        {steps.map(({ icon: Icon, text }) => (
          <li key={text} className="flex items-start gap-3 rounded-xl bg-muted/60 p-3 text-sm">
            <Icon className="mt-0.5 size-4 shrink-0 text-primary" />
            {text}
          </li>
        ))}
      </ul>
    </div>
  )
}

function CandidateList({
  candidates,
  total,
  onSelect,
}: {
  candidates: Parcel[]
  total: number
  onSelect: (p: Parcel) => void
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Ten numer występuje w kilku miejscach. Wybierz swoją działkę z listy lub kliknij punkt na mapie.
      </p>
      {total > candidates.length && (
        <p className="text-xs text-amber-700">
          Pokazano {candidates.length} z {total}. Dopisz nazwę obrębu, aby zawęzić wyniki.
        </p>
      )}
      <ul className="space-y-2">
        {candidates.map((c, i) => (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => onSelect(c)}
              className="group flex w-full items-center gap-3 rounded-xl border bg-card p-3 text-left transition-colors hover:border-primary/50 hover:bg-secondary"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">
                  Działka {c.numer} <span className="font-normal text-muted-foreground">· {ha(c.powierzchnia_ha)} ha</span>
                </span>
                <span className="block truncate text-sm text-muted-foreground">
                  obręb {c.obreb}, gm. {c.gmina}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  {c.powiat}, woj. {c.wojewodztwo}
                </span>
              </span>
              <ChevronRight className="size-4 shrink-0 text-muted-foreground group-hover:text-primary" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium" title={value}>
        {value}
      </dd>
    </div>
  )
}

function ParcelDetails({ parcel, asOf }: { parcel: Parcel; asOf: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(parcel.id)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* schowek niedostępny (np. http na telefonie) – pomijamy */
    }
  }
  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3 rounded-2xl bg-secondary p-4">
        <div>
          <p className="text-xs font-medium tracking-wide text-secondary-foreground/70 uppercase">Powierzchnia</p>
          <p className="text-3xl font-semibold text-secondary-foreground tabular-nums">
            {ha(parcel.powierzchnia_ha)} <span className="text-lg font-medium">ha</span>
          </p>
        </div>
        <MapPin className="mb-1 size-7 text-primary" />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <Row label="Gmina" value={parcel.gmina} />
        <Row label="Obręb" value={parcel.obreb} />
        <Row label="Powiat" value={parcel.powiat} />
        <Row label="Województwo" value={parcel.wojewodztwo} />
      </dl>

      <div>
        <p className="text-xs text-muted-foreground">Identyfikator działki</p>
        <div className="mt-1 flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2">
          <code className="min-w-0 flex-1 truncate text-sm">{parcel.id}</code>
          <button
            type="button"
            onClick={copy}
            title="Kopiuj identyfikator"
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            {copied ? <Check className="size-4 text-primary" /> : <Copy className="size-4" />}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-dashed p-3 text-sm text-muted-foreground">
        Ocena sytuacji wodnej na dzień <b className="text-foreground">{asOf}</b> – w przygotowaniu
        (pogoda z 10 lat, gleba, wilgotność, rekomendacje).
      </div>

      <div className="flex gap-2 border-t pt-3 text-xs text-muted-foreground">
        <Database className="mt-0.5 size-3.5 shrink-0" />
        <p>
          Źródło:{' '}
          <a className="font-medium text-foreground underline-offset-2 hover:underline" href={parcel.zrodlo.url} target="_blank" rel="noreferrer">
            {parcel.zrodlo.nazwa}
          </a>
          , pobrano {formatDateTimePl(parcel.zrodlo.pobrano)}.
          {parcel.zrodlo.uwagi && <> {parcel.zrodlo.uwagi}</>}
        </p>
      </div>
    </div>
  )
}

/** Zawartość panelu działki (ta sama na desktopie i w wysuwanym panelu na telefonie). */
export function ParcelPanelBody(props: Props) {
  const { loading, error, parcel, candidates, totalCandidates, asOf, onSelectCandidate } = props
  return (
    <div className="space-y-3">
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin text-primary" /> Pobieram dane z ewidencji (ULDK)…
        </div>
      )}
      {error && <ErrorBox message={error} />}
      {!loading && candidates.length > 0 && (
        <CandidateList candidates={candidates} total={totalCandidates} onSelect={onSelectCandidate} />
      )}
      {!loading && parcel && <ParcelDetails parcel={parcel} asOf={asOf} />}
      {!loading && !parcel && candidates.length === 0 && !error && <HowToStart />}
    </div>
  )
}

export function PanelHeader(props: PanelState) {
  const { parcel } = props
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <h2 className="truncate text-lg font-semibold">{panelTitle(props)}</h2>
        {parcel && (
          <Badge variant="secondary" className="shrink-0">
            ewidencja
          </Badge>
        )}
      </div>
      {parcel && (
        <p className="truncate text-sm text-muted-foreground">
          obręb {parcel.obreb}, gm. {parcel.gmina}
        </p>
      )}
    </div>
  )
}
