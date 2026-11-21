import { ArrowLeft, FileDown, Link2, Loader2, Printer } from 'lucide-react'
import type { ErrorInfo } from '@/api/client'
import type { AnalysisResponse } from '@/api/types'
import { ErrorNotice } from '@/components/ErrorNotice'
import { LogoMark } from '@/components/LogoMark'
import { WaveDivider } from '@/components/WaveDivider'
import { BRAND_NAME } from '@/lib/brand'
import { cropLabel } from '@/lib/crops'
import { formatDatePl, formatHa } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { NonAgriculturalCard } from '@/features/parcel-panel/NonAgriculturalCard'
import { SoilCard } from '@/features/parcel-panel/SoilCard'
import { TerrainCard } from '@/features/parcel-panel/TerrainCard'
import { SectionA } from './SectionA'
import { SectionB } from './SectionB'
import { SectionC } from './SectionC'
import { SectionD } from './SectionD'
import { SectionE } from './SectionE'

const NAV = [
  ['pass-a', 'A', 'Stan'],
  ['pass-b', 'B', '10 lat'],
  ['pass-c', 'C', 'Dlaczego'],
  ['pass-d', 'D', 'Co zrobić'],
  ['pass-e', 'E', 'Dane'],
] as const

/**
 * Paszport wodny (SPEC 7): sekcje A–E. Komputer – szeroki panel zamiast panelu działki,
 * telefon – pełna szuflada; przyciski „Pobierz PDF”, „Drukuj”, „Kopiuj link”.
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
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  return (
    <article aria-label={t('Paszport wodny')} className="space-y-6">
      <header className={print ? 'space-y-2' : 'sticky top-0 z-10 -mx-5 -mt-5 space-y-3 border-b bg-surface/95 px-5 pt-4 pb-3 backdrop-blur'}>
        {print && (
          <p className="flex items-center gap-2 text-sm text-text-muted">
            <LogoMark className="size-6" /> {BRAND_NAME} · {t('wygenerowano')} {formatDatePl(analysis.generated_at.slice(0, 10))}
          </p>
        )}
        <div className="flex items-start gap-2">
          {onClose && !print && (
            <button
              type="button"
              onClick={onClose}
              aria-label={t('Wróć do panelu działki')}
              className="-ml-2 flex size-11 shrink-0 items-center justify-center rounded-full hover:bg-surface-2"
            >
              <ArrowLeft className="size-5" />
            </button>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-sm leading-5 font-medium text-brand">{t('Paszport wodny')}</p>
            <h2 className="font-display text-2xl leading-8 font-semibold">{t('Działka {numer}', { numer: p.numer })}</h2>
            <p className="text-sm leading-5 text-text-muted">
              {cropLabel(analysis.crop)} · {t('stan na')} {formatDatePl(analysis.analysis_date)} · {formatHa(p.powierzchnia_ha)} ha ·{' '}
              {t('gm. {gmina}, obręb {obreb}', { gmina: p.gmina, obreb: p.obreb })}
              {analysis.historical && <> · {t('analiza historyczna')}</>}
            </p>
          </div>
        </div>
        {!print && (
          <>
            <div className="flex flex-wrap gap-2">
              {report && (
                <button
                  type="button"
                  onClick={report.download}
                  disabled={report.busy}
                  className="flex h-11 items-center gap-2 rounded-md bg-brand-dark px-4 text-sm font-semibold text-white hover:bg-brand disabled:opacity-60"
                >
                  {report.busy ? <Loader2 className="size-4 animate-spin" /> : <FileDown className="size-4" />} {t('Pobierz PDF')}
                </button>
              )}
              <button
                type="button"
                onClick={() => window.print()}
                className="flex h-11 items-center gap-2 rounded-md border bg-surface px-4 text-sm font-medium hover:bg-surface-2"
              >
                <Printer className="size-4 text-brand" /> {t('Drukuj')}
              </button>
              {onCopyLink && (
                <button
                  type="button"
                  onClick={onCopyLink}
                  className="flex h-11 items-center gap-2 rounded-md border bg-surface px-4 text-sm font-medium hover:bg-surface-2"
                >
                  <Link2 className="size-4 text-brand" /> {t('Kopiuj link')}
                </button>
              )}
            </div>
            {!analysis.soil.non_agricultural && (
            <nav aria-label={t('Sekcje paszportu')} className="scrollbar-none -mx-1 flex gap-1.5 overflow-x-auto px-1">
              {NAV.map(([id, letter, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => jump(id)}
                  className="flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-sage-soft px-3 text-sm font-medium text-brand-dark hover:bg-ok-soft"
                >
                  <b>{letter}</b> {t(label)}
                </button>
              ))}
            </nav>
            )}
          </>
        )}
        {report?.error && !print && <ErrorNotice {...report.error} onRetry={report.error.retryable ? report.download : undefined} />}
      </header>

      {analysis.soil.non_agricultural ? (
        // SPEC 15.1: grunt nierolny – bez oceny suszy, tylko gleba i wiarygodność danych
        <>
          <NonAgriculturalCard soil={analysis.soil} />
          <SoilCard soil={analysis.soil} />
          <TerrainCard terrain={analysis.terrain} note={analysis.terrain_note} />
          <WaveDivider />
          <SectionE analysis={analysis} />
        </>
      ) : (
        <>
          <SectionA analysis={analysis} />
          <WaveDivider />
          <SectionB analysis={analysis} chartWidth={print ? 680 : undefined} />
          <WaveDivider />
          <SectionC analysis={analysis} />
          <WaveDivider />
          <SectionD analysis={analysis} onShowOnMap={print ? undefined : onShowOnMap} />
          <WaveDivider />
          <SectionE analysis={analysis} />
        </>
      )}
    </article>
  )
}
