import { Bell } from 'lucide-react'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { NoDataNote as NoData } from '@/components/NoDataNote'

export function AlertsCard() {
  return (
    <Card icon={Bell} title="Alerty">
      <NoData text="Alerty pojawią się po analizie (w budowie)" />
    </Card>
  )
}
