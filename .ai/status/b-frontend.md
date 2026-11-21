# Status – osoba B (Mefju), frontend

_Stan na: 2026-11-21_

## Zrobione
- Układ wg `design/SPEC_UI.md` – kroki 1–2 z sekcji 17: tokeny (paleta, Inter, cienie, zaokrąglenia, lucide), ekran Start (lewy pasek, górny pasek z wyszukiwarką / lokalizacją / pogodą / datą, pigułki warstw + 2D|3D, mapa, prawy panel, dolny pasek 5 kart), tablet, telefon (szuflada z 3 położeniami, dolne zakładki).
- Panel działki i komponenty SPEC 14 (StatusBadge, MetricCard, SourceTag, ScoreRing, RecommendationCard, LoadingSteps, EmptyState, ErrorNotice, ParcelLabel, LegendCard, MapControls); stany pusty / ładowanie / błąd / brak danych.
- Przełącznik języka PL | EN (D40), domyślnie polski; teksty z backendu zostają po polsku.
- Wybór uprawy i daty uruchamia analizę (zmiana = przeliczenie); ekran ładowania z krokami, licznikiem i szkieletami; na mocku symulacja kroków, bez mocka `/api/analysis` (501 → komunikat „w budowie”).
- Wybór uprawy (15 upraw IUNG), zapis działek w pamięci przeglądarki, prognoza 7 dni z `/api/forecast`.
- Struktura `api/ mocks/ theme/ layout/ components/ features/ pages/`; panel czyta wynik analizy wg kontraktu, mock pod `?dane=przykladowe`.
- **B5–B9**: paszport wodny A–E (wykresy, wydruk, „Pokaż na mapie”), Moje działki / Raporty / Ustawienia (pamięć przeglądarki, nawigacja, `?widok=paszport`), dolne karty i oś czasu z danych analizy, warstwy mapy podpięte do `/api/layers`, zgłoszenia rowów i zbiorników (kreator, pismo, pinezki). Frontend korzysta z prawdziwego `/api/analysis` (mock tylko z `?dane=przykladowe`). Sprawdzane zrzutami w Edge (1440 px i 390 px).
- **B3 – link do analizy i raport PDF**: `?dzialka=&uprawa=&data=` otwiera od razu analizę, „Kopiuj link”, „Pobierz raport PDF” (`/api/report.pdf`, dziś 404 → komunikat „w budowie”).
- **B2 – pola kontraktu A3b w panelu**: faza uprawy, woda w glebie (też poza sezonem, porównanie z 10 latami), plan nawadniania, gleba IUNG, „To nie jest grunt rolny”.
- **B1 – wygląd dopasowany do grafik wzorcowych** (`ref-desktop`, `ref-mobile`, nowa `ref-style` – wykonana przez nas, źródło `design/ref-style.src.html`): pływające elementy bez linii, pogoda·data·język w jednej pigułce, dolny pasek jako jedna karta z podziałami, płaskie karty w panelu, karta stanu ze strzałką ›, okrąg z torem -soft w kolorze stanu, legendy (pasek 6 px, próbka „Chmury”), lewy pasek z kartą hasła jak na ref-desktop.

## W trakcie (gałąź)
- `b/frontend` (jedna długa gałąź; B1 z `b/wyglad-grafiki` już scalone) – merge do `main` tylko przy kamieniach milowych, bez PR na zadanie

## Następne
0. **Uwagi mentora (jury ma 3 min):** karty „Zobacz przykład” są (B10, lista lokalna) – podmienić na `GET /api/demo/examples`; po merge `origin/a/backend` z nowym kontraktem – pole „Co rosło w zeszłym roku?” (+ `przedplon` w linku i raporcie), odznaki formalności / ostrzeżenie / ekoschemat w rekomendacjach (3 w panelu, 5 w paszporcie), gleba: piasek/pył/ił %, uziarnienie, przepuszczalność, ulewa, typ gleby.
1. Widok 3D (SPEC 8, P3) – na końcu.

## Blokery / pytania do drugiej osoby
- A: `/api/parcel` 404 dla 4 działek testowych z `.ai/test-parcels.md` (szczegóły w dzienniku B10) – przykłady używają na razie tylko działających (6/1 Wnory-Wandy, 112/11 Szczytno).
- A: zgłoszenia rowów (`/api/infra-reports`, `/confirm`, `/letter`) i raport PDF (`/api/report.pdf`) – frontend gotowy, czeka na endpointy (dziś 501/404). Pole na zdjęcie w `InfraReportIn`? (dziś zdjęcie zostaje na urządzeniu).
- A: format obiektów warstw (`features[].properties`: `kind`, `color`, `label`) – propozycja w dzienniku B8; frontend rysuje już dane z `/api/layers`, czeka na endpoint (dziś 501).
- A: przełącznik PL | EN (D40) – czy backend może przyjmować `lang` i zwracać teksty (błędy, rekomendacje) po angielsku? Do tego czasu zostają po polsku.
- A: kiedy pierwsza wersja `/api/analysis` (choćby z częścią wskaźników)?
