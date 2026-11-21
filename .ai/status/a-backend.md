# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 16:10_

## Zrobione
- Wyszukiwanie działki ULDK: pełny identyfikator, „obręb numer”, punkt; `GET /api/parcel` (409 lista kandydatów, 404, 502 z nazwą źródła), timeout 10 s + jedna ponowna próba, cache 24 h.
- Prognoza pogody: `GET /api/forecast` (Open-Meteo), cache 30 min.
- Kontrakt `GET /api/analysis` w `schemas/analysis.py`; endpoint zwraca 501. Szkielety: `/api/layers`, `/api/reports`, `/api/infra-reports`.
- **A1 (scalone, PR #1):** historia pogody 10 lat – NASA POWER (+ zapasowo archiwum Open-Meteo), ET0 FAO-56 z metodą na każdy dzień, `analysis/water_balance.py` → sekcja `history` (bilans narastająco od 1 marca, pasmo 10 lat, opady miesięczne, braki/opóźnienie w ograniczeniach). Tymczasowy `GET /api/dev/weather-history`.
- **Kontrakt:** `History` rozszerzone o `balance_deviation_mm`, `balance_rank`, `longest_dry_spell`, `band_years` (uzgodnione z B) – wypełniane przez `build_history`.
- **A2 (gałąź `a/gleba`, PR do zrobienia):** gleba – IUNG przez **WCS GetCoverage text/plain** (surowe kody komórek 5 m w obrysie, ~0,3 s; skalowanie > 250 tys. komórek), zapasowo GetFeatureInfo w ≤ 16 punktach; klasy EGiB z KIEG (środek + 3 punkty, tylko nasza działka; brak klas = normalne); `analysis/soil.py` → `indicators.soil_capacity` (WOD, „pomiar”/IUNG), wpisy `reliability.sources` i ograniczenia, flaga „to nie jest grunt rolny” (kody 5, 11–14 > 50%); błąd IUNG → brak danych + obniżona pewność. Tymczasowy `GET /api/dev/soil?parcel_id=`.
- Testy: 83 bez sieci + 3 live. Live gleby: 6 działek testowych zgodnych z opisem (tabela w `.ai/test-parcels.md`), 0,5–0,8 s na działkę.

## W trakcie (gałąź)
- `a/gleba` – czeka na Pull Request / review.

## Następne
1. A3: model wody w glebie FAO-56 (Kc upraw w `analysis/crops.py`, pojemność z WOD × głębokość korzeni), % wody dostępnej, **dni stresu w każdym roku** (`history.stress_days_by_year`), „stres za X dni” z prognozy.
2. Pierwsza wersja `/api/analysis` z prawdziwymi `indicators` (soil_capacity, water_balance_season, soil_water_*), `history`, `reliability` (reszta `brak_danych`); usunięcie `/api/dev/*`.
3. Teren z NMT (`sources/nmt.py`, `analysis/terrain.py`).

## Blokery / pytania do drugiej osoby
- B: czy w panelu „Woda w glebie” duża liczba to `soil_water_pct` czy `soil_water_mm` (kontrakt ma oba)?
- B: `stress_days_by_year` będzie pustą listą do czasu A3 – UI powinien pokazać „Brak danych”, nie zera.
- **Propozycja zmiany kontraktu (do uzgodnienia z B, NIE wprowadzona):** kontrakt nie ma miejsca na szczegóły gleby, które już liczymy: udziały kategorii IUNG (kod, opis, udział), kategoria dominująca, klasy bonitacyjne EGiB, flaga „to nie jest grunt rolny” + powód. Dziś: WOD w `indicators.soil_capacity` (z klasami w `note`), reszta tylko w `/api/dev/soil`. Propozycja: sekcja `soil: { dominant_code, dominant_label, shares[], agricultural_share, classes[], not_agricultural, not_agricultural_reason }` w `AnalysisResponse`. SPEC 15.1 wymaga komunikatu „to nie jest grunt rolny” – bez tego pola UI nie ma skąd go wziąć.
