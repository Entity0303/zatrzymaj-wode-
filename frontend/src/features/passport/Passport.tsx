import { parcelShortName } from '@/features/parcel-panel/parcelTitle'
import { ArrowLeft, FileDown, Link2, Loader2, MoreHorizontal, Printer } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ErrorInfo } from '@/api/client'
import type { AnalysisResponse } from '@/api/types'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LogoMark } from '@/components/LogoMark'
import { WaveDivider } from '@/components/WaveDivider'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { BRAND_NAME } from '@/lib/brand'
import { cropLabel } from '@/lib/crops'
import { formatDatePl, formatHa } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { NonAgriculturalCard } from '@/features/parcel-panel/NonAgriculturalCard'
import { SoilCard } from '@/features/parcel-panel/SoilCard'
import { TerrainCard } from '@/features/parcel-panel/TerrainCard'
import { ApproxAreaBanner } from '@/features/parcel-panel/ApproxAreaBanner'
import { SectionA } from './SectionA'
import { SectionB } from './SectionB'
import { SectionC } from './SectionC'
import { SectionD } from './SectionD'
import { SectionE } from './SectionE'

/** Zakładki bez liter (uwagi z testów main). */
const NAV = [
  ['pass-a', 'Stan'],
  ['pass-b', 'Na tle 10 lat'],
  ['pass-c', 'Dlaczego'],
  ['pass-d', 'Co zrobić'],
  ['pass-e', 'Dane'],
] as const

/** Treść paszportu – wspólna dla ekranu i wydruku. */
function Content({ analysis, print, onShowOnMap }: { analysis: AnalysisResponse; print?: boolean; onShowOnMap?: (g: GeoJSON.Geometry) => void }) {
  const approx = (analysis.parcel.source === 'approximate' || analysis.approximate_area) && <ApproxAreaBanner />
  if (analysis.soil.non_agricultural)
    // SPEC 15.1: grunt nierolny – bez oceny suszy, tylko gleba, teren i wiarygodność danych
    return (
      <>
        {approx}
        <NonAgriculturalCard soil={analysis.soil} />
        <SoilCard soil={analysis.soil} />
        <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} />
        <WaveDivider />
        <SectionE analysis={analysis} />
      </>
    )
  return (
    <>
      {approx}
      <SectionA analysis={analysis} chartWidth={print ? 680 : undefined} />
      <WaveDivider />
      <SectionB analysis={analysis} chartWidth={print ? 680 : undefined} />
      <WaveDivider />
      <SectionC analysis={analysis} />
      <WaveDivider />
      <SectionD analysis={analysis} onShowOnMap={print ? undefined : onShowOnMap} />
      <WaveDivider />
      <SectionE analysis={analysis} />
    </>
  )
}

/**
 * Paszport wodny (SPEC 7) – pełny ekran (nie w prawym panelu): nagłówek w jednej linii
 * („Działka 6/1 · Wnory-Wandy · 0,58 ha · kukurydza”) + PDF + menu ⋯ (Drukuj, Kopiuj link),
 * pod nim przyklejone zakładki bez liter. Nagłówek kurczy się przy przewijaniu; pełne tło – nic nie prześwituje.
 * `print` – wersja do wydruku (bez przycisków, wykresy o stałej szerokości).
 */
export function Passport({
  analysis,
  onClose,
  report,
  onCopyLink,
  onShowOnMap,
  print,
}: {
  analysis: AnalysisResponse
  onClose?: () => void
  report?: { download: () => void; busy: boolean; error: ErrorInfo | null }
  onCopyLink?: () => void
  onShowOnMap?: (g: GeoJSON.Geometry) => void
  print?: boolean
}) {
  const { t } = useLang()
  const p = analysis.parcel
  const crop = cropLabel(analysis.crop)
  const approx = p.source === 'approximate' || p.source === 'drawn'
  const title = (
    approx
      ? [parcelShortName(p), `${formatHa(p.powierzchnia_ha)} ha`, crop?.toLowerCase()]
      : [t('Działka {numer}', { numer: p.numer }), p.obreb, `${formatHa(p.powierzchnia_ha)} ha`, crop?.toLowerCase()]
  )
    .filter(Boolean)
    .join(' · ')
  const scroller = useRef<HTMLDivElement>(null)
  const [small, setSmall] = useState(false)
  const [active, setActive] = useState<string>('pass-a')

  // aktywna zakładka = sekcja widoczna pod nagłówkiem
  useEffect(() => {
    const root = scroller.current
    if (!root || print) return
    const io = new IntersectionObserver(
      (entries) => {
        const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (vis[0]) setActive(vis[0].target.id)
      },
      { root, rootMargin: '-120px 0px -55% 0px' },
    )
    NAV.forEach(([id]) => {
      const el = root.querySelector(`#${id}`)
      if (el) io.observe(el)
    })
    return () => io.disconnect()
  }, [print, analysis])

  const jump = (id: string) => scroller.current?.querySelector(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  if (print)
    return (
      <article aria-label={t('Paszport wodny')} className="space-y-6">
        <header className="space-y-1">
          <p className="flex items-center gap-2 text-sm text-text-muted">
            <LogoMark className="size-6" /> {BRAND_NAME} · {t('Paszport wodny')} · {t('wygenerowano')} {formatDatePl(analysis.generated_at.slice(0, 10))}
          </p>
          <h2 className="font-name text-2xl leading-8 font-semibold">{title}</h2>
          <p className="text-sm text-text-muted">
            {t('stan na')} {formatDatePl(analysis.analysis_date)} · {t('gm. {gmina}, obręb {obreb}', { gmina: p.gmina, obreb: p.obreb })}
          </p>
        </header>
        <Content analysis={analysis} print />
      </article>
    )

  return (
    <div
      ref={scroller}
      onScroll={(e) => setSmall((e.currentTarget as HTMLDivElement).scrollTop > 24)}
      className="fixed inset-0 z-[1600] overflow-y-auto overscroll-contain bg-bg"
      role="dialog"
      aria-modal="true"
      aria-label={t('Paszport wodny')}
    >
      {/* nagłówek + zakładki: pełne tło, przyklejone, kurczą się przy przewijaniu */}
      <div className="sticky top-0 z-20 border-b bg-surface shadow-card">
        <header className={cn('mx-auto flex max-w-5xl items-center gap-2 px-3 transition-[padding] md:px-6', small ? 'py-1.5' : 'py-3')}>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 shrink-0 items-center gap-1.5 rounded-full pr-3 pl-2 text-sm font-semibold hover:bg-surface-2"
          >
            <ArrowLeft className="size-5 text-brand" aria-hidden /> <span className="max-sm:hidden">{t('Wróć do mapy')}</span>
          </button>
          <div className="min-w-0 flex-1">
            <p className={cn('text-xs leading-4 font-medium text-brand transition-all', small && 'h-0 overflow-hidden opacity-0')}>
              {t('Paszport wodny')} · {t('stan na')} {formatDatePl(analysis.analysis_date)}
              {analysis.historical && <> · {t('analiza historyczna')}</>}
            </p>
            <h2 className={cn('font-name truncate font-semibold transition-all', small ? 'text-base leading-6' : 'text-xl leading-7')}>{title}</h2>
          </div>
          {report && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={report.download}
                  disabled={report.busy}
                  aria-label={t('Pobierz PDF')}
                  className="flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-dark text-white hover:bg-brand disabled:opacity-60"
                >
                  {report.busy ? <Loader2 className="size-4 animate-spin" /> : <FileDown className="size-4" />}
                </button>
              </TooltipTrigger>
              <TooltipContent>{t('Pobierz PDF')}</TooltipContent>
            </Tooltip>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" aria-label={t('Więcej opcji')} className="flex size-10 shrink-0 items-center justify-center rounded-full border hover:bg-surface-2">
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
        {!analysis.soil.non_agricultural && (
          <nav aria-label={t('Sekcje paszportu')} className="scrollbar-none mx-auto flex max-w-5xl gap-1 overflow-x-auto px-3 pb-2 md:px-6">
            {NAV.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => jump(id)}
                aria-current={active === id ? 'true' : undefined}
                className={cn(
                  'h-8 shrink-0 rounded-full px-3 text-sm font-medium transition-colors',
                  active === id ? 'bg-brand text-white' : 'text-text-muted hover:bg-surface-2',
                )}
              >
                {t(label)}
              </button>
            ))}
          </nav>
        )}
      </div>

      <article className="relative z-0 mx-auto max-w-5xl space-y-6 px-3 py-6 md:px-6 [&_section[id^=pass-]]:scroll-mt-28">
        {report?.error && <ErrorNotice {...report.error} onRetry={report.error.retryable ? report.download : undefined} />}
        <Content analysis={analysis} onShowOnMap={onShowOnMap} />
      </article>
    </div>
  )
}
