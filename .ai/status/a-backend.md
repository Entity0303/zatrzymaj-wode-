# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 20:30_

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
- Testy: **238 bez sieci** (`docker run --network none`) + 5 live (A5: 210). Smoke A5b-1 (obrys 201305 z zapisu ULDK, reszta na żywo): 5/5 przypadków 201305 OK; analiza 0,02–6,2 s, PDF 1,2–2,8 s.

## W trakcie (gałąź)
- `a/backend` – A5b-1 gotowe (commit + push); **do `main` nie mergowane**.

## Do zrobienia NA ŻYWO (ULDK GUGiK ograniczał ruch – 302 przez całą sesję A5b-1)
1. `scripts/smoke.py` na pełnych przykładach – przypadki z ULDK: „Kukurydza – stan dziś” (061704), „To nie jest pole” (143203) i 5 działek z `test-parcels.md` (dziś 502).
2. Ponownie wygenerować `reports/examples/kukurydza-dzis.pdf` i `to-nie-jest-pole.pdf` – **są jeszcze z A5** (stara logika: m.in. „Ryzyko 39” poza sezonem). Nowe: `susza-2018.pdf`, `mokry-rok-2021.pdf`, `stan-dzialki-bez-uprawy.pdf`.
3. Kontrola „Kukurydza dziś” na właściwej działce 061704 (zastępczo na 201305: „poza sezonem”, 49 pkt – bez kar za stres kukurydzy).
4. Zbadać zgodność gleby na 061704 (IUNG IV/III, mapa – pył zwykły na piasku) i pozostałych działkach testowych.

## Następne
1. **A5b-2 „Co tu posiać?”** – symulacja 15 upraw na pogodzie z 10 lat → `suggestions` (dziś null).
2. Kalibracja progów statusu poza sezonem / bez uprawy (np. profil 61% w listopadzie = „Ryzyko 49”) i z IUNG SMSR.
3. Teren z NMT + rowy BDOT10k (u osoby C – patrz pamięć), Sentinel-2.
4. README, `/api/layers`, sprzątanie `/api/dev/*`, trwały cache (SQLite) – reloady czyszczą cache w pamięci.

## Blokery / pytania do drugiej osoby
- **B (Mefju): panel działki pokazuje „Stan działki” od razu po wybraniu działki – `GET /api/analysis` bez `crop` → `field_state`, `soil.consistency`, rekomendacje retencyjne** (szczegóły i lista plików frontendu zmienionych przez A: `contract-changes.md`, wpis A5b-1, „Dla Mefju”).
- B: `IrrigationCard` – status `nie_praktykowane` (dziś etykieta „Nie stosuje się”); `status.scope_label` („poza sezonem”) przy karcie stanu; `storage.ts` – czy zapamiętywać analizę bez uprawy.
- B: obraz kontenera frontendu nie ma `@fontsource-variable/fraunces` – `docker compose build frontend`.
- Wcześniejsze prośby A5 (pola rekomendacji, gleba, `previous_crop`, `/api/demo/examples`, raport PDF) – bez zmian.
