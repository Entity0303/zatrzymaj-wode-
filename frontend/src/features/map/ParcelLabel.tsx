import type { Parcel, VerdictLevel } from '@/api/types'
import { parcelShortName } from '@/features/parcel-panel/parcelTitle'
import { Leaf } from 'lucide-react'
import { LONG_TERM_LABEL, NOW_LABEL, STATUS, type Status } from '@/theme/status'
import { useLang } from '@/lib/i18n'

/**
 * Etykieta-pigułka w środku działki (SPEC 5.1, 14 ParcelLabel): nazwa działki, pod nią stan w dwóch równych wierszach
 * z ikonami jak w panelu (RiskSummary) – „Teraz: woda w normie” / „Na dłuższą metę: wysokie ryzyko suszy”
 * (dziś ≠ ryzyko na lata, bez pozornej sprzeczności). F9: bez kropki-separatora, maks. 260 px szerokości.
 */

/** Kolor kropki ryzyka na lata – ten sam co pasek w RiskSummary. */
const LONG_TERM_DOT: Record<VerdictLevel, string> = { ok: 'bg-ok', warn: 'bg-amber', bad: 'bg-danger' }
export function ParcelLabel({
  number,
  status,
  source,
  longTerm,
}: {
  number: string
  status: Status
  source?: Parcel['source']
  /** werdykt działki (ryzyko suszy na lata) */
  longTerm?: VerdictLevel | null
}) {
  const { t } = useLang()
  const s = STATUS[status]
  const Icon = s.icon
  return (
    <span className="flex max-w-[260px] items-center gap-1.5 rounded-2xl bg-surface py-1 pr-3 pl-1.5 text-text shadow-float">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-ok-soft text-brand">
        <Leaf className="size-4" aria-hidden />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="text-sm leading-5 font-semibold whitespace-nowrap">{parcelShortName({ source, numer: number })}</span>
        {(status !== 'no_data' || longTerm) && (
          <span className="flex flex-col gap-0.5 text-xs leading-4 font-medium whitespace-normal">
            {status !== 'no_data' && (
              <span className="flex items-start gap-1">
                <span className="flex size-3.5 shrink-0 items-center justify-center">
                  <Icon className={`size-3.5 ${s.fg}`} aria-hidden />
                </span>
                <span>
                  <span className="text-text-muted">{t('Teraz:')}</span> {t(NOW_LABEL[status])}
                </span>
              </span>
            )}
            {longTerm && (
              <span className="flex items-start gap-1">
                <span className="flex size-3.5 shrink-0 items-center justify-center">
                  <span className={`size-2.5 rounded-full ${LONG_TERM_DOT[longTerm]}`} aria-hidden />
                </span>
                <span>
                  <span className="text-text-muted">{t('Na dłuższą metę:')}</span> {t(LONG_TERM_LABEL[longTerm])}
                </span>
              </span>
            )}
          </span>
        )}
      </span>
    </span>
  )
}
