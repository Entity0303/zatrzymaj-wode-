import { Tractor } from 'lucide-react'
import { DashboardCard as Card } from '@/components/DashboardCard'
import { StatusBadge } from '@/components/StatusBadge'
import type { SavedParcel } from '@/lib/hooks'
import { useLang } from '@/lib/i18n'
import { useHistory } from '@/lib/storage'
import type { StatusLevel } from '@/api/types'
import { goTo } from '@/lib/router'

const ORDER: StatusLevel[] = ['danger', 'risk', 'warn', 'ok', 'no_data']

/** Gospodarstwo (SPEC 4.5): liczba zapisanych działek i ostatni znany stan każdej (z historii analiz). */
export function FarmCard({ saved }: { saved: SavedParcel[] }) {
  const { t } = useLang()
  const [history] = useHistory()
  const counts = new Map<StatusLevel, number>()
  let unknown = 0
  for (const p of saved) {
    const last = history.find((h) => h.parcel_id === p.id)
    if (last) counts.set(last.level, (counts.get(last.level) ?? 0) + 1)
    else unknown++
  }
  const attention = (counts.get('warn') ?? 0) + (counts.get('risk') ?? 0) + (counts.get('danger') ?? 0)
  const n = saved.length
  return (
    <Card icon={Tractor} title="Gospodarstwo">
      <button type="button" onClick={() => goTo('parcels')} className="flex items-baseline gap-2 text-left hover:underline">
        <span className="tabular text-[32px] leading-10 font-semibold">{n}</span>
        <span className="text-sm text-text-muted">
          {t(n === 1 ? 'zapisana działka' : n >= 2 && n <= 4 ? 'zapisane działki' : 'zapisanych działek')}
        </span>
      </button>
      {n === 0 ? (
        <p className="mt-auto text-sm leading-5 text-text-muted">{t('Zapisz działkę gwiazdką ☆, a tu zobaczysz wszystkie swoje pola i alerty.')}</p>
      ) : (
        <div className="mt-auto space-y-1.5">
          <div className="flex flex-wrap gap-1">
            {ORDER.filter((l) => counts.get(l)).map((l) => (
              <StatusBadge key={l} status={l} size="sm" label={`${t(l === 'no_data' ? 'Brak danych' : { ok: 'Dobrze', warn: 'Uwaga', risk: 'Ryzyko', danger: 'Bardzo mało wody' }[l])} ${counts.get(l)}`} />
            ))}
          </div>
          <p className="text-sm leading-5 text-text-muted">
            {attention > 0
              ? t('Wymaga uwagi: {n}', { n: attention })
              : unknown === n
                ? t('Jeszcze bez analizy')
                : t('Żadna działka nie wymaga uwagi')}
          </p>
        </div>
      )}
    </Card>
  )
}
