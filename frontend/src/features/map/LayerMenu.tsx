import { Check, ChevronDown, Layers, PenLine } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { LAYERS, layerByKey, type LayerKey } from './layers'

/** Jedno zdanie o warstwie – w menu pod nazwą. */
const DESCRIPTION: Record<LayerKey, string> = {
  kondycja: 'Jak rosną rośliny – ze zdjęć satelitarnych',
  wilgotnosc: 'Ile wody mają rośliny – ze zdjęć satelitarnych',
  teren: 'Górki, stoki i dołki na działce',
  splyw: 'Którędy spływa woda po deszczu',
  woda: 'Rzeki, rowy i stawy wokół działki',
  gleba: 'Jak gleba na działce znosi suszę – mapa IUNG',
}

/**
 * Warstwy mapy (przeprojektowanie): JEDEN przycisk „Warstwa: Teren ▾” zamiast rzędu pigułek. Menu: lista
 * warstw (ikona + nazwa + jedno zdanie), warstwy bez danych wyszarzone z „wkrótce”, na dole przełącznik 2D / 3D.
 */
export function LayerMenu({
  value,
  onChange,
  view,
  onViewChange,
  unavailable = [],
  needsParcel = [],
  notes,
  canUse3d = true,
  side = 'top',
  onDraw,
  className,
}: {
  /** gdzie otwiera się menu: nad przyciskiem (komputer, przycisk na dole) albo pod nim (telefon) */
  side?: 'top' | 'bottom'
  value: LayerKey
  onChange: (k: LayerKey) => void
  view: '2d' | '3d'
  onViewChange: (v: '2d' | '3d') => void
  /** warstwy bez danych z serwera (dziś 501) – wyszarzone, „wkrótce” */
  unavailable?: LayerKey[]
  /** F10: warstwy tylko z wybraną działką (gleba w obrysie) – bez działki nieaktywne, „wybierz działkę” */
  needsParcel?: LayerKey[]
  /** krótka uwaga przy dostępnej warstwie, np. „pobieram…” / „brak zdjęcia” (satelita, A11) */
  notes?: Partial<Record<LayerKey, string>>
  /** 3D tylko przy wybranej działce */
  canUse3d?: boolean
  /** „Narysuj swoje pole” – opcja dodatkowa w menu mapy */
  onDraw?: () => void
  className?: string
}) {
  const { t } = useLang()
  const active = layerByKey(value)
  const ActiveIcon = active.icon
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t('Warstwa mapy: {name}. Zmień warstwę', { name: t(active.label) })}
          className={cn('glass flex h-11 items-center gap-2 rounded-full pr-3 pl-3.5 text-sm shadow-float hover:bg-sage-soft', className)}
        >
          <Layers className="size-5 text-brand" aria-hidden />
          <span className="text-text-muted">{t('Warstwa:')}</span>
          <span className="flex items-center gap-1.5 font-semibold">
            <ActiveIcon className="size-4" aria-hidden /> {t(active.short)}
          </span>
          {view === '3d' && <span className="rounded-full bg-brand px-1.5 text-xs font-semibold text-white">3D</span>}
          <ChevronDown className="size-4 text-text-muted" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side={side} align="start" sideOffset={8} className="z-[1700] w-80 rounded-xl p-1.5">
        <DropdownMenuLabel className="px-2.5 pt-1.5 pb-1 text-xs font-semibold tracking-wider text-text-muted uppercase">{t('Warstwa mapy')}</DropdownMenuLabel>
        <DropdownMenuGroup aria-label={t('Warstwa mapy')}>
          {LAYERS.map((l) => {
            const Icon = l.icon
            const soon = unavailable.includes(l.key)
            const noParcel = !soon && needsParcel.includes(l.key)
            const off = soon || noParcel
            const on = l.key === value
            return (
              <DropdownMenuItem
                key={l.key}
                role="menuitemradio"
                aria-checked={on}
                disabled={off}
                onSelect={() => onChange(l.key)}
                className={cn('min-h-14 items-start gap-3 rounded-lg px-2.5 py-2', on && 'bg-sage-soft')}
              >
                <Icon className={cn('mt-0.5 size-5 shrink-0', on ? 'text-brand' : 'text-text-muted')} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 text-sm leading-5 font-semibold">
                    {t(l.label)}
                    {off && <span className="rounded-full bg-surface-2 px-2 text-xs font-medium text-text-muted">{t(noParcel ? 'wybierz działkę' : 'wkrótce')}</span>}
                    {!off && notes?.[l.key] && <span className="rounded-full bg-surface-2 px-2 text-xs font-medium text-text-muted">{t(notes[l.key]!)}</span>}
                  </span>
                  <span className="block text-sm leading-5 text-text-muted">{t(DESCRIPTION[l.key])}</span>
                </span>
                {on && <Check className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />}
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuGroup>
        {onDraw && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onDraw} className="min-h-12 gap-3 rounded-lg px-2.5 py-2">
              <PenLine className="size-5 shrink-0 text-text-muted" aria-hidden />
              <span className="min-w-0">
                <span className="block text-sm leading-5 font-semibold">{t('Narysuj swoje pole')}</span>
                <span className="block text-sm leading-5 text-text-muted">{t('Gdy działka z ewidencji nie pasuje do pola')}</span>
              </span>
            </DropdownMenuItem>
          </>
        )}
        <DropdownMenuSeparator />
        <div className="flex items-center justify-between gap-3 px-2.5 py-2">
          <span className="text-sm">
            <span className="font-semibold">{t('Widok')}</span>
            {!canUse3d && <span className="block text-xs text-text-muted">{t('3D po wybraniu działki')}</span>}
          </span>
          <div role="radiogroup" aria-label={t('Widok mapy')} className="flex h-9 items-center rounded-full bg-surface-2 p-0.5">
            {(['2d', '3d'] as const).map((v) => (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={view === v}
                disabled={v === '3d' && !canUse3d}
                onClick={() => onViewChange(v)}
                className={cn(
                  'h-8 min-w-12 rounded-full px-3 text-sm font-semibold transition-colors disabled:opacity-40',
                  view === v ? 'bg-brand text-white' : 'text-text-muted hover:bg-surface',
                )}
              >
                {v.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
