import { CalendarRange } from 'lucide-react'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { locale, useLang } from '@/lib/i18n'

export function TimelineCard({ updated }: { updated: string | null }) {
  const { t } = useLang()
  // inicjały miesięcy w bieżącym języku (S L M K … / J F M A …)
  const months = Array.from({ length: 12 }, (_, m) =>
    new Date(2020, m, 15).toLocaleDateString(locale(), { month: 'narrow' }).toUpperCase(),
  )
  return (
    <Card icon={CalendarRange} title="Oś czasu">
      <div className="flex gap-0.5" aria-label={t('Stan w kolejnych miesiącach: brak danych')}>
        {months.map((m, i) => (
          <div key={i} className="flex flex-1 flex-col items-center gap-0.5">
            <span className="hatch-nodata h-5 w-full rounded-sm" />
            <span className="text-[12px] leading-4 text-text-muted">{m}</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-sm leading-5 text-text-muted">{t('Brak danych – analiza w budowie')}</p>
      <p className="mt-auto text-xs leading-4 text-text-muted">
        {t('Ostatnia aktualizacja danych:')} {updated ?? '—'}
      </p>
    </Card>
  )
}
