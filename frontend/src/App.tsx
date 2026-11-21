import { Layers } from 'lucide-react'
import { useRef, useState, type TouchEvent } from 'react'
import { ApiError, api, describeError, type Candidates, type Parcel } from '@/api'
import { ParcelMap, type BaseMap } from '@/components/ParcelMap'
import { PanelHeader, ParcelPanelBody, type PanelState } from '@/components/ParcelPanel'
import { SideNav } from '@/components/SideNav'
import { TopBar } from '@/components/TopBar'
import { todayIso } from '@/lib/dates'
import { cn } from '@/lib/utils'

const EMPTY: PanelState = { loading: false, error: null, parcel: null, candidates: [], totalCandidates: 0 }

const GEO_ERRORS: Record<number, string> = {
  1: 'Nie masz zgody na lokalizację. Zezwól na nią w ustawieniach przeglądarki.',
  2: 'Nie udało się ustalić położenia. Spróbuj na zewnątrz lub wpisz numer działki.',
  3: 'Ustalanie położenia trwa zbyt długo. Spróbuj ponownie.',
}

export default function App() {
  const [state, setState] = useState<PanelState>(EMPTY)
  const [asOf, setAsOf] = useState(todayIso())
  const [baseMap, setBaseMap] = useState<BaseMap>('orto')
  const [pendingPoint, setPendingPoint] = useState<[number, number] | null>(null)
  const [userPoint, setUserPoint] = useState<[number, number] | null>(null)
  const [locating, setLocating] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(true)
  const reqId = useRef(0)
  const touchY = useRef<number | null>(null)

  async function find(fn: () => Promise<Parcel>, kind: 'number' | 'point') {
    const id = ++reqId.current
    setState((s) => ({ ...s, loading: true, error: null, candidates: [], totalCandidates: 0 }))
    setSheetOpen(true)
    try {
      const parcel = await fn()
      if (id !== reqId.current) return
      setState({ ...EMPTY, parcel })
    } catch (e) {
      if (id !== reqId.current) return
      if (e instanceof ApiError && e.status === 409) {
        const d = e.detail as Candidates
        setState({ ...EMPTY, candidates: d.candidates ?? [], totalCandidates: d.total ?? d.candidates?.length ?? 0 })
      } else {
        setState((s) => ({ ...s, loading: false, error: describeError(e, kind) }))
      }
    } finally {
      if (id === reqId.current) setPendingPoint(null)
    }
  }

  const searchByNumber = (q: string) => find(() => api.parcelById(q), 'number')

  function pickPoint(lon: number, lat: number) {
    setPendingPoint([lon, lat])
    find(() => api.parcelByPoint(lon, lat), 'point')
  }

  function selectCandidate(p: Parcel) {
    reqId.current++
    setState({ ...EMPTY, parcel: p })
  }

  function locate() {
    if (!navigator.geolocation) {
      setState((s) => ({ ...s, error: 'Ta przeglądarka nie udostępnia lokalizacji.' }))
      return
    }
    if (!window.isSecureContext) {
      setState((s) => ({
        ...s,
        error: 'Lokalizacja działa tylko przez bezpieczne połączenie (https) lub na tym komputerze (localhost).',
      }))
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        const { longitude, latitude } = pos.coords
        setUserPoint([longitude, latitude])
        pickPoint(longitude, latitude)
      },
      (err) => {
        setLocating(false)
        setSheetOpen(true)
        setState((s) => ({ ...s, error: GEO_ERRORS[err.code] ?? 'Nie udało się pobrać lokalizacji.' }))
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 },
    )
  }

  // gest przesunięcia panelu na telefonie
  const onTouchStart = (e: TouchEvent) => (touchY.current = e.touches[0].clientY)
  const onTouchEnd = (e: TouchEvent) => {
    if (touchY.current === null) return
    const dy = e.changedTouches[0].clientY - touchY.current
    if (dy > 40) setSheetOpen(false)
    if (dy < -40) setSheetOpen(true)
    touchY.current = null
  }

  return (
    <div className="relative h-dvh w-full overflow-hidden">
      <div className="absolute inset-0 md:left-[88px]">
        <ParcelMap
          baseMap={baseMap}
          parcel={state.parcel}
          candidates={state.candidates}
          pendingPoint={pendingPoint}
          userPoint={userPoint}
          onPick={pickPoint}
          onSelectCandidate={selectCandidate}
        />
      </div>

      <SideNav />
      <TopBar
        loading={state.loading}
        locating={locating}
        asOf={asOf}
        onAsOfChange={setAsOf}
        onSearch={searchByNumber}
        onLocate={locate}
      />

      {/* przełącznik podkładu mapy */}
      <div className="absolute top-[124px] right-2 z-[1000] flex items-center gap-1 rounded-full border bg-card/95 p-1 shadow-md md:top-auto md:right-auto md:bottom-6 md:left-[104px]">
        <Layers className="mx-1.5 hidden size-4 text-muted-foreground md:block" />
        {(
          [
            ['orto', 'Ortofotomapa'],
            ['osm', 'Mapa'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setBaseMap(key)}
            aria-pressed={baseMap === key}
            className={cn(
              'rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
              baseMap === key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* panel działki: na telefonie wysuwany od dołu, na komputerze karta po prawej */}
      <aside
        aria-label="Panel działki"
        className={cn(
          'fixed inset-x-0 bottom-0 z-[1060] flex max-h-[46dvh] flex-col rounded-t-3xl border bg-card shadow-[0_-8px_30px_rgb(0_0_0/0.15)] transition-transform duration-300',
          sheetOpen ? 'translate-y-0' : 'translate-y-[calc(100%-5.25rem)]',
          'md:absolute md:inset-x-auto md:top-[92px] md:right-4 md:bottom-auto md:max-h-[calc(100%-110px)] md:w-[380px] md:translate-y-0 md:rounded-2xl md:shadow-xl',
        )}
      >
        <button
          type="button"
          className="flex w-full flex-col items-stretch gap-2 px-5 pt-2 pb-3 text-left md:pointer-events-none md:pt-5"
          onClick={() => setSheetOpen((o) => !o)}
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
          aria-expanded={sheetOpen}
        >
          <span className="mx-auto h-1.5 w-10 rounded-full bg-muted-foreground/30 md:hidden" />
          <PanelHeader {...state} />
        </button>
        <div className="min-h-0 overflow-y-auto px-5 pb-5">
          <ParcelPanelBody {...state} asOf={asOf} onSelectCandidate={selectCandidate} />
        </div>
      </aside>
    </div>
  )
}
