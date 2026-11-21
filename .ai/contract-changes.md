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

### 2026-11-21 · gałąź `a/backend` · A + B (uzgodnione – propozycja z A2)
**Nowa sekcja `soil: Soil` w `AnalysisResponse`** (`schemas/analysis.py` ↔ `types.ts`, przykład w `mocks/analysis.sample.json`):
`dominant_code`, `dominant_label`, `shares[] {code, label, share}` (kody IUNG), `agricultural_share` (kody 1–4), `wod_mm`, `classes` (EGiB, informacyjnie) + `classes_note` (powód braku), `non_agricultural`, `non_agricultural_reason` (`las` | `woda` | `zabudowa` | `drogi` | `gleby_organiczne`), `non_agricultural_note` (komunikat SPEC 15.1), `source_tag`.
WOD jako wskaźnik dalej w `indicators.soil_capacity`.
**Łamie zgodność:** tak dla odpowiedzi – `soil` jest wymagane (endpoint `/api/analysis` dziś zwraca 501, więc nikt go jeszcze nie konsumuje; mock zaktualizowany).

### 2026-11-21 · gałąź `a/backend` · A + B (uzgodnione co do zasady – zadanie A3b)
**Nowe sekcje w `AnalysisResponse`** (`schemas/analysis.py` ↔ `types.ts`, przykład w `mocks/analysis.sample.json`):
- `crop_season: CropSeason` – `phase` (`przed_siewem` | `wschody_jesienne` | `spoczynek_zimowy` | `poczatkowa` | `rozwoj` | `pelnia` | `dojrzewanie` | `po_zbiorze`), `phase_label`, `season_year`, `season_start`, `harvest`, `day_of_season`, `sensitive` (faza wrażliwa → stres i nawadnianie), `root_depth_m`;
- `soil_water: SoilWaterState` – `scope` (`strefa_korzeni` w fazach uprawy / `profil` ~1 m poza sezonem), `depth_m`, `description` (np. „poza sezonem – gleba odbudowuje zapas wody”), `rank` (ten sam dzień w 10 latach: w ilu latach było mniej wody, z ilu – typ `BalanceRank`), `last_season` (`SeasonSummary`: rok, dni stresu, średnia 10 lat);
- `irrigation: IrrigationPlan` – `status` (`zalecane` | `niepotrzebne` | `nieuzasadnione_w_fazie` | `brak_danych`), `message` („25 mm teraz, powtórz za ok. 5 dni”), `dose_mm` (≤ 35), `first_date`, `interval_days`, `total_7d_mm`, `doses_7d`, `source_tag`.
`indicators.soil_water_pct/mm` mają teraz wartość także poza sezonem (zakres opisuje `soil_water.scope`).
**Łamie zgodność:** tak dla odpowiedzi (3 nowe pola wymagane; `/api/analysis` dziś 501, mock zaktualizowany).
