# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 21:00_

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
- Testy: **256 bez sieci** (`docker run --network none`) + 5 live (A5b-1: 238). Ścieżka demo przy odciętej sieci (DEMO_OFFLINE, cache z wolumenu): wyszukanie 0,00 s, analiza 0,03–0,09 s, PDF 0,5–1,0 s.

## W trakcie (gałąź)
- `a/backend` – A5d gotowe (commit + push); **do `main` nie mergowane**.

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

## Następne
1. **A5b-2 „Co tu posiać?”** – symulacja 15 upraw na pogodzie z 10 lat → `suggestions` (dziś null).
2. Kalibracja progów statusu poza sezonem / bez uprawy (np. profil 61% w listopadzie = „Ryzyko 49”) i z IUNG SMSR.
3. Teren z NMT + rowy BDOT10k (u osoby C) – klienty mają korzystać z `cached_fetch` (D53); Sentinel-2.
4. README, `/api/layers`, sprzątanie `/api/dev/*`.

## Blokery / pytania do drugiej osoby
- **B (Mefju): panel działki pokazuje „Stan działki” od razu po wybraniu działki – `GET /api/analysis` bez `crop` → `field_state`, `soil.consistency`, rekomendacje retencyjne** (szczegóły i lista plików frontendu zmienionych przez A: `contract-changes.md`, wpis A5b-1, „Dla Mefju”).
- B: `IrrigationCard` – status `nie_praktykowane` (dziś etykieta „Nie stosuje się”); `status.scope_label` („poza sezonem”) przy karcie stanu; `storage.ts` – czy zapamiętywać analizę bez uprawy.
- B: obraz kontenera frontendu nie ma `@fontsource-variable/fraunces` – `docker compose build frontend`.
- **B: przykłady na ekranie startowym brać z `GET /api/demo/examples`** – w trybie offline i przy blokadzie ULDK backend zwraca tylko przykłady, które działają (dziś: Susza 2018, Mokry rok 2021); lista lokalna pokaże jury przykłady, które skończą się błędem.
- Wcześniejsze prośby A5 (pola rekomendacji, gleba, `previous_crop`, `/api/demo/examples`, raport PDF) – bez zmian.
