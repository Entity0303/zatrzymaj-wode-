import { ShowerHead, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { AnalysisResponse } from '@/api/types'
import { irrigationShown } from '@/lib/crops'
import { tr } from '@/lib/i18n'

export type Alert = { icon: LucideIcon; text: string; tone: string }

/**
 * Alerty z wyniku analizy (SPEC 4.5): ryzyko na 7 dni i zalecone nawadnianie. Grunt nierolny – bez alertów
 * (nie pokazujemy wskaźników działki, która nie jest polem).
 */
export function analysisAlerts(analysis: AnalysisResponse | null): Alert[] {
  if (!analysis || analysis.soil.non_agricultural) return []
  const name = analysis.parcel.source === 'approximate' ? tr('Obszar przybliżony') : tr('Działka {numer}', { numer: analysis.parcel.numer })
  const alerts: Alert[] = []
  const risk = analysis.indicators.risk_7d
  if (risk.status && ['warn', 'risk', 'danger'].includes(risk.status) && (risk.note || risk.label))
    alerts.push({
      icon: TriangleAlert,
      text: `${name} – ${tr(risk.note ?? risk.label ?? '')}`,
      tone: risk.status === 'warn' ? 'text-amber' : 'text-danger',
    })
  if (analysis.irrigation?.status === 'zalecane' && irrigationShown(analysis))
    alerts.push({ icon: ShowerHead, text: `${name} – ${tr('nawadnianie: {what}', { what: tr(analysis.irrigation?.message ?? '') })}`, tone: 'text-water' })
  return alerts
}
