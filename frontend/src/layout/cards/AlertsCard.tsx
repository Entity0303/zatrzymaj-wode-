import { Bell, CircleCheck, ShowerHead, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { AnalysisResponse } from '@/api/types'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { NoDataNote as NoData } from '@/components/NoDataNote'
import { useLang } from '@/lib/i18n'

type Alert = { icon: LucideIcon; text: string; tone: string }

/**
 * Alerty (SPEC 4.5): maks. 2 najważniejsze – z wyniku analizy (ryzyko na 7 dni, zalecone nawadnianie).
 * Bez analizy – „Brak danych”; analiza bez zagrożeń – zielony ✓ „Brak alertów”.
 */
export function AlertsCard({ analysis }: { analysis: AnalysisResponse | null }) {
  const { t } = useLang()
  if (!analysis)
    return (
      <Card icon={Bell} title="Alerty">
        <NoData text="Alerty pojawią się po analizie działki" />
      </Card>
    )
  const numer = analysis.parcel.numer
  const alerts: Alert[] = []
  const risk = analysis.indicators.risk_7d
  if (risk.status && ['warn', 'risk', 'danger'].includes(risk.status) && (risk.note || risk.label))
    alerts.push({
      icon: TriangleAlert,
      text: t('Działka {numer} – {what}', { numer, what: t(risk.note ?? risk.label ?? '') }),
      tone: risk.status === 'warn' ? 'text-amber' : 'text-danger',
    })
  if (analysis.irrigation?.status === 'zalecane')
    alerts.push({ icon: ShowerHead, text: t('Działka {numer} – nawadnianie: {what}', { numer, what: t(analysis.irrigation.message) }), tone: 'text-water' })

  return (
    <Card icon={Bell} title="Alerty">
      {alerts.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1 text-center">
          <CircleCheck className="size-7 text-ok" aria-hidden />
          <p className="text-sm text-text-muted">{t('Brak alertów')}</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {alerts.slice(0, 2).map((a) => (
            <li key={a.text} className="flex gap-2 text-sm leading-5">
              <a.icon className={`mt-0.5 size-4 shrink-0 ${a.tone}`} aria-hidden />
              <span className="line-clamp-2">{a.text}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
