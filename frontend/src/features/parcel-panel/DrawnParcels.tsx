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
export function DrawnParcels({
  parcel,
  className,
  max = MAX_SHOWN,
  compact,
}: {
  parcel: Parcel
  className?: string
  /** ile pozycji pokazać od razu; reszta pod „i N więcej” (rozwijane kliknięciem) */
  max?: number
  /** wąski panel: krótsze pozycje (sam numer, obręb raz w nagłówku, gdy wspólny) */
  compact?: boolean
}) {
  const { t } = useLang()
  const [open, setOpen] = useState(false)
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
  const shown = open ? data.parcels : data.parcels.slice(0, max)
  const rest = data.parcels.length - shown.length
  // wąski panel (`compact`): sam numer i udział – „6/1 (25%), 6/2 (25%), 147 (17%) i 3 więcej”; obręb w podpowiedzi,
  // a gdy wszystkie działki są z jednego obrębu – raz w nagłówku
  const oneRegion = compact && data.parcels.every((p) => p.obreb === data.parcels[0].obreb)
  return (
    <p className={className}>
      {oneRegion ? t('Obejmuje działki ({obreb}):', { obreb: data.parcels[0].obreb }) : t('Obejmuje działki:')}{' '}
      {shown.map((p, i) => (
        <span key={p.id}>
          {i > 0 && ', '}
          <span className="whitespace-nowrap">
            <a href={startLink({ dzialka: p.id })} title={`${p.numer} ${p.obreb}`} className="font-medium text-brand-dark underline-offset-2 hover:underline">
              {compact ? p.numer : `${p.numer} ${p.obreb}`}
            </a>{' '}
            ({compact ? `${p.share}%` : t('ok. {n}%', { n: p.share })})
          </span>
        </span>
      ))}
      {(rest > 0 || open) && data.parcels.length > max && (
        <>
          {' '}
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="font-medium whitespace-nowrap text-brand-dark underline underline-offset-2">
            {open ? t('pokaż mniej') : t('i {n} więcej', { n: rest })}
          </button>
        </>
      )}
    </p>
  )
}
