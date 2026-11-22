# Status – osoba B (Mefju), frontend

_Stan na: 2026-11-22 (F1 – A za B)_

## Zrobione
- **F4 (A za B)**: karta powitalna chowa się przy przybliżaniu/przeciąganiu; publiczny link (VITE_API_URL, vercel.json, render.yaml, DEPLOY.md); README.md.
- **F3 (A za B)** na mockach: adresy w wyszukiwarce, teren i woda w okolicy liczone w tle, warstwa i karta „Woda w okolicy”, przychód z pola i ceny, „Okres” (zakres dat) z kartą i wykresem, satelita POST dla pola narysowanego. Czeka na backend F3.
- **F2 (A za B)**: przykłady tylko z `/api/demo/examples`, „Narysuj swoje pole” (POST z `geometry`), stany ładowania/błędów przed wyborem działki, poprawki 390 px (tabele w paszporcie).
- **F1 (A za B)**: baner obszaru przybliżonego, źródła opadów IMGW (A7) w werdykcie i paszporcie, satelita (A11): karta „Z satelity”, dociąganie `/api/satellite`, warstwy Kondycja / Wilgotność z legendą z serwera, „Rośliny” w werdykcie; jedna liczba sezonu w „Bilans wody” i paszporcie; „Teraz: …” przy statusie.
- Układ wg `design/SPEC_UI.md` – kroki 1–2 z sekcji 17: tokeny (paleta, Inter, cienie, zaokrąglenia, lucide), ekran Start (lewy pasek, górny pasek z wyszukiwarką / lokalizacją / pogodą / datą, pigułki warstw + 2D|3D, mapa, prawy panel, dolny pasek 5 kart), tablet, telefon (szuflada z 3 położeniami, dolne zakładki).
- Panel działki i komponenty SPEC 14 (StatusBadge, MetricCard, SourceTag, ScoreRing, RecommendationCard, LoadingSteps, EmptyState, ErrorNotice, ParcelLabel, LegendCard, MapControls); stany pusty / ładowanie / błąd / brak danych.
- Przełącznik języka PL | EN (D47), domyślnie polski; teksty z backendu zostają po polsku.
- Wybór uprawy i daty uruchamia analizę (zmiana = przeliczenie); ekran ładowania z krokami, licznikiem i szkieletami; na mocku symulacja kroków, bez mocka `/api/analysis` (501 → komunikat „w budowie”).
- Wybór uprawy (15 upraw IUNG), zapis działek w pamięci przeglądarki, prognoza 7 dni z `/api/forecast`.
- Struktura `api/ mocks/ theme/ layout/ components/ features/ pages/`; panel czyta wynik analizy wg kontraktu, mock pod `?dane=przykladowe`.
- **B5–B9**: paszport wodny A–E (wykresy, wydruk, „Pokaż na mapie”), Moje działki / Raporty / Ustawienia (pamięć przeglądarki, nawigacja, `?widok=paszport`), dolne karty i oś czasu z danych analizy, warstwy mapy podpięte do `/api/layers`, zgłoszenia rowów i zbiorników (kreator, pismo, pinezki). Frontend korzysta z prawdziwego `/api/analysis` (mock tylko z `?dane=przykladowe`). Sprawdzane zrzutami w Edge (1440 px i 390 px).
- **B3 – link do analizy i raport PDF**: `?dzialka=&uprawa=&data=` otwiera od razu analizę, „Kopiuj link”, „Pobierz raport PDF” (`/api/report.pdf`, dziś 404 → komunikat „w budowie”).
- **B2 – pola kontraktu A3b w panelu**: faza uprawy, woda w glebie (też poza sezonem, porównanie z 10 latami), plan nawadniania, gleba IUNG, „To nie jest grunt rolny”.
- **B28 – A5e/A7 w UI**: „Co planujesz posiać?” + „Twój wybór” i lepsze możliwości, „Nie siej:”, formularz „Przygotuj raport” (skrócony 2 str. / szczegółowy), 11 słupków „Na tle 10 lat”, „dane pogodowe do”, zdanie o stacjach IMGW.
- **B27 – przeprojektowanie ekranu mapy (etap 1)**: górny pasek w 1 wierszu, „Warstwa: …” zamiast pigułek, „Moje gospodarstwo” zamiast paska kart, kontrolki w prawym dolnym rogu, „Ryzyko suszy” na górze panelu, jedna karta dla gruntu nierolnego. Etap 2: zakładki panelu, `en.json`.
- **B26 – wyszukiwarka `/api/search` + B3 bez uprawy**: podpowiedzi Działki/Miejscowości, ranking „Co tu posiać?”, „Doprecyzuj” (uprawa, historia pola, powierzchnia), obszar przybliżony po punkcie, panel z mniejszą liczbą informacji.
- **B1 – wygląd dopasowany do grafik wzorcowych** (`ref-desktop`, `ref-mobile`, nowa `ref-style` – wykonana przez nas, źródło `design/ref-style.src.html`): pływające elementy bez linii, pogoda·data·język w jednej pigułce, dolny pasek jako jedna karta z podziałami, płaskie karty w panelu, karta stanu ze strzałką ›, okrąg z torem -soft w kolorze stanu, legendy (pasek 6 px, próbka „Chmury”), lewy pasek z kartą hasła jak na ref-desktop.

## W trakcie (gałąź)
- `b/frontend` (jedna długa gałąź; B1 z `b/wyglad-grafiki` już scalone) – merge do `main` tylko przy kamieniach milowych, bez PR na zadanie

## Następne
- F3: po wdrożeniu backendu – sprawdzić na żywo; przenieść `revenue`/`price_now` z `mocks/prices.sample.json` do `analysis.choice.sample.json`, gdy `schemas/` je przyjmie.
- F2: wizualna kontrola przez A na http://localhost:5173 (lista kroków w raporcie F2); ewentualne poprawki z jego zrzutów.
- F1: zrobione (teksty, przycięcie warstw do obrysu, „Spróbuj ponownie” w legendzie). Do sprawdzenia na żywo: „Spróbuj ponownie” przy prawdziwym błędzie warstwy.
0. **Uwagi mentora (jury ma 3 min):** karty „Zobacz przykład” są (B10, lista lokalna) – podmienić na `GET /api/demo/examples`; po merge `origin/a/backend` z nowym kontraktem – pole „Co rosło w zeszłym roku?” (+ `przedplon` w linku i raporcie), odznaki formalności / ostrzeżenie / ekoschemat w rekomendacjach (3 w panelu, 5 w paszporcie), gleba: piasek/pył/ił %, uziarnienie, przepuszczalność, ulewa, typ gleby.
1. Widok 3D – zrobiony (B21) na kaflach ~30 m; dokładniej po endpoincie siatki NMT od A (propozycja w dzienniku B21).

## Blokery / pytania do drugiej osoby
- **Licencja:** react-leaflet 5 i @react-leaflet/core 3 = Hippocratic-2.1 (niepermisywna) – decyzja: zamiana na własną warstwę nad Leafletem (BSD-2)?
- Backend (opcjonalnie, DEPLOY.md pkt 8): regex CORS dla podglądów Vercela, seed cache w obrazie dla planu free Render.
- A: słupki 10 lat – zrobione przez A (`seasonal_balance_by_year`, A5e), frontend podpięty (B28).
- A: wyszukiwanie miejsc – zrobione przez A (`/api/search`), frontend podpięty (B26).
- A: pole `irrigation_practice` (np. `"not_practiced"` dla zbóż i rzepaku) w odpowiedzi analizy – frontend ma na razie listę lokalną (`lib/crops.ts` `IRRIGATION_NOT_PRACTICED`); gdzie będzie pole (np. `crop_season` / `irrigation`)?
- A: `/api/parcel` 404 dla 4 działek testowych z `.ai/test-parcels.md` (szczegóły w dzienniku B10) – przykłady używają na razie tylko działających (6/1 Wnory-Wandy, 112/11 Szczytno).
- A: zgłoszenia rowów (`/api/infra-reports`, `/confirm`, `/letter`) i raport PDF (`/api/report.pdf`) – frontend gotowy, czeka na endpointy (dziś 501/404). Pole na zdjęcie w `InfraReportIn`? (dziś zdjęcie zostaje na urządzeniu).
- A: format obiektów warstw (`features[].properties`: `kind`, `color`, `label`) – propozycja w dzienniku B8; frontend rysuje już dane z `/api/layers`, czeka na endpoint (dziś 501).
- A: przełącznik PL | EN (D47) – czy backend może przyjmować `lang` i zwracać teksty (błędy, rekomendacje) po angielsku? Do tego czasu zostają po polsku.
- A: kiedy pierwsza wersja `/api/analysis` (choćby z częścią wskaźników)?
