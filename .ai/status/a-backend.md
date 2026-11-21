# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 19:30_

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
- Testy: 210 bez sieci (sprawdzone w kontenerze bez sieci) + 5 live. Smoke A5: 10/10 OK; po rozgrzewce przykłady 0,01–0,05 s, PDF 1,1–2,5 s.

## W trakcie (gałąź)
- `a/backend` – A5 gotowe; **merge do `main` robi właściciel repo po przejrzeniu** (B może już teraz `git merge origin/a/backend`).
- `integracja` (INT1, 2026-11-21 19:30) – `main` + `b/frontend` (B11) + `a/backend` (A5) połączone i sprawdzone (pytest 210, build, docker, curl); **nie scalone do `main`**. Decyzja B o języku = teraz **D47**.

## Następne
1. Teren z NMT (`sources/nmt.py`, `analysis/terrain.py`) + rowy BDOT10k – włączy reguły `requires: terrain / water_nearby` (oczko, zastawka, pas buforowy, mokradło) i mapkę miejsc w raporcie.
2. Sentinel-2 NDVI/NDMI – `crop_health`, `plant_moisture`; pewność może dojść do „wysokiej”.
3. Kalibracja do IUNG SMSR (kukurydza 2018) i weryfikacja nazw ekoschematów z instrukcją ARiMR 2026.
4. README (wymóg KOWR 4.2), `/api/layers`, sprzątanie `/api/dev/*`.

## Blokery / pytania do drugiej osoby
- **B: kontrakt A5** (`contract-changes.md`): `Recommendation` + `when`/`when_label`, `permit`/`permit_note`/`permit_url`, `warning`, `eco_scheme`; `Soil` + `texture`, `permeability`, `soil_map`, `texture_note`; `previous_crop` w zapytaniu i odpowiedzi; nowe `GET /api/demo/examples`, `GET /api/status`, `GET /api/report.pdf`.
- **B: panel filtruje po `in_panel`** (maks. 3); paszport pokazuje całą listę (maks. 5). Ostrzeżenie (`warning`) wyraźnie, formalności z linkiem, ekoschemat, „Kiedy: …”.
- **B: wybór przedplonu** (opcjonalny, z „Nie wiem”) obok uprawy → `previous_crop`.
- **B: przycisk „Pobierz raport”** → `/api/report.pdf` z tymi samymi parametrami co analiza.
- **B: link z kodu QR w raporcie:** `{PUBLIC_URL}/?dzialka=<id>&uprawa=<crop>&data=<RRRR-MM-DD>&przedplon=<crop>` – frontend powinien po wejściu z takim adresem od razu uruchomić analizę (dziś nie obsługuje parametrów).
- **B: przykłady demo** – np. 4 przyciski na ekranie startowym z `GET /api/demo/examples` (wynik zawsze przez normalne `/api/analysis`).
- B: `stress_days_by_year` – `null` = „Brak danych”, nie 0; `crop_health`/`plant_moisture` – `brak_danych` (satelita w przygotowaniu).
