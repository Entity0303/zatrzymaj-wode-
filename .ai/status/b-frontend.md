# Status – osoba B (Mefju), frontend

_Stan na: 2026-11-21_

## Zrobione
- Układ wg `design/SPEC_UI.md` – kroki 1–2 z sekcji 17: tokeny (paleta, Inter, cienie, zaokrąglenia, lucide), ekran Start (lewy pasek, górny pasek z wyszukiwarką / lokalizacją / pogodą / datą, pigułki warstw + 2D|3D, mapa, prawy panel, dolny pasek 5 kart), tablet, telefon (szuflada z 3 położeniami, dolne zakładki).
- Panel działki i komponenty SPEC 14 (StatusBadge, MetricCard, SourceTag, ScoreRing, RecommendationCard, LoadingSteps, EmptyState, ErrorNotice, ParcelLabel, LegendCard, MapControls); stany pusty / ładowanie / błąd / brak danych.
- Przełącznik języka PL | EN (D35), domyślnie polski; teksty z backendu zostają po polsku.
- Wybór uprawy i daty uruchamia analizę (zmiana = przeliczenie); ekran ładowania z krokami, licznikiem i szkieletami; na mocku symulacja kroków, bez mocka `/api/analysis` (501 → komunikat „w budowie”).
- Wybór uprawy (15 upraw IUNG), zapis działek w pamięci przeglądarki, prognoza 7 dni z `/api/forecast`.
- Struktura `api/ mocks/ theme/ layout/ components/ features/ pages/`; panel czyta wynik analizy wg kontraktu, mock pod `?dane=przykladowe`.
- **B2 – pola kontraktu A3b w panelu**: faza uprawy, woda w glebie (też poza sezonem, porównanie z 10 latami), plan nawadniania, gleba IUNG, „To nie jest grunt rolny”.
- **B1 – wygląd dopasowany do grafik wzorcowych** (`ref-desktop`, `ref-mobile`, nowa `ref-style` – wykonana przez nas, źródło `design/ref-style.src.html`): pływające elementy bez linii, pogoda·data·język w jednej pigułce, dolny pasek jako jedna karta z podziałami, płaskie karty w panelu, karta stanu ze strzałką ›, okrąg z torem -soft w kolorze stanu, legendy (pasek 6 px, próbka „Chmury”), lewy pasek z kartą hasła jak na ref-desktop.

## W trakcie (gałąź)
- `b/frontend` (jedna długa gałąź; B1 z `b/wyglad-grafiki` już scalone) – merge do `main` tylko przy kamieniach milowych, bez PR na zadanie

## Następne
1. Sprawdzić B1 w przeglądarce (komputer, tablet, telefon; z `?dane=przykladowe`) – dotąd weryfikacja tylko `npm run build`.
2. Warstwy mapy (krok 3 SPEC 17) – na razie tylko legendy; dane po gotowym `/api/layers`.
4. Paszport wodny A–E na mocku (krok 4), wykresy Recharts w SectionB.

## Blokery / pytania do drugiej osoby
- A: przełącznik PL | EN (D35) – czy backend może przyjmować `lang` i zwracać teksty (błędy, rekomendacje) po angielsku? Do tego czasu zostają po polsku.
- A: kiedy pierwsza wersja `/api/analysis` (choćby z częścią wskaźników)?
