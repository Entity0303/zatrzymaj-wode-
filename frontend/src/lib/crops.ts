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
 * TODO: gdy kontrakt dostanie pole `irrigation_practice`, czytać je z odpowiedzi analizy zamiast tej listy.
 */
export const IRRIGATION_NOT_PRACTICED: readonly CropId[] = ['zboza_ozime', 'zboza_jare', 'rzepak', 'rzepak_jesien']

export const irrigationPracticed = (crop: CropId | null | undefined) => !crop || !IRRIGATION_NOT_PRACTICED.includes(crop)
