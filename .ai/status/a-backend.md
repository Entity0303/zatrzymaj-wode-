# Status – osoba A (Dominik), backend

_Stan na: 2026-11-22 06:00_

## Zrobione
- Wyszukiwanie działki ULDK: pełny identyfikator, „obręb numer”, punkt; `GET /api/parcel` (409 lista kandydatów, 404, 502 z nazwą źródła), timeout 10 s + jedna ponowna próba, cache 24 h.
- Prognoza pogody: `GET /api/forecast` (Open-Meteo), cache 30 min.
- Kontrakt `GET /api/analysis` w `schemas/analysis.py`; endpoint zwraca 501. Szkielety: `/api/layers`, `/api/reports`, `/api/infra-reports`.
- **A1 (scalone, PR #1):** historia pogody 10 lat – NASA POWER (+ zapasowo archiwum Open-Meteo), ET0 FAO-56 z metodą na każdy dzień, `analysis/water_balance.py` → sekcja `history` (bilans narastająco od 1 marca, pasmo 10 lat, opady miesięczne, braki/opóźnienie w ograniczeniach). Tymczasowy `GET /api/dev/weather-history`.
- **Kontrakt:** `History` rozszerzone o `balance_deviation_mm`, `balance_rank`, `longest_dry_spell`, `band_years` (uzgodnione z B) – wypełniane przez `build_history`.
- **A2 (gałąź `a/gleba`):** gleba – IUNG przez WCS (kody komórek 5 m), zapasowo GetFeatureInfo; klasy EGiB z KIEG; `analysis/soil.py` → `indicators.soil_capacity`, flaga „to nie jest grunt rolny”. Tymczasowy `GET /api/dev/soil`.
- **Kontrakt:** `History` + 4 pola (A1→A2); **nowa sekcja `soil`** (A3, uzgodnione z B) – wypełniana przez `analysis/soil.to_contract`.
- **A3 + A3b (gałąź `a/backend`):** `analysis/crops.py` – 15 upraw (Kc, fazy przeskalowane do siew–zbiór w PL, Zr, p, terminy zbioru, kalendarz całego roku: przed siewem / fazy / dojrzewanie / po zbiorze / wschody jesienne / spoczynek zimowy). Model wody w glebie FAO-56 w `analysis/water_balance.py` jako **ciągły bilans** od 1 XI (1 VII dla rzepaku jesiennego): profil 1 m w dwóch warstwach, korzenie rosną od siewu, goła gleba – parowanie dwuetapowe, siew nie resetuje zapasu, zimowa odbudowa z przesiąkaniem. Dni stresu tylko w fazach wrażliwych; w dojrzewaniu / po zbiorze / spoczynku brak alarmu i nawadniania. Nawadnianie: dawka wg kategorii gleby (17,5–32,5 mm, ≤ 35), harmonogram w 7 dniach, częstotliwość, łączny niedobór. Stan wody na każdą datę (także listopad) z opisem i porównaniem z 10 latami. Tymczasowy `GET /api/dev/water`.
- **Kontrakt:** `soil`, `crop_season`, `soil_water`, `irrigation` (A3, A3b – uzgodnione z B).
- **A4 – KAMIEŃ MILOWY 1 (gałąź `a/backend`):** pełne `GET /api/analysis?parcel_id=&crop=&date=` zgodne z kontraktem – ULDK → równolegle pogoda 10 lat, gleba IUNG, klasy EGiB, prognoza (dla dziś) → bilans i model wody → ocena (`analysis/scoring.py`) → pewność i `reliability` (`analysis/confidence.py`) → przyczyny z udziałami (`analysis/causes.py`) → rekomendacje z 19 reguł YAML (`analysis/recommendations.py`, `analysis/rules/*.yaml`; 4 wyłączone do A6/A7) z `in_panel` (maks. 3). Kroki z czasami, budżet 27 s, 502 tylko bez ULDK/pogody, 422 bez uprawy. Wspólne fakty: `analysis/facts.py`. Mock frontendu = zapis prawdziwej odpowiedzi.
- **A5 (gałąź `a/backend`) – konsultacja z mentorem + gotowość do 3-minutowej oceny:**
  - reguły przejrzane wg „Podstaw naukowych” KOWR (23, w tym 4 czekające na teren); panel maks. 3, paszport maks. 5; `warning` przy niskiej pewności (nigdy pierwsza); retencja zawsze obecna; `when`, `permit` (Wody Polskie), `eco_scheme` (ARiMR, bez kwot); „Odłóż nawożenie” przy silnym stresie; płodozmian z `previous_crop`;
  - gleba dla rolnika: SoilGrids (frakcje, klasa uziarnienia, Ksat Saxton–Rawls, woda z ulewy) + **mapa glebowo-rolnicza GUGiK działa** (kompleks, gatunek, rok mapy) – `sources/soilgrids.py`, `sources/soil_map.py`, `analysis/soil_texture.py`;
  - `app/demo.py` + `GET /api/demo/examples` (4 przykłady), rozgrzewka cache w tle przy starcie (`DEMO_WARMUP`), `GET /api/status`, **`GET /api/report.pdf`** (WeasyPrint, A4, SPEC 10.2, QR);
  - odporność: cache z TTL na wpis + przeterminowany wpis przy awarii (pewność −1 poziom), limity na źródło, bezpiecznik, ULDK 302 = chwilowa niedostępność (wcześniej błędnie 404);
  - `backend/scripts/smoke.py`, raporty przykładów w `reports/examples/`.
- **A5b-1 (gałąź `a/backend`) – fundament „Stan działki” + poprawki merytoryczne:**
  - nawadnianie wg praktyki (`irrigation_practice`, D48): zboża, rzepak, strączkowe – bez dawek (`nie_praktykowane`), zamiast tego 3 reguły (zatrzymanie wody, bez uprawek + odchwaszczanie, zabiegi rano/wieczorem) i zdanie „Zbóż w Polsce się nie nawadnia…”; kukurydza, burak, tytoń – z dopiskiem; „Susza 2018” – zero zaleceń nawadniania;
  - ekoschematy tylko E_MPW, E_USU, E_WSG, E_PN, E_MIOD, E_EKSTUZ (D51), kod spoza listy = błąd wczytania;
  - status poza sezonem i bez uprawy = 0,6 woda w profilu + 0,4 bilans 30 dni (D52), `status.scope/scope_label`;
  - zgodność gleby (`soil.consistency`, D49): mapa glebowo-rolnicza w 9 punktach, porównanie udziałów gleb lekkich z IUNG; 201305 = dwie gleby, źródła zgodne;
  - analiza i PDF bez uprawy: `field_state` (pokrycie referencyjne FAO-56, D50, przebieg od 1 XI z pasmem 10 lat, KBW 30 dni), `crop`/`crop_season`/`irrigation` = null, `suggestions` = null (A5b-2), PDF „Stan wodny działki”;
  - kontrakt (A5b-1 w `contract-changes.md`) + minimalne poprawki typów w 5 plikach frontendu (za zgodą właściciela);
  - `scripts/smoke_cached_uldk.py` – smoke w procesie z zapisanym obrysem ULDK (gdy ULDK ogranicza ruch).
- **A5d (gałąź `a/backend`) – odporność demo (ULDK blokuje IP sieci hackathonu):**
  - trwały cache SQLite wszystkich źródeł (`core/cache.py`, D53) w wolumenie Dockera `/data` – przeżywa restart i reload; działki, gleba, pogoda historyczna bez wygasania, prognoza 1 h; plik niedostępny = tylko pamięć (bez błędu startu);
  - działki: indeks znanych (cache + `app/data/demo_parcels.json`), po id i po punkcie bez ULDK; blokada ULDK (302 / 429 / HTML) → ponowienia 1 s i 3 s → bezpiecznik 60 s; wspólny bezpiecznik dla źródeł, stan w `/api/status` („ograniczony (do HH:MM)”, czas polski) (D54);
  - `DEMO_OFFLINE=true` – zero zapytań zewnętrznych, brak w cache = czytelny 502; `/api/demo/examples` pokazuje tylko przykłady, które da się policzyć (D55);
  - `scripts/warm_demo.py` (przygotowanie przed prezentacją), `scripts/demo_check.py` (ścieżka demo z czasami); `smoke_cached_uldk.py` usunięty.
- **A6 (gałąź `a/backend`) – teren i spływ wody z NMT (port prototypu osoby C, bez merge `c/research`):**
  - `sources/nmt.py` (POST po 1000 punktów, cache bez wygasania, bezpiecznik), `analysis/terrain.py` (rdzeń prototypu bez zmian + wejście aplikacyjne), `analysis/terrain_interpret.py` (kontrakt, zdania, progi oczka, warstwy), `rules/teren_gleba.yaml` (ocena stref z glebą) – D57–D59;
  - sekcja `terrain` w `/api/analysis` (z uprawą i bez), `terrain_note` przy braku NMT; `/api/layers/teren` i `/api/layers/splyw` (GeoJSON przycięty, 3–11 kB); 5 reguł z terenu (oczko główne / „do rozważenia”, zastawka, pas zieleni E_MIOD, mokradło); przyczyna „teren”; NMT w `/api/status`; raport PDF: „Teren działki” (pasek, zdania, mapka stref) + szczegóły w „Gleba i teren”;
  - zapas: zapisane prawdziwe wyniki NMT osoby C z 21.11 (`app/data/terrain/`, 201305 i 061704) – gdy NMT nie odpowiada;
  - wszystkie źródła bez przekierowań, treść 3xx nieczytana, limity rozmiaru, User-Agent „Wodoskop/0.1 (HackNation 2026)” (D56); znaleziony i naprawiony na żywo błąd podwójnego dekodowania gzip.
- **A5b-2a (gałąź `a/backend`) – ranking „Co tu posiać?”:**
  - dane osoby C w `app/data/crops/` (crops.csv = jedno źródło prawdy, plony GUS wg województw); `analysis/crops.py` czyta CSV (15 upraw analizy + 7 gatunków rankingu) – D60;
  - `analysis/suggestions.py` + `rules/ranking.yaml`: 17 upraw × 10 pełnych sezonów, plon FAO-33, Ym z GUS × gleba, kalibracja do „dobrego roku na przeciętnej glebie”, kategorie ✅/🟡/❌ z jednym zdaniem, grupa wieloletnich osobno – D61, D62;
  - `crop_history` (twarda przerwa, złe / dobre przedplony, zboże po zbożu) i `cultivated_area_ha` (plon w tonach) – D63;
  - kukurydza / tytoń bez dawek (D64); status poza sezonem i bez uprawy z percentyli tej samej daty, „zimowanie” dla ozimin, goła gleba po zbiorze w stanie działki (D65).
- **A5b-2b (gałąź `a/backend`) – werdykt działki + PDF:**
  - `analysis/verdict.py` + `rules/verdict.yaml`: `verdict` w `/api/analysis` (z uprawą i bez) – nagłówek + 4–6 zdań z liczbami (gleba, opady z KBW V–VI, teren × gleba, ✅/❌ uprawy z jednym powodem, 1–3 działania wodne, wybrana uprawa); progi w YAML (D68);
  - spójność: etykieta gleby ważona udziałem (`analysis/soil_label.py`; 201305 = gleba średnia, nie „zwięzła”), „obniżenie” vs „zagłębienie bez odpływu”, reguła próchnicy tylko dla lekkiej gleby (D66);
  - ranking: uprawy wieloletnie osobno (`suggestions.perennials`), kukurydza – status `informacyjne` (D67); kompleks przydatności rozstrzyga przydatność gleby (D70);
  - analiza po punkcie `lon`/`lat` – obszar przybliżony 1 ha, gdy ULDK nie odpowiada (`analysis/approx_area.py`, D69); test słabej ziemi: Puszcza Notecka i Kurpie – ❌ pszenica, rzepak; ✅ żyto, łubin (owies ❌ – D70);
  - PDF: str. 1 „Werdykt”, str. 2 „Co tu posiać?”, maks. 6 stron (D71); przykłady i PNG pierwszych stron: `reports/examples/{dobra,slaba}-*-p1.png`.
- **A5b-2c:** nazwa „Wodoskop” w PDF i API, bez QR (włącza `PUBLIC_URL`), „woda” w werdykcie = `info`, PDF obszaru przybliżonego bez komunikatów technicznych (D72).
- **A5c (gałąź `a/backend`) – wyszukiwanie + własny obrys pola:**
  - `GET /api/search?q=` (`routers/search.py`, `core/search_query.py`, `sources/{prng,nominatim,places}.py`): identyfikator → działka, „obręb numer” → działki (kilka obrębów = lista z gminą i powiatem; ponowienie z nazwą kanoniczną), nazwa → miejscowości (słownik demo + **PRNG GUGiK** + rezerwa Nominatim OSM); brak wyników = 200 + `hint`; awarie źródeł w `notices` (D73, D74);
  - UUG GUGiK zablokowany z tej sieci („blocked for abuse”), ULDK 302 – „Tczów 123” nie dało się potwierdzić na żywo (przyczyny w D74);
  - `GET /api/parcel?lon&lat` – istniał, dopisane testy; `Parcel.source` / `name`;
  - własny obrys: `POST /api/analysis` i `POST /api/report.pdf` z `geometry` (0,05–200 ha, w Polsce, bez samoprzecięć, id z kształtu, gmina z ULDK / Nominatim) – D75;
  - słownik demo `app/data/places_demo.json` (offline), `scripts/build_places_demo.py`.
- **A5e (gałąź `a/backend`) – raport krótszy + wybór rolnika:**
  - `planned_crops` (1–3) → `suggestions.choice` / `choice_summary` / `alternatives` / `not_recommended` / `top_ids` (`analysis/choice.py`, `rules/choice.yaml`) – D77;
  - `report_type` short (5 stron) / full (8–9 stron), nowe strony: Co tu posiać? · Woda na działce (słupki „Na tle 10 lat”) · Co zrobić z wodą (maks. 4) · Gleba, teren i skąd dane – D78;
  - jedno źródło liczby (mm do całości, odchylenie z zaokrąglonych), `history.summary` prostym zdaniem + `details`, `seasonal_balance_by_year` / `_mean_mm` / `_label`, `weather_data_until` – D78;
  - jeden stan wody poza sezonem uprawy (status = stan działki), `irrigation` tylko w fazach wzrostu, reguły nawadniania z `in_season`, jedno „najważniejsze” w PDF – D79; ziemniak `optional` – D76.
- **A5e-2:** raport skrócony = 2 strony (werdykt + co siać / 3 działania / mały wykres 10 lat), reszta w szczegółowym (D81); alternatywy tylko z mniejszym ryzykiem suszy (wyjątek: ❌ przez płodozmian), grupy upraw w planie siewu, płodozmian ludzkim językiem (D80); pola wykresu `year` / `balance_mm` / `current`.
- Testy: **437 bez sieci** (403 + 24 w `test_a5e.py` + kontrakt przykładu wyboru) (`docker run --network none`) + 5 live. Analiza z cache: 0,04–0,2 s; PDF 1–2 s (punkt przy blokadzie ULDK ~5 s – ponowienia ULDK).

## W trakcie (gałąź)
- `a/backend` – A5b-2b, A5b-2c, A5c, A5e i A5e-2 gotowe (commit + push); **do `main` nie mergowane**.

## Uwaga (A5e)
- Backend w kontenerze działa teraz w trybie **DEMO_OFFLINE** (tylko cache) – GUGiK oznaczył sieć jako nadużycie; przykłady PDF wygenerowane z cache. Powrót: `docker compose up -d backend` (bez zmiennej) – dopiero na innej sieci.

## Przed prezentacją (na dobrej sieci; w Git Bash poprzedź komendy `MSYS_NO_PATHCONV=1`)
1. `docker compose up -d --build` – backend z wolumenem cache (`/data/cache.sqlite`).
2. `docker compose exec backend python scripts/warm_demo.py --out /reports/examples` – pobiera brakujące działki z ULDK, potem wszystkie dane działek demo i PDF-y; na końcu „Działki demo gotowe: N z 5” (dziś **1 z 5** – ULDK blokuje).
3. `DEMO_OFFLINE=true docker compose up -d backend` (PowerShell: `$env:DEMO_OFFLINE="true"; docker compose up -d backend`) – tylko cache, zero zapytań zewnętrznych.
4. `docker compose exec backend python scripts/demo_check.py` – musi skończyć się „WYNIK: OK – ścieżka demo działa”.
5. `curl http://localhost:8000/api/status` – ULDK „ok” albo „ograniczony (do HH:MM)”; w trybie offline każde źródło „tryb demo offline” z liczbą wpisów w cache. Powrót do zwykłego trybu: `docker compose up -d backend` (bez zmiennej).

## Do zrobienia NA ŻYWO (ULDK GUGiK blokuje IP – 302 przez całe sesje A5b-1 i A5d)
1. `warm_demo.py` na sieci, w której ULDK odpowiada – uzupełni w `app/data/demo_parcels.json` działki z `needs_fetch`: **061704_2.0011.383/2** („Kukurydza – stan dziś”), **143203_2.0027.112/11** („To nie jest pole”), **Szczytno 126/3** (gm. Kampinos), **Lasotka 118** – i zacommitować plik.
2. Pełny `scripts/smoke.py` na wszystkich przykładach i działkach z `test-parcels.md`.
3. Nowe `reports/examples/kukurydza-dzis.pdf` i `to-nie-jest-pole.pdf` (dziś jeszcze z A5 – stara logika). Aktualne: `susza-2018.pdf`, `mokry-rok-2021.pdf`, `stan-dzialki-bez-uprawy.pdf`, `stan-dzialki-201305_2-0038-6-1.pdf`.
4. Kontrola „Kukurydza dziś” na 061704 (zastępczo na 201305: „poza sezonem”, 49 pkt) i zgodność gleby na 061704 i działkach testowych.
5. KIEG nie odpowiadał (0 wpisów w cache) – po restarcie w trybie online pierwsza analiza czeka na niego ~6 s (bezpiecznik nie przeżywa restartu); w DEMO_OFFLINE nie dotyczy.
6. **NMT GUGiK też odsyła 302** (A6) – porównanie na żywo 201305 z `research/terrain/out/201305_2.0038.6-1.facts.json` nie było możliwe; offline: ten sam kod rdzenia (testy prototypu przechodzą), siatka i liczba punktów identyczne z wynikiem C (test), zapisany wynik C używany jako zapas. Na dobrej sieci: `warm_demo.py` pobierze NMT do cache – potem porównać `terrain.zone_share_pct` z plikiem C.

## Następne
0. **Na żywo z innej sieci (A5c):** `Tczów 123`, `Tczów 123/4`, `Wola 1` przez `/api/search` (ULDK); ew. `GetRegionByNameOrId` (obręby / gminy po nazwie) jako dodatkowe źródło; porównanie PRNG z ULDK dla obrębów o nietypowych nazwach.
1. Werdykt i ranking – do weryfikacji z agronomem / mentorem: owies na piasku (dziś ❌), współczynniki gleby, progi kategorii, próg KBW V–VI < −100 mm i 3 / 5 lat; norma opadów (NASA POWER zawyża względem IMGW).
2. Obszar przybliżony: województwo z granic administracyjnych zamiast najbliższego środka (dziś przy granicy może być sąsiednie).
3. Rowy i cieki BDOT10k (zastawka potwierdzona na mapie, warstwa „Spływ” z rowami), Sentinel-2; pas buforowy po warstwicy.
4. README, `/api/layers`, sprzątanie `/api/dev/*`; ceny skupu (`price`).

## Blokery / pytania do drugiej osoby
- **B (Mefju): panel działki pokazuje „Stan działki” od razu po wybraniu działki – `GET /api/analysis` bez `crop` → `field_state`, `soil.consistency`, rekomendacje retencyjne** (szczegóły i lista plików frontendu zmienionych przez A: `contract-changes.md`, wpis A5b-1, „Dla Mefju”).
- B: `IrrigationCard` – status `nie_praktykowane` (dziś etykieta „Nie stosuje się”); `status.scope_label` („poza sezonem”) przy karcie stanu; `storage.ts` – czy zapamiętywać analizę bez uprawy.
- B: obraz kontenera frontendu nie ma `@fontsource-variable/fraunces` – `docker compose build frontend`.
- **B (A5b-2a): ranking „Co tu posiać?”, pola historii 1–3 lat i powierzchni** – `contract-changes.md`, wpis A5b-2a „Dla Mefju”.
- **B (A5b-2b): karta „Werdykt” na samej górze panelu, pasek stref, oznaczenie obszaru przybliżonego, klik na mapie → `?lon=&lat=`, sekcja wieloletnich, status `informacyjne`** – `contract-changes.md`, wpis A5b-2b „Dla Mefju”.
- **B (A5e-2): pola wykresu `year` / `balance_mm` / `current`; „Raport skrócony / szczegółowy”; grupy w „Co planujesz posiać?”; `group_note`, `choice_notes`** – `contract-changes.md`, wpis A5e-2.
- **B (A5e): formularz „Przygotuj raport” (co planujesz posiać, historia pola, powierzchnia, krótki / pełny), ten sam blok w panelu „Co tu posiać?” (Twój wybór + lepsze możliwości + „Nie siej”), wykres słupkowy „Na tle 10 lat” z `seasonal_balance_by_year`, jeden stan wody poza sezonem** – `contract-changes.md`, wpis A5e „Dla Mefju”.
- **B (A5c): lista podpowiedzi `/api/search` (grupy Działki / Miejscowości, debounce 300 ms), przybliżenie do `bbox`, „Narysuj swoje pole” jako opcja dodatkowa (`POST /api/analysis` z `geometry`), `Parcel.source = drawn`; różnice względem `places.proposal.ts`** – `contract-changes.md`, wpis A5c „Dla Mefju”.
- **B (A5b-2c): pozycja `woda` w werdykcie ma `level = info` (kropla #2F80C9); nie pokazywać `approximate_area.reason`** – `contract-changes.md`.
- **B (A6): pasek stref terenu, warstwy Teren i Spływ wody** – `contract-changes.md`, wpis A6 „Dla Mefju” (kolory, `kind`, dymki); w Terrain.tsx zmienić kolory stoku i płasko na #E8B931 i #5BB37F.
- **B: przykłady na ekranie startowym brać z `GET /api/demo/examples`** – w trybie offline i przy blokadzie ULDK backend zwraca tylko przykłady, które działają (dziś: Susza 2018, Mokry rok 2021); lista lokalna pokaże jury przykłady, które skończą się błędem.
- Wcześniejsze prośby A5 (pola rekomendacji, gleba, `previous_crop`, `/api/demo/examples`, raport PDF) – bez zmian.
