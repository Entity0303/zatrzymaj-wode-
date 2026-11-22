import type { Parcel } from '@/api/types'
import { formatArea } from '@/lib/format'
import { tr, useLang } from '@/lib/i18n'

/** Tytuł działki: „Działka 112/11”, „Obszar przybliżony” (bez granic z ULDK) albo „Pole narysowane przez rolnika” (A5c). */
export function useParcelTitle(parcel: Parcel) {
  const { t } = useLang()
  const approx = parcel.source === 'approximate'
  const drawn = parcel.source === 'drawn'
  return {
    approx,
    drawn,
    title: drawn ? t('Pole narysowane przez rolnika') : approx ? t('Obszar przybliżony') : t('Działka {numer}', { numer: parcel.numer }),
    sub: drawn
      ? `${t('obrys narysowany na mapie')} · ${formatArea(parcel.powierzchnia_ha)}`
      : approx
      ? `${t('wokół wskazanego punktu')} · ${formatArea(parcel.powierzchnia_ha)}`
      : `${t('gm. {gmina}, obręb {obreb}', { gmina: parcel.gmina, obreb: parcel.obreb })} · ${formatArea(parcel.powierzchnia_ha)}`,
  }
}

/** Krótka nazwa do etykiet (mapa, karty, alerty): „Działka 6/1”, „Obszar przybliżony”, „Pole narysowane”. */
export function parcelShortName(p: Pick<Parcel, 'source' | 'numer'>): string {
  if (p.source === 'drawn') return tr('Pole narysowane')
  if (p.source === 'approximate') return tr('Obszar przybliżony')
  return tr('Działka {numer}', { numer: p.numer })
}
