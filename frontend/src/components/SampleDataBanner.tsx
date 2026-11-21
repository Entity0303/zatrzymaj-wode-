import { FlaskConical } from 'lucide-react'

/** Widoczny znak, że na ekranie są dane z mocka, a nie z analizy (tylko tryb deweloperski). */
export function SampleDataBanner() {
  return (
    <div
      role="status"
      className="pointer-events-none flex items-center gap-2 rounded-full border-2 border-danger bg-warn px-4 py-1.5 text-sm font-bold tracking-wide text-text uppercase shadow-float"
    >
      <FlaskConical className="size-4" aria-hidden />
      DANE PRZYKŁADOWE – nie z analizy tej działki
    </div>
  )
}
