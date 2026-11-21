import { CalendarRange } from 'lucide-react'
import { DashboardCard as Card } from '@/components/DashboardCard'

export function TimelineCard({ updated }: { updated: string | null }) {
  const months = ['S', 'L', 'M', 'K', 'M', 'C', 'L', 'S', 'W', 'P', 'L', 'G']
  return (
    <Card icon={CalendarRange} title="Oś czasu">
      <div className="flex gap-0.5" aria-label="Stan w kolejnych miesiącach: brak danych">
        {months.map((m, i) => (
          <div key={i} className="flex flex-1 flex-col items-center gap-0.5">
            <span className="hatch-nodata h-5 w-full rounded-sm" />
            <span className="text-[12px] leading-4 text-text-muted">{m}</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-sm leading-5 text-text-muted">Brak danych – analiza w budowie</p>
      <p className="mt-auto text-xs leading-4 text-text-muted">
        Ostatnia aktualizacja danych: {updated ?? '—'}
      </p>
    </Card>
  )
}
