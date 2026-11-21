import type { Parcel } from '@/api/types'
import { formatHa } from '@/lib/format'
import { useLang } from '@/lib/i18n'

/** Tytuł działki: „Działka 112/11” albo „Obszar przybliżony” (bez granic z ULDK, A5c). */
export function useParcelTitle(parcel: Parcel) {
  const { t } = useLang()
  const approx = parcel.source === 'approximate'
  return {
    approx,
    title: approx ? t('Obszar przybliżony') : t('Działka {numer}', { numer: parcel.numer }),
    sub: approx
      ? `${t('wokół wskazanego punktu')} · ${formatHa(parcel.powierzchnia_ha)} ha`
      : `${t('gm. {gmina}, obręb {obreb}', { gmina: parcel.gmina, obreb: parcel.obreb })} · ${formatHa(parcel.powierzchnia_ha)} ha`,
  }
}
