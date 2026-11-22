import { parcelShortName } from '@/features/parcel-panel/parcelTitle'
import { ArrowLeft, FileDown, Link2, Loader2, MoreHorizontal, Printer } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { ErrorInfo } from '@/api/client'
import type { AnalysisResponse } from '@/api/types'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LogoMark } from '@/components/LogoMark'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { REPORT_KINDS } from '@/features/reports/reportKinds'
import { consumePassportJump } from './jump'
import { BRAND_NAME } from '@/lib/brand'
import { cropLabel } from '@/lib/crops'
import { formatDatePl, formatArea, shortCounty } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { NonAgriculturalCard } from '@/features/parcel-panel/NonAgriculturalCard'
import { SoilCard } from '@/features/parcel-panel/SoilCard'
import { TerrainCard } from '@/features/parcel-panel/TerrainCard'
import { ApproxAreaBanner } from '@/features/parcel-panel/ApproxAreaBanner'
import { CropTableSection } from './CropTableSection'
import { WaterHistorySection } from './WaterHistorySection'
import { ActionsSection } from './ActionsSection'
import { SatelliteSection } from './SatelliteSection'
import { SourcesSection } from './SourcesSection'
import { TerrainSection } from './TerrainSection'
import { VerdictSection } from './VerdictSection'

/** Zakładki-kotwice (F6) – te same nazwy co nagłówki sekcji. */
const NAV = [
  ['pp-werdykt', 'Werdykt'],
  ['pp-posiac', 'Co tu posiać'],
  ['pp-woda', 'Woda na tle 10 lat'],
  ['pp-teren', 'Teren i okolica'],
  ['pp-satelita', 'Z satelity'],
  ['pp-dzialania', 'Co mogę zrobić?'],
  ['pp-zrodla', 'Skąd dane'],
] as const

/** F8: wybór okresu w pasku paszportu + stan przeliczania (stare dane przyciemnione) / błąd nowego okresu */
export type PassportPeriod = {
  /** przycisk „Okres: …” (PeriodPicker) */
  picker: ReactNode
  /** trwa przeliczanie dla nowego okresu – widać poprzedni wynik, przyciemniony */
  loading: boolean
  /** nowy okres się nie policzył – poprzedni wynik zostaje, komunikat z „Spróbuj ponownie” */
  error?: ErrorInfo | null
  onRetry?: () => void
}

/** Treść paszportu – wspólna dla ekranu i wydruku (F6: nowy układ sekcji). */
function Content({ analysis, print, onShowOnMap, refineForm }: { analysis: AnalysisResponse; print?: boolean; onShowOnMap?: (g: GeoJSON.Geometry) => void; refineForm?: ReactNode }) {
  const approx = (analysis.parcel.source === 'approximate' || analysis.approximate_area) && <ApproxAreaBanner />
  if (analysis.soil.non_agricultural)
    // SPEC 15.1: grunt nierolny – bez oceny suszy, tylko gleba, teren i wiarygodność danych
    return (
      <>
        {approx}
        <NonAgriculturalCard soil={analysis.soil} />
        <SoilCard soil={analysis.soil} />
        <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} />
        <SourcesSection analysis={analysis} />
      </>
    )
  return (
    <>
      {approx}
      <VerdictSection analysis={analysis} />
      <CropTableSection analysis={analysis} refineForm={refineForm} />
      <WaterHistorySection analysis={analysis} chartWidth={print ? 680 : undefined} />
      <div className="grid gap-7 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <TerrainSection analysis={analysis} />
        <SatelliteSection analysis={analysis} chartWidth={print ? 680 : undefined} />
      </div>
      <ActionsSection analysis={analysis} onShowOnMap={print ? undefined : onShowOnMap} />
      <SourcesSection analysis={analysis} />
    </>
  )
}

/**
 * Paszport wodny (SPEC 7, F6 – widok analityczny działki) – pełny ekran na papierowym tle (#F8F6F1), maks. 1240 px.
 * Pasek u góry (przyklejony): „Wróć do mapy” | nazwa działki + gmina/powiat · ha · data analizy | „Okres: …” |
 * „Raport PDF” (główny) | ⋯ (Drukuj, Kopiuj link). Pod nim zakładki-kotwice z podkreśleniem aktywnej; sekcje mają
 * scroll-margin-top, więc pasek nie zasłania nagłówków. `print` – wersja do wydruku (bez przycisków).
 */
export function Passport({
  analysis,
  onClose,
  report,
  onCopyLink,
  onShowOnMap,
  print,
  period,
  refineForm,
}: {
  period?: PassportPeriod
  analysis: AnalysisResponse
  onClose?: () => void
  report?: { download: () => void; downloadType?: (type: 'short' | 'full') => void; retry?: () => void; busy: boolean; busyType?: 'short' | 'full' | null; error: ErrorInfo | null }
  onCopyLink?: () => void
  onShowOnMap?: (g: GeoJSON.Geometry) => void
  print?: boolean
  /** „Podaj, co rosło” – ten sam formularz co w panelu (F6 sekcja 3) */
  refineForm?: ReactNode
}) {
  const { t } = useLang()
  const p = analysis.parcel
  const crop = cropLabel(analysis.crop)
  const approx = p.source === 'approximate' || p.source === 'drawn'
  const title = approx ? parcelShortName(p) : t('Działka {numer}, obręb {obreb}', { numer: p.numer, obreb: p.obreb })
  const sub = [
    approx ? null : t('gm. {gmina}, {powiat}', { gmina: p.gmina, powiat: shortCounty(p.powiat) }),
    formatArea(p.powierzchnia_ha),
    `${t('data analizy')} ${formatDatePl(analysis.analysis_date)}`,
    crop?.toLowerCase(),
  ]
    .filter(Boolean)
    .join(' · ')
  const scroller = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState<string>(NAV[0][0])

  // aktywna zakładka = sekcja widoczna pod paskiem
  useEffect(() => {
    const root = scroller.current
    if (!root || print) return
    const io = new IntersectionObserver(
      (entries) => {
        const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (vis[0]) setActive(vis[0].target.id)
      },
      { root, rootMargin: '-140px 0px -55% 0px' },
    )
    NAV.forEach(([id]) => {
      const el = root.querySelector(`#${id}`)
      if (el) io.observe(el)
    })
    return () => io.disconnect()
  }, [print, analysis])

  const jump = (id: string) => scroller.current?.querySelector(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  // F32: paszport otwarty linkiem z panelu („Ceny i pogoda na tle lat →”) – od razu w tej sekcji
  useEffect(() => {
    const id = consumePassportJump()
    if (!id) return
    const timer = setTimeout(() => scroller.current?.querySelector(`#${id}`)?.scrollIntoView({ block: 'start' }), 150)
    return () => clearTimeout(timer)
  }, [])

  if (print)
    return (
      <article aria-label={t('Paszport wodny')} className="space-y-6">
        <header className="space-y-1">
          <p className="flex items-center gap-2 text-sm text-text-muted">
            <LogoMark className="size-6" /> {BRAND_NAME} · {t('Paszport wodny')} · {t('wygenerowano')} {formatDatePl(analysis.generated_at.slice(0, 10))}
          </p>
          <h2 className="font-name text-2xl leading-8 font-bold">{title}</h2>
          <p className="text-sm text-text-muted">{sub}</p>
          {analysis.period && <p className="text-sm text-text-muted">{t('Okres: {label}', { label: t(analysis.period.label) })}</p>}
        </header>
        <Content analysis={analysis} print />
      </article>
    )

  const visibleNav = analysis.soil.non_agricultural ? [] : NAV
  return (
    <div ref={scroller} className="fixed inset-0 z-[1600] overflow-y-auto overscroll-contain bg-paper" role="dialog" aria-modal="true" aria-label={t('Paszport wodny')}>
      {/* pasek + zakładki: przyklejone, pełne tło */}
      <div className="sticky top-0 z-20 border-b border-paper-line bg-surface">
        <header className="mx-auto flex max-w-[1240px] items-center gap-2 px-3 py-2.5 md:gap-3 md:px-6">
          <button type="button" onClick={onClose} className="flex h-10 shrink-0 items-center gap-1.5 rounded-full pr-3 pl-2 text-sm font-semibold hover:bg-surface-2">
            <ArrowLeft className="size-5 text-pp-brand" aria-hidden /> <span className="max-sm:hidden">{t('Wróć do mapy')}</span>
          </button>
          <div className="min-w-0 flex-1">
            <h2 className="font-name truncate text-lg leading-6 font-bold md:text-xl md:leading-7">{title}</h2>
            <p className="truncate text-sm leading-5 text-text-muted">
              {sub}
              {analysis.historical && <> · {t('analiza historyczna')}</>}
            </p>
          </div>
          {period && !analysis.soil.non_agricultural && <div className="shrink-0 max-lg:hidden">{period.picker}</div>}
          {report && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  disabled={report.busy}
                  className="flex h-10 shrink-0 items-center gap-2 rounded-full bg-pp-brand px-4 text-sm font-semibold whitespace-nowrap text-white hover:bg-brand disabled:opacity-60"
                >
                  {report.busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <FileDown className="size-4" aria-hidden />}
                  <span className="max-sm:sr-only">{t(report.busy ? 'Generuję raport… (do ok. 30 s)' : 'Raport PDF')}</span>
                </button>
              </DropdownMenuTrigger>
              {/* F25: te same dwie opcje co w panelu – skrócony / pełny, z opisami */}
              <DropdownMenuContent align="end" className="z-[1700] w-[min(22rem,calc(100vw-1.5rem))] rounded-xl p-1.5">
                {REPORT_KINDS.map((k) => (
                  <DropdownMenuItem
                    key={k.type}
                    className="min-h-14 items-start gap-3 rounded-lg px-3 py-2"
                    onSelect={() => (report.downloadType ? report.downloadType(k.type) : report.download())}
                  >
                    <k.icon className="mt-0.5 size-5 shrink-0 text-pp-brand" aria-hidden />
                    <span className="min-w-0">
                      <span className="block text-sm leading-5 font-semibold">{t(k.title)}</span>
                      <span className="block text-sm leading-5 text-text-muted">{t(k.description)}</span>
                    </span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" aria-label={t('Więcej opcji')} className="flex size-10 shrink-0 items-center justify-center rounded-full border border-paper-line hover:bg-surface-2">
                <MoreHorizontal className="size-5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="z-[1700] w-52 rounded-xl">
              <DropdownMenuItem className="min-h-11 text-sm" onSelect={() => window.print()}>
                <Printer className="size-4" /> {t('Drukuj')}
              </DropdownMenuItem>
              {onCopyLink && (
                <DropdownMenuItem className="min-h-11 text-sm" onSelect={onCopyLink}>
                  <Link2 className="size-4" /> {t('Kopiuj link')}
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </header>
        {period && !analysis.soil.non_agricultural && <div className="mx-auto max-w-[1240px] px-3 pb-1.5 md:px-6 lg:hidden">{period.picker}</div>}
        {visibleNav.length > 0 && (
          <nav aria-label={t('Sekcje paszportu')} className="scrollbar-none mx-auto flex max-w-[1240px] gap-1 overflow-x-auto px-3 md:px-6">
            {visibleNav.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => jump(id)}
                aria-current={active === id ? 'true' : undefined}
                className={cn(
                  'h-10 shrink-0 border-b-2 px-2.5 text-sm font-medium transition-colors',
                  active === id ? 'border-pp-brand font-semibold text-pp-brand' : 'border-transparent text-text-muted hover:text-text',
                )}
              >
                {t(label)}
              </button>
            ))}
          </nav>
        )}
      </div>

      <article className="relative z-0 mx-auto max-w-[1240px] space-y-7 px-3 py-6 md:px-6 [&_[id^=pp-]]:scroll-mt-36 [&_section[id^=pass-]]:scroll-mt-36">
        {report?.error && <ErrorNotice {...report.error} onRetry={report.error.retryable ? (report.retry ?? report.download) : undefined} />}
        {period?.error && <ErrorNotice {...period.error} onRetry={period.error.retryable ? period.onRetry : undefined} />}
        {period?.loading && (
          <p role="status" className="sticky top-[148px] z-10 mx-auto flex w-fit items-center gap-2 rounded-full bg-surface px-4 py-2 text-sm font-medium shadow-float">
            <Loader2 className="size-4 animate-spin text-pp-brand" aria-hidden /> {t('Przeliczam dla wybranego okresu…')}
          </p>
        )}
        <div aria-busy={period?.loading || undefined} className={cn('space-y-7 transition-opacity', period?.loading && 'pointer-events-none opacity-50')}>
          <Content analysis={analysis} onShowOnMap={onShowOnMap} refineForm={refineForm} />
        </div>
      </article>
    </div>
  )
}
