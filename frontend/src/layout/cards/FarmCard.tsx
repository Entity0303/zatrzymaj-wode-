import { Tractor } from 'lucide-react'
import { DashboardCard as Card } from '@/components/DashboardCard'

export function FarmCard({ savedCount }: { savedCount: number }) {
  return (
    <Card icon={Tractor} title="Gospodarstwo">
      <div className="flex items-baseline gap-2">
        <span className="tabular text-[32px] leading-10 font-semibold">{savedCount}</span>
        <span className="text-sm text-text-muted">
          {savedCount === 1 ? 'zapisana działka' : savedCount >= 2 && savedCount <= 4 ? 'zapisane działki' : 'zapisanych działek'}
        </span>
      </div>
      <p className="mt-auto text-sm leading-5 text-text-muted">
        {savedCount ? 'Stan działek: brak danych – analiza w budowie' : 'Zapisz działkę gwiazdką w panelu działki'}
      </p>
    </Card>
  )
}
