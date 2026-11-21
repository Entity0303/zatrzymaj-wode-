import { Leaf } from 'lucide-react'
import { STATUS, type Status } from '@/theme/status'

/** Etykieta-pigułka w środku działki: numer + ikona stanu (SPEC 5.1, 14 ParcelLabel). */
export function ParcelLabel({ number, status }: { number: string; status: Status }) {
  const s = STATUS[status]
  const Icon = s.icon
  return (
    <span className="flex items-center gap-1.5 rounded-full bg-surface py-1 pr-2.5 pl-1.5 text-sm font-semibold whitespace-nowrap text-text shadow-float">
      <span className="flex size-6 items-center justify-center rounded-full bg-ok-soft text-brand">
        <Leaf className="size-4" aria-hidden />
      </span>
      Działka {number}
      <span className={`flex items-center gap-1 text-xs font-medium ${s.fg}`}>
        <Icon className="size-4" aria-hidden />
        {s.label}
      </span>
    </span>
  )
}
