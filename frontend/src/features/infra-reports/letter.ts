import { BRAND_NAME } from '@/lib/brand'
import type { InfraReportIn, Parcel } from '@/api/types'
import { formatDatePl } from '@/lib/format'
import { todayIso } from '@/lib/dates'
import { LEVEL, OBJECT, PROBLEM } from './infra'

/**
 * Gotowe pismo (SPEC 11 krok 4) – zwykły tekst do wydruku lub skopiowania. Pola osobowe zostają
 * do uzupełnienia ręcznie (nie zbieramy danych osobowych). Nic nie wysyłamy automatycznie.
 */
export function buildLetter(r: InfraReportIn, parcel: Parcel | null, hasPhoto: boolean): string {
  const o = OBJECT[r.object_type]
  const where = parcel
    ? `w pobliżu działki ewidencyjnej nr ${parcel.numer} (obręb ${parcel.obreb}, gmina ${parcel.gmina}, identyfikator ${parcel.id})`
    : 'w miejscu wskazanym współrzędnymi'
  const lines = [
    '…………………………………, dnia ' + formatDatePl(todayIso()),
    '',
    'Imię i nazwisko: …………………………………………',
    'Adres: …………………………………………………',
    'Telefon / e-mail: ……………………………………',
    '',
    `Do: ${o.addressee}`,
    '',
    `Zgłoszenie stanu obiektu wodnego – ${o.label.toLowerCase()}`,
    '',
    `Zgłaszam stan obiektu: ${o.label.toLowerCase()}, ${where}.`,
    `Położenie (WGS84): szer. ${r.lat.toFixed(6)}, dł. ${r.lon.toFixed(6)}.`,
    `Stwierdzony stan: ${PROBLEM[r.problem].label.toLowerCase()}.`,
    ...(r.water_level ? [`Poziom wody: ${LEVEL[r.water_level].toLowerCase()}.`] : []),
    ...(r.description ? ['', `Opis: ${r.description}`] : []),
    '',
    r.problem === 'drozny'
      ? 'Informuję o stanie obiektu w celu aktualizacji wiedzy o jego drożności.'
      : 'Proszę o sprawdzenie stanu obiektu i podjęcie działań, które przywrócą jego prawidłowe działanie – zatrzymanie i odpływ wody wpływają na uprawy w okolicy.',
    ...(hasPhoto ? ['', 'Załącznik: zdjęcie obiektu.'] : []),
    '',
    'Z poważaniem',
    '',
    '…………………………………………',
    '(podpis)',
    '',
    '—',
    `Pismo przygotowane w aplikacji ${BRAND_NAME}. Aplikacja niczego nie wysyła automatycznie.`,
  ]
  return lines.join('\n')
}
