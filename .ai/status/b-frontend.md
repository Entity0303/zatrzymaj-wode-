# Status – osoba B (Mefju), frontend

_Stan na: 2026-11-21_

## Zrobione
- Układ wg `design/SPEC_UI.md` – kroki 1–2 z sekcji 17: tokeny (paleta, Inter, cienie, zaokrąglenia, lucide), ekran Start (lewy pasek, górny pasek z wyszukiwarką / lokalizacją / pogodą / datą, pigułki warstw + 2D|3D, mapa, prawy panel, dolny pasek 5 kart), tablet, telefon (szuflada z 3 położeniami, dolne zakładki).
- Panel działki i komponenty SPEC 14 (StatusBadge, MetricCard, SourceTag, ScoreRing, RecommendationCard, LoadingSteps, EmptyState, ErrorNotice, ParcelLabel, LegendCard, MapControls); stany pusty / ładowanie / błąd / brak danych.
- Przełącznik języka PL | EN (D30), domyślnie polski; teksty z backendu zostają po polsku.
- Wybór uprawy i daty uruchamia analizę (zmiana = przeliczenie); ekran ładowania z krokami, licznikiem i szkieletami; na mocku symulacja kroków, bez mocka `/api/analysis` (501 → komunikat „w budowie”).
- Wybór uprawy (15 upraw IUNG), zapis działek w pamięci przeglądarki, prognoza 7 dni z `/api/forecast`.
- Struktura `api/ mocks/ theme/ layout/ components/ features/ pages/`; panel czyta wynik analizy wg kontraktu, mock pod `?dane=przykladowe`.

## W trakcie (gałąź)
- `b/frontend` (jedna długa gałąź, merge do `main` tylko przy kamieniach milowych)

## Następne
1. Dopasowanie wyglądu do grafik wzorcowych `design/ref-desktop.png`, `ref-mobile.png`, `ref-style.png` (odstępy, kolory, kształty).
2. Warstwy mapy (krok 3 SPEC 17) – na razie tylko legendy; dane po gotowym `/api/layers`.
3. Paszport wodny A–E na mocku (krok 4), wykresy Recharts w SectionB.

## Blokery / pytania do drugiej osoby
- A: przełącznik PL | EN (D30) – czy backend może przyjmować `lang` i zwracać teksty (błędy, rekomendacje) po angielsku? Do tego czasu zostają po polsku.
- A: czekam na kontrakt sekcji gleby (`origin/a/backend`) – „To nie jest grunt rolny”.
- **Brak grafik wzorcowych w repo**: w `design/` jest tylko `SPEC_UI.md` – `ref-desktop.png`, `ref-mobile.png`, `ref-style.png` trzeba dodać, inaczej krok 1 z „Następne” nie ruszy.
- A: kiedy pierwsza wersja `/api/analysis` (choćby z częścią wskaźników)?
