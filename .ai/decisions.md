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

### D14 · 2026-11-21 · Sezon bilansu domyślnie od 1 marca
**Uzasadnienie:** początek okresu wegetacyjnego i okres oceny w metodyce suszy rolniczej (KBW liczony od wiosny). Reguła liczona względem **ostatniego dnia z danymi** (data analizy − 1): jeśli jest przed 1 marca, sezon zaczyna się 1 marca roku poprzedniego. Dla daty analizy 1 marca daje to sezon poprzedni (bieżący miałby 0 dni).
**Konsekwencje:** `analysis/water_balance.default_season_start`; parametr `season_start` pozwala to zmienić (np. per uprawa w A3).

### D15 · 2026-11-21 · Dane pogodowe tylko do dnia przed datą analizy; zakres od 1 stycznia (rok początku sezonu − 10)
**Uzasadnienie:** zasada „tylko dane sprzed daty analizy”. Dla dat przed 1 marca sezon zaczyna się rok wcześniej, więc 10 poprzednich sezonów wymaga danych od roku daty − 11 (o rok więcej niż „rok daty − 10”).
**Konsekwencje:** `history_range()`; opóźnienie publikacji (NASA POWER ~2–4 dni) nie jest maskowane – „Dane pogodowe do dnia X” w ograniczeniach.

### D16 · 2026-11-21 · ET0 przy źródle zapasowym: wartość z archiwum Open-Meteo przed Hargreavesem
**Uzasadnienie:** archiwum nie podaje promieniowania, wilgotności ani wiatru (PM niemożliwe), ale podaje ET0 FAO-56 liczone z ERA5 – dokładniejsze niż Hargreaves z samej temperatury. Uzupełnia D2.
**Konsekwencje:** kolejność metod na dzień: PM → OM → HG → brak; liczba dni wg metody w metadanych i ograniczeniach.

### D17 · 2026-11-21 · Obsługa braków w bilansie
**Uzasadnienie:** brak danych nie może udawać pełności ani zaniżać wyniku bez informacji.
**Konsekwencje:** rok porównawczy z > 10% braków w okresie – pomijany (lista w ograniczeniach); pojedyncze dni bez danych w bieżącym sezonie – 0 mm w bilansie + ograniczenie „N dni bez danych”; miesiąc z > 20% braków – brak sumy (`null`); percentyl = % lat porównawczych z niższym bilansem (0 = najgorszy z 10 lat).

### D18 · 2026-11-21 · Budżet czasu pobierania pogody
**Uzasadnienie:** limit 30 s na całą analizę. NASA POWER zwykle ~1,6–1,9 s za 10 lat.
**Konsekwencje:** NASA POWER: 9 s na próbę + 1 ponowna próba (sieć/timeout/5xx; 429 bez ponawiania); archiwum Open-Meteo: 10 s, bez ponawiania. Cache 6 h, klucz – współrzędne zaokrąglone do 0,1° (rozdzielczość źródła ~50 km) + zakres dat.
