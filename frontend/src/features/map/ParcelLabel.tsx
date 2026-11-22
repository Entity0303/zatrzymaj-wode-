import type { Parcel, VerdictLevel } from '@/api/types'
import { parcelShortName } from '@/features/parcel-panel/parcelTitle'
import { Leaf } from 'lucide-react'
import { StatusRows } from '@/components/StatusRows'
import type { Status } from '@/theme/status'

/**
 * Etykieta-pigułka w środku działki (SPEC 5.1, 14 ParcelLabel): nazwa działki, pod nią stan w dwóch równych wierszach
 * (wspólny `StatusRows`, jak w panelu) – „Teraz: woda w normie” / „Na dłuższą metę: wysokie ryzyko suszy”
 * (dziś ≠ ryzyko na lata, bez pozornej sprzeczności). Bez kropki-separatora, maks. 260 px szerokości.
 */
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
  return (
    <span className="flex max-w-[260px] items-center gap-1.5 rounded-2xl bg-surface py-1 pr-3 pl-1.5 text-text shadow-float">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-ok-soft text-brand">
        <Leaf className="size-4" aria-hidden />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-sm leading-5 font-bold">{parcelShortName({ source, numer: number })}</span>
        <StatusRows now={status} longTerm={longTerm} size="xs" className="whitespace-normal" />
      </span>
    </span>
  )
}
