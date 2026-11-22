import type { AnalysisResponse, ApproximateArea, CropRevenue, Hydro, LayerResponse, Parcel, PeriodSummary, PriceNow, Satellite, SearchResponse, Terrain, Verdict } from '@/api/types'
import type { Step } from '@/components/LoadingSteps'

/**
 * Przykładowa odpowiedź /api/analysis (mocks/analysis.sample.json) – WYŁĄCZNIE do pracy nad UI,
 * zanim backend policzy analizę. Włącza się tylko w trybie deweloperskim (npm run dev) i tylko
 * z parametrem w adresie: http://localhost:5173/?dane=przykladowe
 * W buildzie produkcyjnym ten kod (i plik JSON) jest usuwany. UI pokazuje wtedy „DANE PRZYKŁADOWE”.
 */
export const mockRequested = () =>
  import.meta.env.DEV && new URLSearchParams(window.location.search).get('dane') === 'przykladowe'

/** pojedynczy krok w symulacji trwa tyle, ile w mocku (`duration_ms`), ale nie dłużej niż 2,5 s */
const MAX_STEP_MS = 2500

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => {
      clearTimeout(t)
      reject(new DOMException('aborted', 'AbortError'))
    })
  })
}

/**
 * `?dane=przykladowe&wariant=obszar` – klik na mapie daje „obszar przybliżony” (jak przy braku działki w ULDK):
 * kwadrat 100 × 100 m wokół punktu + werdykt słabej działki z `verdict.weak.sample.json`. Tylko do pracy nad UI.
 */
export const mockApproxRequested = () => mockVariant('obszar')

/**
 * Warianty mocka (po przecinku): `?dane=przykladowe&wariant=obszar,adres,bez_tla,bez_wody`
 * – `obszar`: klik = obszar przybliżony · `adres`: wyszukiwarka zwraca search.address.sample.json (działka + adresy)
 * – `bez_tla`: teren i woda od razu w odpowiedzi (bez „Liczę…”) · `bez_wody`: brak sekcji hydro (jak stary backend)
 */
export function mockVariant(name: string): boolean {
  if (!mockRequested()) return false
  return (new URLSearchParams(window.location.search).get('wariant') ?? '').split(',').map((v) => v.trim()).includes(name)
}

/** Kwadrat ok. 1 ha wokół punktu – geometria „obszaru przybliżonego” w mocku. */
export function mockApproxParcel(lon: number, lat: number): Parcel {
  const dLat = 50 / 111320
  const dLon = 50 / (111320 * Math.cos((lat * Math.PI) / 180))
  const ring = [
    [lon - dLon, lat - dLat],
    [lon + dLon, lat - dLat],
    [lon + dLon, lat + dLat],
    [lon - dLon, lat + dLat],
    [lon - dLon, lat - dLat],
  ]
  return {
    id: `obszar_${lon.toFixed(5)}_${lat.toFixed(5)}`,
    wojewodztwo: 'wielkopolskie',
    powiat: '—',
    gmina: '—',
    obreb: '—',
    numer: '—',
    teryt_gminy: '',
    powierzchnia_ha: 1,
    geometria: { type: 'Polygon', coordinates: [ring] },
    zrodlo: { nazwa: 'DANE PRZYKŁADOWE', url: '', pobrano: new Date().toISOString(), uwagi: null },
    source: 'approximate',
    name: null,
  } as Parcel
}

/**
 * Symulacja ekranu ładowania na mocku: kroki z analysis.sample.json przechodzą kolejno
 * ⏳ → ✓ w tempie `duration_ms`, na końcu zwracamy przykładową odpowiedź (zdjęcie satelitarne „pending” –
 * dociąga je runMockSatellite). Z `point` – wariant obszaru przybliżonego.
 */
export async function runMockAnalysis(
  onSteps: (steps: Step[]) => void,
  signal: AbortSignal,
  point?: [number, number] | null,
  period?: string | null,
): Promise<AnalysisResponse> {
  const base = (await import('./analysis.choice.sample.json')).default as unknown as AnalysisResponse
  const data = await withF3(base, period)
  const final = data.steps
  for (let i = 0; i < final.length; i++) {
    onSteps(
      final.map((s, j) => ({
        label: s.label,
        state: j < i ? s.state : j === i ? 'active' : 'pending',
        note: j < i ? (s.note ?? undefined) : undefined,
      })),
    )
    await wait(Math.min(final[i].duration_ms ?? 500, MAX_STEP_MS), signal)
  }
  const pending: Satellite = {
    status: 'pending',
    sentence: 'Pobieram zdjęcie satelitarne…',
    series: [],
    layers: [],
    source_tag: { kind: 'brak_danych', date: null, source: 'Sentinel-2 L2A' },
  }
  if (!point) return { ...data, satellite: pending }
  const weak = (await import('./verdict.weak.sample.json')).default as unknown as { verdict: Verdict; approximate_area: ApproximateArea }
  return {
    ...data,
    parcel: mockApproxParcel(point[0], point[1]),
    verdict: weak.verdict,
    approximate_area: { ...weak.approximate_area, center: [point[0], point[1]] },
    satellite: pending,
  }
}

/**
 * F3 na mocku: ceny (prices.sample.json doklejane do rankingu, wyboru i alternatyw), teren i woda „pending”
 * (dociąga je runMockBackground), okres z period.sample.json, gdy zapytanie ma okres.
 */
async function withF3(a: AnalysisResponse, period?: string | null): Promise<AnalysisResponse> {
  const prices = (await import('./prices.sample.json')).default as unknown as { revenue: Record<string, CropRevenue>; price_now: PriceNow[] }
  const rev = <T extends { crop_id: string }>(x: T): T => ({ ...x, revenue: prices.revenue[x.crop_id] ?? null })
  const s = a.suggestions
  const out: AnalysisResponse = {
    ...a,
    price_now: prices.price_now,
    suggestions: s
      ? {
          ...s,
          groups: s.groups.map((g) => ({ ...g, items: g.items.map(rev) })),
          choice: s.choice?.map(rev),
          alternatives: s.alternatives?.map(rev),
        }
      : s,
  }
  if (!mockVariant('bez_tla')) out.terrain = { status: 'pending' }
  if (mockVariant('bez_wody')) out.hydro = undefined
  else out.hydro = mockVariant('bez_tla') ? ((await import('./hydro.sample.json')).default as unknown as Hydro) : { status: 'pending' }
  if (period) out.period = (await import('./period.sample.json')).default as unknown as PeriodSummary
  return out
}

/** Mock GET /api/terrain i /api/hydro: ok. 2,5–3,5 s „liczenia”, potem pliki przykładowe. */
export async function runMockBackground(kind: 'terrain', signal: AbortSignal): Promise<Terrain>
export async function runMockBackground(kind: 'hydro', signal: AbortSignal): Promise<Hydro>
export async function runMockBackground(kind: 'terrain' | 'hydro', signal: AbortSignal): Promise<Terrain | Hydro> {
  await wait(kind === 'terrain' ? 2500 : 3500, signal)
  return kind === 'terrain'
    ? ((await import('./terrain.sample.json')).default as unknown as Terrain)
    : ((await import('./hydro.sample.json')).default as unknown as Hydro)
}

/** Mock warstwy „Woda w okolicy”. */
export async function mockWaterLayer(): Promise<LayerResponse> {
  return (await import('./layers.woda.sample.json')).default as unknown as LayerResponse
}

/** Mock wyszukiwarki z adresami (wariant `adres`). */
export async function mockSearchAddress(): Promise<SearchResponse> {
  await new Promise((r) => setTimeout(r, 400))
  return (await import('./search.address.sample.json')).default as unknown as SearchResponse
}

/** Mock GET /api/satellite: ok. 2 s „pobierania”, potem satellite.sample.json. */
export async function runMockSatellite(signal: AbortSignal): Promise<Satellite> {
  await wait(2000, signal)
  return (await import('./satellite.sample.json')).default as unknown as Satellite
}
