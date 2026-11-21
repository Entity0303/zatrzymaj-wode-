# Historia zmian kontraktu API

Kontrakt = `backend/app/schemas/` + `frontend/src/api/types.ts` (+ przykład `frontend/src/mocks/analysis.sample.json`).
Zmiana tylko po uzgodnieniu A ↔ B, w obu plikach naraz, `backend/tests/test_contract.py` musi przechodzić.
Wpis: data · commit/gałąź · kto uzgodnił · co się zmieniło · czy zmiana łamie zgodność.

---

### 2026-11-21 · commit f31e94c · A + B (przygotowanie repo)
**Utworzenie schematu `GET /api/analysis?parcel_id=&crop=&date=`** (`schemas/analysis.py` ↔ `AnalysisResponse` w `types.ts`):
`parcel`, `crop` (15 upraw IUNG), `analysis_date`, `historical`, `generated_at`, `status` (ok/warn/risk/danger/no_data + score, headline, summary), `indicators` (soil_water_pct, soil_water_mm, risk_7d, crop_health, plant_moisture, water_balance_season, soil_capacity – każdy z `value`, `unit`, `source_tag`), `history` (bilans narastająco, pasmo 10 lat, dni stresu w latach, opady miesięczne), `causes`, `recommendations` (retencja/agrotechnika/nawadnianie, why, inputs, confidence, location), `reliability`, `steps`.
Endpoint zwraca 501 „w budowie”.

Jednocześnie spisane jako kontrakt istniejące odpowiedzi: `GET /api/parcel` (`schemas/parcel.py`: Parcel, ParcelCandidates przy 409, ErrorDetail przy 404/502) i `GET /api/forecast` (`schemas/weather.py`) – bez zmiany formatu. Szkielety: `schemas/layers.py`, `schemas/reports.py` (raport PDF, zgłoszenia).
**Łamie zgodność:** nie (nowy endpoint; istniejące bez zmian).

### 2026-11-21 · gałąź `a/gleba` · A + B (uzgodnione – propozycja z A1)
**Rozszerzenie `History` o 4 pola** (`schemas/analysis.py` ↔ `types.ts`, przykład w `mocks/analysis.sample.json`):
- `balance_deviation_mm: float | null` – bieżący bilans − średnia z lat porównawczych (mm),
- `balance_rank: { lower_years, of_years } | null` – w ilu latach bilans był niższy niż teraz i z ilu lat,
- `longest_dry_spell: { days, end_date } | null` – najdłuższy okres bez opadu (< 1 mm) w sezonie,
- `band_years: int[]` – lata użyte w paśmie porównawczym (lata z niepełnymi danymi pominięte).
Wszystkie opcjonalne (brak danych = `null` / pusta lista). Liczone w `analysis/water_balance.py` od A1, wcześniej tylko w tekście `summary`.
**Łamie zgodność:** nie (pola dodane, opcjonalne).
