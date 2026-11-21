# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 16:21_

## Zrobione
- Wyszukiwanie działki ULDK: pełny identyfikator, „obręb numer”, punkt; `GET /api/parcel` (409 lista kandydatów, 404, 502 z nazwą źródła), timeout 10 s + jedna ponowna próba, cache 24 h.
- Prognoza pogody: `GET /api/forecast` (Open-Meteo), cache 30 min.
- Kontrakt `GET /api/analysis` w `schemas/analysis.py`; endpoint zwraca 501. Szkielety: `/api/layers`, `/api/reports`, `/api/infra-reports`.
- **A1 (scalone, PR #1):** historia pogody 10 lat – NASA POWER (+ zapasowo archiwum Open-Meteo), ET0 FAO-56 z metodą na każdy dzień, `analysis/water_balance.py` → sekcja `history` (bilans narastająco od 1 marca, pasmo 10 lat, opady miesięczne, braki/opóźnienie w ograniczeniach). Tymczasowy `GET /api/dev/weather-history`.
- **Kontrakt:** `History` rozszerzone o `balance_deviation_mm`, `balance_rank`, `longest_dry_spell`, `band_years` (uzgodnione z B) – wypełniane przez `build_history`.
- **A2 (gałąź `a/gleba`):** gleba – IUNG przez WCS (kody komórek 5 m), zapasowo GetFeatureInfo; klasy EGiB z KIEG; `analysis/soil.py` → `indicators.soil_capacity`, flaga „to nie jest grunt rolny”. Tymczasowy `GET /api/dev/soil`.
- **Kontrakt:** `History` + 4 pola (A1→A2); **nowa sekcja `soil`** (A3, uzgodnione z B) – wypełniana przez `analysis/soil.to_contract`.
- **A3 (gałąź `a/backend`):** `analysis/crops.py` – 15 upraw z parametrami FAO-56 (Kc, fazy, Zr, p, start sezonu PL); model wody w glebie FAO-56 w `analysis/water_balance.py` (TAW z WOD i głębokości korzeni, zapas na start z bilansu przed sezonem, Ks, spływ, przesiąkanie), woda w glebie % i mm, dni stresu w sezonie i w 10 poprzednich latach (`history.stress_days_by_year`), ryzyko 7 dni / „stres za X dni” (prognoza Open-Meteo dla dziś, scenariusz typowej pogody dla dat historycznych), nawadnianie (dawka i termin), poza sezonem bez wymyślania. Tymczasowy `GET /api/dev/water?parcel_id=&crop=&date=`.
- Testy: 108 bez sieci + 4 live. Live A3 (tabela w logu): 2018-07-15 zboża ozime – 52 dni stresu vs śr. 19,3 (201305), 48 vs 12,8 (061704); czas 0,01–5,5 s.

## W trakcie (gałąź)
- `a/backend` – jedna długa gałąź backendu (bez PR po zadaniu); merge do `main` przy kamieniu milowym „pełne /api/analysis”.

## Następne
1. **Pełne `/api/analysis`** (kamień milowy 1): ULDK + pogoda + prognoza + gleba + model równolegle, `status`/`score`, `causes`, `recommendations` (retencja → agrotechnika → nawadnianie, reguły YAML), `reliability`, `steps`; usunięcie `/api/dev/*`.
2. Teren z NMT (`sources/nmt.py`, `analysis/terrain.py`) – nadpisze parametry spływu w modelu wody.
3. Kalibracja do IUNG SMSR (porównanie dni stresu / KBW z komunikatami SMSR dla 2018 i 2021).

## Blokery / pytania do drugiej osoby
- B: czy w panelu „Woda w glebie” duża liczba to `soil_water_pct` czy `soil_water_mm` (kontrakt ma oba)?
- B: `stress_days_by_year` jest już wypełniane (bieżący rok + 10 poprzednich, `null` dla lat z niepełnymi danymi) – UI: `null` = „Brak danych”, nie 0. Przed sezonem uprawy lista jest pusta.
- B: poza sezonem uprawy `soil_water_*` i `risk_7d` mają `value: null` z notatką „Poza sezonem wegetacji tej uprawy…”.
