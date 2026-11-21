import { ChartNoAxesCombined } from 'lucide-react'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { NoDataNote as NoData } from '@/components/NoDataNote'

export function BalanceCard() {
  return (
    <Card icon={ChartNoAxesCombined} title="Bilans wody">
      <NoData />
    </Card>
  )
}
