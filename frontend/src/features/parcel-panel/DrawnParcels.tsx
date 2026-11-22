import { useEffect, useState } from 'react'
import { api, type ParcelsInArea } from '@/api/client'
import type { Parcel } from '@/api/types'
import { startLink } from '@/lib/deepLink'
import { useLang } from '@/lib/i18n'

/** wynik na pole narysowane (id pola) – bez ponownych zapytań przy przełączaniu widoków */
const cache = new Map<string, ParcelsInArea>()
const MAX_SHOWN = 5

/**
 * F30: „Obejmuje działki: 6/1 Wnory-Wandy (ok. 60%), …” pod nagłówkiem pola narysowanego – działki ewidencyjne
 * pod obrysem (POST /api/parcels-in-area, próbkowanie punktami). Zapytanie w tle – nie blokuje analizy ani warstw.
 * Pozycja to link do tej działki (otwiera ją jak wynik wyszukiwarki). Błąd / nota z serwera – szary tekst.
 */
export function DrawnParcels({ parcel, className }: { parcel: Parcel; className?: string }) {
  const { t } = useLang()
  const [res, setRes] = useState<{ id: string; data: ParcelsInArea } | null>(() => {
    const c = cache.get(parcel.id)
    return c ? { id: parcel.id, data: c } : null
  })
  const geometry = parcel.geometria

  useEffect(() => {
    if (parcel.source !== 'drawn' || geometry.type !== 'Polygon') return
    const hit = cache.get(parcel.id)
    if (hit) return setRes({ id: parcel.id, data: hit })
    const ctrl = new AbortController()
    api.parcelsInArea(geometry as GeoJSON.Polygon, ctrl.signal).then(
      (data) => {
        if (ctrl.signal.aborted) return
        if (!data.note) cache.set(parcel.id, data)
        setRes({ id: parcel.id, data })
      },
      () => !ctrl.signal.aborted && setRes({ id: parcel.id, data: { parcels: [], note: 'Nie udało się sprawdzić działek ewidencyjnych – spróbuj za chwilę.' } }),
    )
    return () => ctrl.abort()
    // obrys należy do pola (parcel.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parcel.id])

  if (parcel.source !== 'drawn') return null
  const data = res?.id === parcel.id ? res.data : null
  if (!data) return <p className={className}>{t('sprawdzam działki ewidencyjne…')}</p>
  if (data.note) return <p className={className}>{t(data.note)}</p>
  if (!data.parcels.length) return null
  const shown = data.parcels.slice(0, MAX_SHOWN)
  const rest = data.parcels.length - shown.length
  return (
    <p className={className}>
      {t('Obejmuje działki:')}{' '}
      {shown.map((p, i) => (
        <span key={p.id}>
          {i > 0 && ', '}
          <a href={startLink({ dzialka: p.id })} className="font-medium whitespace-nowrap text-brand-dark underline-offset-2 hover:underline">
            {p.numer} {p.obreb}
          </a>{' '}
          <span className="whitespace-nowrap">({t('ok. {n}%', { n: p.share })})</span>
        </span>
      ))}
      {rest > 0 && ` ${t('i {n} innych', { n: rest })}`}
    </p>
  )
}
