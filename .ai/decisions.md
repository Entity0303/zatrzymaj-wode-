# Decyzje projektowe

Wpis: data · decyzja · uzasadnienie · konsekwencje. Zmieniany w osobnym małym commicie. Nowe decyzje na dole.

---

### D1 · 2026-11-21 · NASA POWER jako główne źródło pogody z 10 lat
**Uzasadnienie:** dzienne dane od dziesięcioleci dla dowolnego punktu, bez klucza, ~1,6 s na 10 lat (wszystkie parametry do ET0 w jednym zapytaniu). Archiwum Open-Meteo (ERA5-Land ~10 km) ma dzienny limit na IP – w sieci hackathonu zwraca 429.
**Konsekwencje:** rozdzielczość ~50 km → ograniczenie „Pogoda uśredniona dla obszaru ok. 50 km” w wiarygodności. Archiwum Open-Meteo tylko jako źródło opcjonalne z fallbackiem na NASA POWER. Open-Meteo forecast – prognoza 16 dni.

### D2 · 2026-11-21 · ET0 liczone samodzielnie wg FAO-56 (Penman-Monteith), fallback Hargreaves
**Uzasadnienie:** kontrola nad metodą i jednolitość dla 10 lat; zgodność z metodyką (KBW = opad − ET0). Hargreaves wymaga tylko temperatury – gdy brakuje promieniowania, wilgotności lub wiatru.
**Konsekwencje:** metoda oznaczana dla każdego dnia (`PM`/`HG`); udział dni Hargreavesa obniża pewność. Test na przykładzie 18 z FAO-56.

### D3 · 2026-11-21 · Kategorie gleb IUNG (WOD) jako podstawa pojemności wodnej
**Uzasadnienie:** ogólnopolska mapa podatności na suszę używana w oficjalnym SMSR, z zakresami wody ogólnie dostępnej (WOD) dla kategorii I–IV; dostępna przez WMS GetFeatureInfo.
**Konsekwencje:** działkę próbkujemy kilkoma punktami → udziały kategorii; kody 11–14 = „to nie jest grunt rolny”.

### D4 · 2026-11-21 · Klasy bonitacyjne EGiB (KIEG) tylko informacyjnie
**Uzasadnienie:** usługa obejmuje tylko część powiatów, format HTML – nie da się na niej oprzeć obliczeń dla dowolnej działki w Polsce.
**Konsekwencje:** pokazywane w szczegółach, gdy dostępne; brak = ograniczenie, nie błąd.

### D5 · 2026-11-21 · NMT przez GetHByPointList zamiast WCS
**Uzasadnienie:** WCS za wolny dla wymogu < 30 s; GetHByPointList zwraca wysokości ±0,1 m dla listy punktów (POST do 1000 punktów ~2,5 s).
**Konsekwencje:** siatka punktów w obrysie + bufor; kolejność osi x = PÓŁNOC, y = WSCHÓD (odwrotnie niż ULDK). Spadki, dołki, spływ, TWI liczone w numpy (bez bibliotek GPL).

### D6 · 2026-11-21 · BDOT10k zamiast OSM/Overpass dla rowów i wód
**Uzasadnienie:** urzędowa baza z rozróżnieniem rów melioracyjny / ciek / kanał / zbiornik i datą aktualizacji; Overpass – niepełne rowy, limity publicznych serwerów.
**Konsekwencje:** WMS GetMap (odległość) + GetFeatureInfo (`x_kod`, data); typ obiektu decyduje o adresacie pisma (ciek → Wody Polskie, rów → właściciel/spółka wodna).

### D7 · 2026-11-21 · Sentinel-2 z Earth Search (2017+) + Copernicus Data Space (2016)
**Uzasadnienie:** Earth Search STAC – darmowe COG L2A, odczyt fragmentu przez rasterio bez pobierania sceny; brak 2016 → Copernicus Data Space STAC, żeby objąć pełne 10 lat.
**Konsekwencje:** zdjęcie najbliższe *przed* datą analizy, maska chmur SCL, data zdjęcia w `source_tag`.

### D8 · 2026-11-21 · Nie pokazujemy pH, składników pokarmowych ani temperatury gleby
**Uzasadnienie:** brak takich danych w publicznych źródłach dla dowolnej działki; zasada „wszystko liczone z danych”.
**Konsekwencje:** sekcja Gleba = kategoria podatności, ile wody zmieści gleba, klasa bonitacyjna (gdy dostępna) – SPEC 15.3.

### D9 · 2026-11-21 · Interfejs wyłącznie po polsku, prostym językiem
**Uzasadnienie:** użytkownik – rolnik bez wiedzy GIS (KOWR, SPEC 1).
**Konsekwencje:** słownik SPEC 1 (np. „Kondycja upraw” zamiast NDVI); terminy techniczne tylko w „Szczegółach”.

### D10 · 2026-11-21 · Czcionka Inter (SIL OFL 1.1), dołączona lokalnie
**Uzasadnienie:** wymagana przez SPEC 2.3; OFL 1.1 to licencja permisywna dla czcionek (dopisana do zasady licencji w CLAUDE.md). Pakiet `@fontsource-variable/inter` – bez zapytań do Google Fonts.

### D11 · 2026-11-21 · Brak kont, logowania i stron prawnych
**Uzasadnienie:** działający prototyp na hackathon, bez danych osobowych; liczy się ścieżka Szukaj działki → Zobacz pole → Zrozum stan → Rekomendacje → Raport.
**Konsekwencje:** zapis działek i raportów tylko w pamięci przeglądarki; bez polityki prywatności, cookies, RODO, admina, „O nas”.

### D12 · 2026-11-21 · Mock analizy tylko z parametrem `?dane=przykladowe`
**Uzasadnienie:** `docker compose up` uruchamia serwer deweloperski, więc warunek „tylko w trybie dev” włączałby mock zawsze i udawał prawdziwe dane.
**Konsekwencje:** mock = tryb dev **i** parametr w adresie; widoczny napis „DANE PRZYKŁADOWE”; plik JSON usuwany z buildu produkcyjnego.

### D13 · 2026-11-21 · Ortofotomapa przez WMTS (EPSG:3857) zamiast WMS
**Uzasadnienie:** WMS Geoportalu obsługuje EPSG:3857, ale kafel ~4,5 s; WMTS tej samej usługi (te same zdjęcia, kafle z cache) ~2,3 s.
**Konsekwencje:** `features/map/ParcelMap.tsx` – szablon KVP GetTile; OSM jako zapas.

### D30 · 2026-11-21 · Przełącznik języka PL | EN (domyślnie polski) – zmienia D9
**Uzasadnienie:** prośba osoby B – interfejs ma być czytelny także dla osób nieznających polskiego (np. jury, goście). Polski zostaje językiem domyślnym, więc rolnik nic nie musi przełączać.
**Konsekwencje:** własny mały moduł `frontend/src/lib/i18n.ts` (bez nowej zależności): kluczem tłumaczenia jest tekst polski (`t('Szukam działki')`, zmienne `{n}`), słownik `lib/i18n.en.ts`, brak wpisu = tekst polski. Wybór zapamiętany w przeglądarce (`zw.lang.v1`), przełącznik w górnym pasku. Liczby i daty w formacie języka. Teksty z backendu (komunikaty błędów, rekomendacje, opisy) zostają po polsku, dopóki backend nie obsłuży języka – wyjątek: opisy pogody Open-Meteo i teksty mocka są w słowniku. Nowy tekst w UI = nowy wpis w `i18n.en.ts`.
