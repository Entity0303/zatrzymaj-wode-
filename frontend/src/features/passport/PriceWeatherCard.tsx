import { useEffect, useState } from 'react'
import { api, type PriceWeather } from '@/api/client'
import type { AnalysisResponse } from '@/api/types'
import { formatNum } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { PassportCard } from './PassportCard'

/** Uprawy z cenami skupu GUS (produkt → etykieta) i kody upraw rankingu, które do nich należą. */
const PRODUCTS: { value: string; label: string; crops: string[] }[] = [
  { value: 'pszenica', label: 'Pszenica', crops: ['pszenica_ozima', 'zboza_ozime'] },
  { value: 'żyto', label: 'Żyto', crops: ['zyto'] },
  { value: 'jęczmień', label: 'Jęczmień', crops: ['jeczmien_ozimy', 'jeczmien_jary', 'zboza_jare'] },
  { value: 'owies', label: 'Owies', crops: ['owies'] },
  { value: 'pszenżyto', label: 'Pszenżyto', crops: ['pszenzyto_ozime'] },
  { value: 'kukurydza', label: 'Kukurydza na ziarno', crops: ['kukurydza_ziarno'] },
  { value: 'rzepak', label: 'Rzepak', crops: ['rzepak', 'rzepak_jesien'] },
  { value: 'ziemniaki', label: 'Ziemniaki', crops: ['ziemniak'] },
]

/** wynik na (region, uprawa, rok) – dane statyczne, bez ponownych zapytań przy przełączaniu */
const cache = new Map<string, PriceWeather>()

// wymiary wykresu (viewBox) – SVG skaluje się do szerokości karty
const W = 640
const H = 250
const PAD = { l: 44, r: 52, t: 12, b: 26 }
const COLOR = { rain: '#2F80C9', dry: '#E07B39', price: '#1E2A23', yield: '#2F6B47', grid: '#E4E0D6', muted: '#6B746E' }

function niceMax(v: number, step: number) {
  return Math.max(step, Math.ceil((v * 1.08) / step) * step)
}

/**
 * F32: „Ceny i pogoda na tle lat” – porównanie REGIONALNE (województwo działki albo cała Polska), nie dla działki.
 * Słupki = opad IV–IX w regionie (lata najsuchsze w kolorze ryzyka), linia ciągła = cena skupu (zł/t, prawa oś),
 * linia przerywana = plon w regionie (t/ha). Nad wykresem wniosek z danych, pod nim nota i źródła.
 */
export function PriceWeatherCard({ analysis }: { analysis: AnalysisResponse }) {
  const { t } = useLang()
  const woj = analysis.parcel.wojewodztwo?.trim() || null
  const ranked = (analysis.suggestions?.groups ?? []).flatMap((g) => g.items.map((i) => i.crop_id as string))
  const first = [...ranked, analysis.crop ?? ''].map((c) => PRODUCTS.find((p) => p.crops.includes(c))).find(Boolean)
  const [crop, setCrop] = useState<string>(first?.value ?? 'pszenica')
  const [region, setRegion] = useState<'woj' | 'PL'>(woj ? 'woj' : 'PL')
  const [hover, setHover] = useState<number | null>(null)
  const toYear = Number(analysis.analysis_date.slice(0, 4))
  const regionParam = region === 'woj' && woj ? woj : 'PL'
  const key = `${regionParam}|${crop}|${toYear}`
  const [state, setState] = useState<{ key: string; data: PriceWeather | null; error: boolean } | null>(null)

  useEffect(() => {
    const hit = cache.get(key)
    if (hit) return setState({ key, data: hit, error: false })
    const ctrl = new AbortController()
    api.priceWeather(regionParam, crop, toYear, ctrl.signal).then(
      (data) => {
        if (ctrl.signal.aborted) return
        cache.set(key, data)
        setState({ key, data, error: false })
      },
      () => !ctrl.signal.aborted && setState({ key, data: null, error: true }),
    )
    return () => ctrl.abort()
    // parametry zapytania zawarte w `key`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const cur = state?.key === key ? state : null
  const data = cur?.data ?? null
  const rows = (data?.years ?? []).filter((y) => y.precip_mm != null || y.price_pln_t != null || y.yield_t_ha != null)
  const dry = new Set(data?.dry_years ?? [])

  const tab = (k: 'woj' | 'PL', label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={region === k}
      onClick={() => setRegion(k)}
      className={cn(
        'h-10 flex-1 rounded-md px-3 text-sm font-semibold whitespace-nowrap transition-colors',
        region === k ? 'bg-surface text-pp-brand shadow-sm' : 'text-text-muted hover:text-text',
      )}
    >
      {label}
    </button>
  )

  let chart = null
  if (rows.length >= 2) {
    const w = W - PAD.l - PAD.r
    const h = H - PAD.t - PAD.b
    const rainMax = niceMax(Math.max(...rows.map((r) => r.precip_mm ?? 0), 100), 100)
    const priceMax = niceMax(Math.max(...rows.map((r) => r.price_pln_t ?? 0), 500), 250)
    const yieldMax = Math.max(...rows.map((r) => r.yield_t_ha ?? 0), 1) * 1.25
    const bw = w / rows.length
    const cx = (i: number) => PAD.l + bw * (i + 0.5)
    const y = (v: number, max: number) => PAD.t + h * (1 - v / max)
    const line = (get: (r: (typeof rows)[number]) => number | null | undefined, max: number) =>
      rows
        .map((r, i) => ({ v: get(r), i }))
        .filter((p): p is { v: number; i: number } => p.v != null)
        .map((p, n) => `${n ? 'L' : 'M'}${cx(p.i).toFixed(1)} ${y(p.v, max).toFixed(1)}`)
        .join('')
    const hv = hover != null ? rows[hover] : null
    chart = (
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label={t('Wykres: opady, cena skupu i plon w kolejnych latach')}>
          {[0, 0.5, 1].map((f) => (
            <g key={f}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(rainMax * f, rainMax)} y2={y(rainMax * f, rainMax)} stroke={COLOR.grid} strokeWidth={1} />
              <text x={PAD.l - 6} y={y(rainMax * f, rainMax) + 4} textAnchor="end" fontSize={12} fill={COLOR.rain}>
                {Math.round(rainMax * f)}
              </text>
              <text x={W - PAD.r + 6} y={y(priceMax * f, priceMax) + 4} fontSize={12} fill={COLOR.price}>
                {Math.round(priceMax * f)}
              </text>
            </g>
          ))}
          <text x={PAD.l - 6} y={PAD.t - 1} textAnchor="end" fontSize={11} fill={COLOR.rain}>
            mm
          </text>
          <text x={W - PAD.r + 6} y={PAD.t - 1} fontSize={11} fill={COLOR.price}>
            zł/t
          </text>
          {rows.map((r, i) => (
            <g key={r.year}>
              {r.precip_mm != null && (
                <rect
                  x={cx(i) - bw * 0.3}
                  y={y(r.precip_mm, rainMax)}
                  width={bw * 0.6}
                  height={Math.max(1, PAD.t + h - y(r.precip_mm, rainMax))}
                  rx={2}
                  fill={dry.has(r.year) ? COLOR.dry : COLOR.rain}
                  opacity={hover === null || hover === i ? 0.85 : 0.5}
                />
              )}
              {/* telefon: co drugi rok, żeby podpisy się nie zlewały */}
              <text x={cx(i)} y={H - 8} textAnchor="middle" fontSize={12} fill={COLOR.muted} className={cn((rows.length - 1 - i) % 2 === 1 && 'max-sm:hidden')}>
                {r.year}
              </text>
            </g>
          ))}
          <path d={line((r) => r.yield_t_ha, yieldMax)} fill="none" stroke={COLOR.yield} strokeWidth={2.2} strokeDasharray="6 4" />
          <path d={line((r) => r.price_pln_t, priceMax)} fill="none" stroke={COLOR.price} strokeWidth={2.4} />
          {rows.map((r, i) => (
            <g key={r.year}>
              {r.price_pln_t != null && <circle cx={cx(i)} cy={y(r.price_pln_t, priceMax)} r={hover === i ? 5 : 3} fill={COLOR.price} />}
              {r.yield_t_ha != null && <circle cx={cx(i)} cy={y(r.yield_t_ha, yieldMax)} r={hover === i ? 5 : 3} fill="#fff" stroke={COLOR.yield} strokeWidth={2} />}
              {/* pole najechania / dotknięcia na cały rok */}
              <rect
                x={cx(i) - bw / 2}
                y={PAD.t}
                width={bw}
                height={h + PAD.b}
                fill="transparent"
                onPointerEnter={() => setHover(i)}
                onPointerDown={() => setHover(i)}
                onPointerLeave={(e) => e.pointerType === 'mouse' && setHover(null)}
              />
            </g>
          ))}
        </svg>
        {hv && hover != null && (
          <div
            role="status"
            className="tabular pointer-events-none absolute top-1 z-10 w-max max-w-[15rem] rounded-lg border border-paper-line bg-surface px-3 py-2 text-sm leading-5 shadow-float"
            style={hover < rows.length / 2 ? { left: `${(cx(hover) / W) * 100 + 3}%` } : { right: `${100 - (cx(hover) / W) * 100 + 3}%` }}
          >
            <p className="font-semibold">
              {hv.year}
              {dry.has(hv.year) && <span className="font-medium text-pp-risk"> · {t('rok suchy')}</span>}
            </p>
            <p>{t('opad IV–IX: {v}', { v: hv.precip_mm == null ? t('brak danych') : `${formatNum(hv.precip_mm, 0)} mm` })}</p>
            <p>{t('cena skupu: {v}', { v: hv.price_pln_t == null ? t('brak danych') : `${formatNum(hv.price_pln_t, 0)} zł/t` })}</p>
            <p>{t('plon: {v}', { v: hv.yield_t_ha == null ? t('brak danych') : `${formatNum(hv.yield_t_ha, 1)} t/ha` })}</p>
          </div>
        )}
        <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs leading-4 text-text-muted" aria-hidden>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-3 rounded-sm" style={{ background: COLOR.rain }} /> {t('opad IV–IX, mm')}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-2.5 w-3 rounded-sm" style={{ background: COLOR.dry }} /> {t('lata najsuchsze')}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-0.5 w-4" style={{ background: COLOR.price }} /> {t('cena skupu, zł/t')}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <i className="inline-block h-0 w-4 border-t-2 border-dashed" style={{ borderColor: COLOR.yield }} /> {t('plon w regionie, t/ha')}
          </span>
        </p>
      </div>
    )
  }

  return (
    <div id="pp-ceny" className="scroll-mt-36">
      <PassportCard title={t('Ceny i pogoda na tle lat')}>
        <p className="-mt-2 mb-3 text-sm leading-5 text-text-muted">{t('Porównanie dla regionu – nie dla tej działki.')}</p>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div role="tablist" aria-label={t('Region')} className="flex min-w-0 flex-1 gap-1 rounded-lg bg-surface-2 p-1 sm:max-w-md">
            {woj && tab('woj', t('Województwo {w}', { w: woj }))}
            {tab('PL', t('Cała Polska'))}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-text-muted">{t('Uprawa')}</span>
            <select
              value={crop}
              onChange={(e) => setCrop(e.target.value)}
              className="h-10 rounded-md border border-paper-line bg-surface px-2 text-sm font-medium outline-none focus-visible:border-pp-brand"
            >
              {PRODUCTS.map((p) => (
                <option key={p.value} value={p.value}>
                  {t(p.label)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {!cur ? (
          <p className="text-sm leading-5 text-text-muted" role="status">
            {t('Wczytuję dane o cenach i opadach…')}
          </p>
        ) : cur.error || !data ? (
          <p className="text-sm leading-5 text-text-muted">{t('Nie udało się pobrać danych o cenach i opadach – spróbuj za chwilę.')}</p>
        ) : data.unavailable ? (
          <p className="text-sm leading-5 text-text-muted">{t(data.note_pl ?? 'brak cen skupu GUS dla tej uprawy')}</p>
        ) : (
          <div className="space-y-2">
            {data.summary_pl && <p className="text-base leading-6 font-medium">{data.summary_pl}</p>}
            {chart ?? <p className="text-sm leading-5 text-text-muted">{t('Za mało lat z danymi, żeby narysować wykres.')}</p>}
            {data.note_pl && <p className="text-sm leading-5">{data.note_pl}</p>}
            {data.sources.length > 0 && <p className="text-xs leading-4 text-text-muted">{t('Źródła: {src}.', { src: data.sources.join('; ') })}</p>}
          </div>
        )}
      </PassportCard>
    </div>
  )
}
