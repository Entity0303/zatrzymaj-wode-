# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 16:40_

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
- Testy: 125 bez sieci + 4 live. Live A3b – tabela w logu.

## W trakcie (gałąź)
- `a/backend` – jedna długa gałąź backendu (bez PR po zadaniu); merge do `main` przy kamieniu milowym „pełne /api/analysis”.

## Następne
1. **Pełne `/api/analysis`** (kamień milowy 1): ULDK + pogoda + prognoza + gleba + model równolegle, `status`/`score`, `causes`, `recommendations` (retencja → agrotechnika → nawadnianie, reguły YAML), `reliability`, `steps`; usunięcie `/api/dev/*`.
2. Teren z NMT (`sources/nmt.py`, `analysis/terrain.py`) – nadpisze parametry spływu w modelu wody.
3. **Kalibracja do IUNG SMSR** – model pokazuje dla kukurydzy 2018 mniej dni stresu niż średnia (wilgotna jesień 2017, mały popyt wody do VII); porównać z komunikatami SMSR 2018/2019/2021 przed użyciem w rekomendacjach.
4. Rekomendacje jesienno-zimowe (retencja, międzyplony) na podstawie `soil_water` poza sezonem.

## Blokery / pytania do drugiej osoby
- B: czy w panelu „Woda w glebie” duża liczba to `soil_water_pct` czy `soil_water_mm` (kontrakt ma oba)?
- B: `stress_days_by_year` jest już wypełniane (bieżący rok + 10 poprzednich, `null` dla lat z niepełnymi danymi) – UI: `null` = „Brak danych”, nie 0. Przed sezonem uprawy lista jest pusta.
- B: poza sezonem uprawy `soil_water_*` i `risk_7d` mają `value: null` z notatką „Poza sezonem wegetacji tej uprawy…”.
