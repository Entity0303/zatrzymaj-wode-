import { Droplets, FileText, House, Map as MapIcon, Settings, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

type Item = { label: string; icon: LucideIcon; active?: boolean; disabled?: boolean }

const ITEMS: Item[] = [
  { label: 'Start', icon: House, active: true },
  { label: 'Moje działki', icon: MapIcon, disabled: true },
  { label: 'Raporty', icon: FileText, disabled: true },
  { label: 'Ustawienia', icon: Settings, disabled: true },
]

/** Wąski pasek nawigacji po lewej (tylko desktop). */
export function SideNav() {
  return (
    <nav
      aria-label="Nawigacja główna"
      className="absolute inset-y-0 left-0 z-[1100] hidden w-[88px] flex-col items-center gap-1 border-r bg-card/95 py-4 shadow-sm md:flex"
    >
      <div className="mb-4 flex flex-col items-center gap-1" title="Zatrzymaj wodę">
        <div className="flex size-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md">
          <Droplets className="size-6" />
        </div>
        <span className="text-center text-[10px] font-semibold leading-tight text-primary">
          Zatrzymaj
          <br />
          wodę
        </span>
      </div>
      {ITEMS.map(({ label, icon: Icon, active, disabled }) => (
        <button
          key={label}
          type="button"
          disabled={disabled}
          aria-current={active ? 'page' : undefined}
          title={disabled ? `${label} – wkrótce` : label}
          className={cn(
            'flex w-[76px] flex-col items-center gap-1 rounded-xl px-1 py-2.5 text-[11px] font-medium transition-colors',
            active
              ? 'bg-secondary text-secondary-foreground'
              : 'text-muted-foreground hover:bg-muted',
            disabled && 'cursor-not-allowed opacity-55 hover:bg-transparent',
          )}
        >
          <Icon className="size-5" />
          <span className="text-center leading-tight">{label}</span>
        </button>
      ))}
    </nav>
  )
}
