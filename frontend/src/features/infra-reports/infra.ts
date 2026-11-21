import type { InfraProblem, WaterLevel, WaterObjectType } from '@/api/types'

/** Słowniki zgłoszeń (SPEC 11) – teksty polskie = klucze tłumaczeń. */
export const OBJECT: Record<WaterObjectType, { label: string; addressee: string; hint: string }> = {
  row: {
    label: 'Rów melioracyjny',
    addressee: 'Właściciel gruntu lub spółka wodna',
    hint: 'Rowy na polach utrzymuje właściciel gruntu albo spółka wodna, jeśli działa w gminie.',
  },
  ciek: {
    label: 'Rzeka lub strumień',
    addressee: 'Wody Polskie – Nadzór Wodny',
    hint: 'Rzekami i strumieniami zarządza Państwowe Gospodarstwo Wodne Wody Polskie.',
  },
  zbiornik: {
    label: 'Staw lub zbiornik',
    addressee: 'Właściciel lub zarządca zbiornika',
    hint: 'Pismo skieruj do właściciela albo zarządcy zbiornika.',
  },
}

export const PROBLEM: Record<InfraProblem, { label: string; tone: 'ok' | 'warn' | 'danger' }> = {
  drozny: { label: 'Drożny, w porządku', tone: 'ok' },
  zarosniety: { label: 'Zarośnięty', tone: 'warn' },
  zamulony: { label: 'Zamulony', tone: 'warn' },
  zatkany_przepust: { label: 'Zatkany przepust', tone: 'danger' },
  uszkodzona_zastawka: { label: 'Uszkodzona zastawka', tone: 'danger' },
  uszkodzona_skarpa: { label: 'Uszkodzona skarpa', tone: 'danger' },
  zanieczyszczony: { label: 'Zanieczyszczony', tone: 'danger' },
}

export const LEVEL: Record<WaterLevel, string> = {
  brak: 'Brak wody',
  niski: 'Niski',
  normalny: 'Normalny',
  wysoki: 'Wysoki',
}

export const TONE_HEX = { ok: '#5F9F63', warn: '#E2A23B', danger: '#C0473C' } as const
