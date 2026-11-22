import type { CropId } from '@/api/types'
import { tr } from './i18n'

export type { CropId }

/**
 * 15 upraw wg IUNG SMSR (https://susza.iung.pulawy.pl – lista wyboru sprawdzona 21.11.2026).
 * Identyfikatory = kontrakt API (api/types.ts CropId, backend schemas/analysis.py CropId).
 */
export const CROPS = [
  { id: 'zboza_ozime', label: 'Zboża ozime' },
  { id: 'zboza_jare', label: 'Zboża jare' },
  { id: 'kukurydza_ziarno', label: 'Kukurydza na ziarno' },
  { id: 'kukurydza_kiszonka', label: 'Kukurydza na kiszonkę' },
  { id: 'rzepak', label: 'Rzepak i rzepik' },
  { id: 'rzepak_jesien', label: 'Rzepak i rzepik (jesień)' },
  { id: 'ziemniak', label: 'Ziemniak' },
  { id: 'burak_cukrowy', label: 'Burak cukrowy' },
  { id: 'straczkowe', label: 'Rośliny strączkowe' },
  { id: 'warzywa', label: 'Warzywa gruntowe' },
  { id: 'drzewa_owocowe', label: 'Drzewa owocowe' },
  { id: 'krzewy_owocowe', label: 'Krzewy owocowe' },
  { id: 'truskawki', label: 'Truskawki' },
  { id: 'chmiel', label: 'Chmiel' },
  { id: 'tyton', label: 'Tytoń' },
] as const satisfies readonly { id: CropId; label: string }[]

/** Nazwa uprawy w bieżącym języku (null = brak uprawy). */
export const cropLabel = (id: CropId | null) => {
  const label = CROPS.find((c) => c.id === id)?.label
  return label ? tr(label) : null
}

/**
 * Uprawy, których w Polsce praktycznie się nie nawadnia (irrigation_practice = "not_practiced"):
 * zboża i rzepak. Dla nich bez karty nawadniania, dawek i zaleceń nawadniania – zamiast tego retencja.
 * Zapas, gdy odpowiedź nie ma `irrigation.practice` (kontrakt A5b-1) – wtedy liczy się pole z serwera.
 */
export const IRRIGATION_NOT_PRACTICED: readonly CropId[] = ['zboza_ozime', 'zboza_jare', 'rzepak', 'rzepak_jesien', 'straczkowe']

export const irrigationPracticed = (crop: CropId | null | undefined) => !crop || !IRRIGATION_NOT_PRACTICED.includes(crop)

/**
 * Czy pokazywać nawadnianie (kartę, dawki, zalecenia, alert) dla tego wyniku analizy:
 * serwer mówi „nie_praktykowane” / practice = not_practiced → nie; brak pola → lista lokalna.
 */
export function irrigationShown(a: { crop: CropId | null; irrigation: { status: string; practice?: string | null } | null }) {
  if (!a.irrigation) return false
  if (a.irrigation.status === 'nie_praktykowane' || a.irrigation.practice === 'not_practiced') return false
  if (a.irrigation.practice) return true
  return irrigationPracticed(a.crop)
}

/**
 * Historia pola (B3, `crop_history`): 22 uprawy z crops.csv backendu – 15 upraw IUNG + 7 gatunków z rankingu.
 * Ogólne „Zboża ozime/jare” zostają dla rolnika, który nie pamięta gatunku.
 */
export const HISTORY_CROPS = [
  { id: 'pszenica_ozima', label: 'Pszenica ozima' },
  { id: 'zyto', label: 'Żyto' },
  { id: 'pszenzyto_ozime', label: 'Pszenżyto ozime' },
  { id: 'jeczmien_ozimy', label: 'Jęczmień ozimy' },
  { id: 'jeczmien_jary', label: 'Jęczmień jary' },
  { id: 'owies', label: 'Owies' },
  { id: 'zboza_ozime', label: 'Zboża ozime (inne)' },
  { id: 'zboza_jare', label: 'Zboża jare (inne)' },
  { id: 'kukurydza_ziarno', label: 'Kukurydza na ziarno' },
  { id: 'kukurydza_kiszonka', label: 'Kukurydza na kiszonkę' },
  { id: 'rzepak', label: 'Rzepak i rzepik' },
  { id: 'rzepak_jesien', label: 'Rzepak i rzepik (jesień)' },
  { id: 'ziemniak', label: 'Ziemniak' },
  { id: 'burak_cukrowy', label: 'Burak cukrowy' },
  { id: 'straczkowe', label: 'Rośliny strączkowe' },
  { id: 'lubin', label: 'Łubin' },
  { id: 'warzywa', label: 'Warzywa gruntowe' },
  { id: 'drzewa_owocowe', label: 'Drzewa owocowe' },
  { id: 'krzewy_owocowe', label: 'Krzewy owocowe' },
  { id: 'truskawki', label: 'Truskawki' },
  { id: 'chmiel', label: 'Chmiel' },
  { id: 'tyton', label: 'Tytoń' },
] as const

export const HISTORY_UNKNOWN = 'nie_wiem'
export const isHistoryCrop = (v: string) => v === HISTORY_UNKNOWN || HISTORY_CROPS.some((c) => c.id === v)
export const historyLabel = (id: string) => {
  const l = HISTORY_CROPS.find((c) => c.id === id)?.label
  return l ? tr(l) : null
}
