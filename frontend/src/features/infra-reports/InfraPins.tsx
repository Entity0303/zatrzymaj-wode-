import { useEffect, useState } from 'react'
import { CircleMarker, Popup, Tooltip } from '@/features/map/leaflet'
import { ApiError, api } from '@/api/client'
import type { InfraReport } from '@/api/types'
import { formatDatePl } from '@/lib/format'
import { useLang } from '@/lib/i18n'
import { OBJECT, PROBLEM, TONE_HEX } from './infra'
import { useMyReports } from './myReports'

/**
 * Zgłoszenia rolników na mapie (SPEC 11): pinezki w kolorze stanu, liczba potwierdzeń, data;
 * „Potwierdzam” (POST /confirm). Lista z GET /api/infra-reports w obszarze wokół działki;
 * brak usługi (501) = brak pinezek, bez komunikatu błędu.
 */
export function InfraPins({ bbox, refresh }: { bbox: [number, number, number, number] | null; refresh: number }) {
  const { t } = useLang()
  const [reports, setReports] = useState<InfraReport[]>([])
  const [note, setNote] = useState<Record<string, string>>({})
  const key = bbox?.map((v) => v.toFixed(4)).join(',')
  // F22: zgłoszenia wysłane z tej przeglądarki – wyróżnione na mapie (ciemna obwódka, większa pinezka)
  const mineIds = new Set(useMyReports().map((r) => r.id))

  useEffect(() => {
    if (!bbox) return
    const ctrl = new AbortController()
    api.infraReports(bbox, ctrl.signal).then(
      (r) => !ctrl.signal.aborted && setReports(r),
      () => !ctrl.signal.aborted && setReports([]),
    )
    return () => ctrl.abort()
    // bbox porównywany przez `key`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, refresh])

  async function confirm(r: InfraReport) {
    try {
      const updated = await api.confirmInfraReport(r.id)
      setReports((list) => list.map((x) => (x.id === r.id ? updated : x)))
      setNote((n) => ({ ...n, [r.id]: t('Dziękujemy – potwierdzono') }))
    } catch (e) {
      const msg = e instanceof ApiError && (e.status === 404 || e.status === 501) ? t('Potwierdzanie jest chwilowo niedostępne') : t('Nie udało się potwierdzić')
      setNote((n) => ({ ...n, [r.id]: msg }))
    }
  }

  if (!bbox) return null
  return (
    <>
      {reports.map((r) => {
        const color = TONE_HEX[PROBLEM[r.problem].tone]
        const mine = mineIds.has(r.id)
        const label = (mine ? t('Twoje zgłoszenie') + ' · ' : '') + `${t(OBJECT[r.object_type].label)} · ${t(PROBLEM[r.problem].label)}`
        return (
          <CircleMarker
            key={r.id}
            center={[r.lat, r.lon]}
            radius={mine ? 12 : 9}
            pathOptions={{ color: mine ? '#1F4E79' : '#FFFFFF', weight: mine ? 4 : 2.5, fillColor: color, fillOpacity: 1 }}
          >
            <Tooltip direction="top" offset={[0, -8]}>
              {label}
            </Tooltip>
            <Popup>
              <div className="space-y-1.5 text-sm">
                <p className="font-semibold">{label}</p>
                <p className="text-text-muted">
                  {t('Potwierdzeń: {n}', { n: r.confirmations })} · {formatDatePl(r.created_at.slice(0, 10))}
                </p>
                <p className="text-text-muted">{t('Adresat: {a}', { a: t(r.addressee) })}</p>
                <button
                  type="button"
                  onClick={() => confirm(r)}
                  className="mt-1 h-10 rounded-md bg-brand px-3 text-sm font-semibold text-white hover:bg-brand-dark"
                >
                  {t('Potwierdzam')}
                </button>
                {note[r.id] && <p className="text-xs">{note[r.id]}</p>}
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </>
  )
}
