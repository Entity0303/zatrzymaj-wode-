import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

/** Przełącznik 2D | 3D – 3D nieaktywne do czasu implementacji (SPEC 4.2, 8). */
export function ViewToggle() {
  return (
    <div role="radiogroup" aria-label="Widok mapy" className="flex h-10 shrink-0 items-center rounded-full border bg-surface p-1 shadow-float">
      <button type="button" role="radio" aria-checked className="h-8 rounded-full bg-brand px-3.5 text-sm font-semibold text-white">
        2D
      </button>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            role="radio"
            aria-checked={false}
            aria-disabled
            onClick={(e) => e.preventDefault()}
            className="h-8 cursor-not-allowed rounded-full px-3.5 text-sm font-semibold text-text-muted/70"
          >
            3D
          </button>
        </TooltipTrigger>
        <TooltipContent>Wkrótce</TooltipContent>
      </Tooltip>
    </div>
  )
}
