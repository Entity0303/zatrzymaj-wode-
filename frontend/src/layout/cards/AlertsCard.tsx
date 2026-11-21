import { Bell, CircleCheck } from 'lucide-react'
import type { AnalysisResponse } from '@/api/types'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { useLang } from '@/lib/i18n'
import { analysisAlerts } from './alerts'

/** Alerty (SPEC 4.5): maks. 2 najważniejsze; bez zagrożeń – zielony ✓ „Brak alertów”. */
export function AlertsCard({ analysis }: { analysis: AnalysisResponse | null }) {
  const { t } = useLang()
  const alerts = analysisAlerts(analysis)
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
