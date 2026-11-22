/**
 * Kolory kodów gleby IUNG (SPEC 5.3) – wspólne dla legendy warstwy „Gleba” i karty gleby w panelu.
 * 1–4 kategorie podatności na suszę, 5 organiczne, 11 las, 12 woda, 13 zabudowa, 14 drogi/nieużytki.
 */
export const SOIL_COLOR: Record<number, string> = {
  1: '#F2D64B',
  2: '#F0A04B',
  3: '#D9722E',
  4: '#9C3D2A',
  5: '#8E918F',
  11: '#4E7A5A',
  12: '#2F80C9',
  13: '#7A7F7C',
  14: '#B8BDB9',
}

/** Kolor dla nieznanego kodu – szary „brak danych”. */
export const soilColor = (code: number) => SOIL_COLOR[code] ?? '#B8BDB9'

/** Etykiety kategorii IUNG (kody 1–5) – legenda warstwy „Gleba”. */
export const SOIL_CLASS_LABELS: Record<number, string> = {
  1: 'I – bardzo podatna na suszę',
  2: 'II – podatna',
  3: 'III – średnio podatna',
  4: 'IV – mało podatna',
  5: 'Gleby organiczne',
}
