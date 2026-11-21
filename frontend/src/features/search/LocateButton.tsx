import { Loader2, LocateFixed } from 'lucide-react'
import { cn } from '@/lib/utils'

/** „Moja lokalizacja” – działka, na której stoi rolnik. */
export function LocateButton({ locating, onClick, iconOnly }: { locating: boolean; onClick: () => void; iconOnly?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={locating}
      aria-label="Moja lokalizacja – znajdź działkę, na której stoisz"
      className={cn(
        'flex h-12 shrink-0 items-center justify-center gap-2 rounded-full border bg-surface font-medium text-text shadow-float hover:bg-ok-soft disabled:opacity-70',
        iconOnly ? 'w-12' : 'px-4 text-base',
      )}
    >
      {locating ? <Loader2 className="size-5 animate-spin text-brand" /> : <LocateFixed className="size-5 text-brand" />}
      {!iconOnly && <span className="whitespace-nowrap">Moja lokalizacja</span>}
    </button>
  )
}
