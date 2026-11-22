import { plForm } from '@/lib/format'
import { ChevronDown, ChevronUp, MousePointerClick, Tractor } from 'lucide-react'
import type { CSSProperties } from 'react'
import { ForecastCard } from '@/features/weather/ForecastCard'
import { useLang } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { analysisAlerts } from './cards/alerts'
import { AlertsCard } from './cards/AlertsCard'
import { BalanceCard } from './cards/BalanceCard'
import { FarmCard } from './cards/FarmCard'
import type { BottomCardsProps } from './cards/types'

/** „2 działki” / „5 działek” */
function parcelsLabel(n: number, t: ReturnType<typeof useLang>['t']) {
  return t(n === 1 ? '{n} działka' : n >= 2 && n <= 4 ? '{n} działki' : '{n} działek', { n })
}

/**
 * „Moje gospodarstwo” (przeprojektowanie): zamiast stałego paska 4–5 kart – szuflada zwinięta do cienkiego
 * paska z tym, co ważne („3 działki · 1 alert”). Rozwinięta: Gospodarstwo, Bilans wody, Alerty, Prognoza
 * w siatce, która się nie ucina. Bilans tylko dla prawdziwego pola (podpisany, czyje to liczby);
 * prognoza tylko, gdy jest. Pierwsze uruchomienie (nic zapisane, nic wybrane) – jedna karta „Kliknij pole…”.
 * `inline` – telefon: w szufladzie działki, w zwykłym układzie.
 */
export function FarmDrawer({
  open,
  onToggle,
  inline,
  panelStyle,
  ...props
}: BottomCardsProps & {
  open: boolean
  onToggle: () => void
  inline?: boolean
  /** komputer: szerokość / położenie rozwiniętego panelu (nad paskiem) */
  panelStyle?: CSSProperties
}) {
  const { t } = useLang()
  const a = props.analysis
  const farmland = !!a && !a.soil.non_agricultural
  const alerts = analysisAlerts(a).length
  const n = props.saved.length
  const firstRun = n === 0 && !a
  const forecastOk = !!props.forecast && !props.forecastError

  const summary = firstRun
    ? t('kliknij pole, aby zacząć')
    : n === 0 && !alerts
      ? t('Zapisz działkę gwiazdką ☆, a tu zobaczysz wszystkie swoje pola i alerty.') // F36: pusty stan – co zrobić, żeby pasek się wypełnił
      : [n ? parcelsLabel(n, t) : null, alerts ? t(plForm(alerts, '{n} alert', '{n} alerty', '{n} alertów'), { n: alerts }) : null].filter(Boolean).join(' · ') ||
        t('bez alertów')

  const bar = (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className={cn(
        'flex h-11 items-center gap-2 rounded-full pr-3 pl-3.5 text-sm hover:bg-sage-soft',
        inline ? 'w-full border bg-surface' : 'glass shadow-float',
      )}
    >
      <Tractor className="size-5 text-brand" aria-hidden />
      <span className="font-semibold whitespace-nowrap">{t('Moje gospodarstwo')}</span>
      <span className="truncate text-text-muted" title={summary}>
        · {summary}
      </span>
      {alerts > 0 && <span className="size-2 shrink-0 rounded-full bg-danger" aria-hidden />}
      {open ? <ChevronDown className="ml-auto size-4 shrink-0 text-text-muted" aria-hidden /> : <ChevronUp className="ml-auto size-4 shrink-0 text-text-muted" aria-hidden />}
    </button>
  )

  const content = firstRun ? (
    <div className="flex items-center gap-3 rounded-xl border bg-surface p-4">
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-sage-soft text-brand">
        <MousePointerClick className="size-5" aria-hidden />
      </span>
      <p className="text-base leading-6">
        <b>{t('Kliknij pole na mapie, aby zobaczyć jego stan.')}</b>{' '}
        <span className="text-text-muted">{t('Zapisane działki i alerty pojawią się tutaj.')}</span>
      </p>
    </div>
  ) : (
    <div className={cn('grid gap-3', inline ? 'grid-cols-1' : 'grid-cols-[repeat(auto-fill,minmax(240px,1fr))]')}>
      <div className="min-h-[148px]">
        <FarmCard saved={props.saved} />
      </div>
      {farmland && (
        <div className="min-h-[148px]">
          <BalanceCard analysis={a} />
        </div>
      )}
      <div className="min-h-[148px]">
        <AlertsCard analysis={a} />
      </div>
      {forecastOk && (
        <div className={cn('min-h-[200px]', !inline && 'sm:col-span-2')}>
          <ForecastCard forecast={props.forecast} loading={props.forecastLoading} error={false} where={props.where} historical={props.historical} />
        </div>
      )}
    </div>
  )

  if (inline)
    return (
      <section className="space-y-3 border-t pt-5">
        {bar}
        {open && content}
      </section>
    )
  return (
    <>
      {bar}
      {open && (
        <div
          role="region"
          aria-label={t('Moje gospodarstwo')}
          className="glass absolute bottom-full left-0 mb-2 max-h-[60vh] overflow-y-auto rounded-xl p-3 shadow-float"
          style={panelStyle}
        >
          {content}
        </div>
      )}
    </>
  )
}
