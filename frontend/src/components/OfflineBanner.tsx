import { WifiOff } from 'lucide-react'

/** Baner „Brak połączenia” (SPEC 15.1). */
export function OfflineBanner() {
  return (
    <div
      role="status"
      className="pointer-events-auto flex items-center gap-2 rounded-full bg-text px-4 py-2 text-sm font-medium text-white shadow-float"
    >
      <WifiOff className="size-4" aria-hidden />
      Brak połączenia – pokazujemy ostatnio zapisane dane
    </div>
  )
}
