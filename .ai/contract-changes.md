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

### 2026-11-21 · gałąź `a/backend` · A4 (uzgodnione co do zasady)
**`Recommendation` + `priority: int` i `in_panel: bool`** (`schemas/analysis.py` ↔ `types.ts`, mock).
Silnik reguł zwraca pełną listę (retencja → agrotechnika → nawadnianie, w grupie od najważniejszej); `in_panel = true` ma maks. 3 rekomendacje – najważniejsza z każdej grupy (SPEC 6.5). Paszport pokazuje całą listę. **Dla B:** panel powinien filtrować po `in_panel`, a nie brać pierwszych 3.
**Łamie zgodność:** nie (pola z wartościami domyślnymi).

### 2026-11-21 · gałąź `a/backend` · A4 – przykład (bez zmiany kontraktu)
`frontend/src/mocks/analysis.sample.json` zastąpiony **zapisem prawdziwej odpowiedzi** `/api/analysis` (201305_2.0038.6/1, zboża ozime, 2018-06-10: status „Susza”, plan nawadniania, 101 dni historii). Dopisek w `parcel.zrodlo.uwagi`; UI dalej pokazuje „DANE PRZYKŁADOWE”.

### 2026-11-21 · gałąź `a/backend` · A5 – konsultacja z mentorem, gleba dla rolnika, demo i status
**Zmiana kontraktu (obie strony: `backend/app/schemas/` + `frontend/src/api/types.ts`, mock = prawdziwa odpowiedź):**
- `GET /api/analysis` – nowy opcjonalny parametr **`previous_crop`** (15 upraw albo `nie_wiem`); w odpowiedzi `previous_crop`.
- `Recommendation` – nowe pola: **`when`** (`teraz` | `po_zbiorze` | `przed_sezonem`) + `when_label`, **`permit`** (`none` | `maybe` | `required`) + `permit_note` + `permit_url` (Wody Polskie), **`warning`** (przy niskiej pewności: „Obarczone dużym ryzykiem błędu…”), **`eco_scheme`** (`EcoScheme`: name, practice, code, note – bez kwot dopłat).
- Lista rekomendacji: **maks. 5** (paszport), `in_panel` – maks. 3 (po jednej z grupy). Rekomendacja z `warning` nigdy nie jest pierwsza w grupie.
- `Soil` – nowe pola: **`texture`** (`SoilTexture`: piasek/pył/ił %, węgiel org. %, klasa uziarnienia PL, kod USDA, głębokość), **`permeability`** (`SoilPermeability`: Ksat mm/h, opis, `rain_retention` `ucieka` | `zatrzymuje` | `splywa`, zdanie dla rolnika), **`soil_map`** (`SoilMapInfo`: kompleks przydatności, gatunek gleby, głębsze warstwy, typ, rok mapy), `texture_note` (powód braku).
- Nowe endpointy i typy: **`GET /api/demo/examples`** → `DemoExample[]`; **`GET /api/status`** → `StatusResponse` (źródła: ok, czas, cache; rozgrzewka przykładów); **`GET /api/report.pdf?parcel_id=&crop=&date=&previous_crop=`** → PDF.
**Dla B:** panel filtruje po `in_panel`; przy każdej rekomendacji pokazać `when_label`, formalności (`permit_note` + link), `warning` (wyraźnie) i ekoschemat; w sekcji gleby – uziarnienie, przepuszczalność i „woda z ulewy”; wybór przedplonu (opcjonalny, „Nie wiem”) obok wyboru uprawy; przycisk „Pobierz raport” → `/api/report.pdf` z tymi samymi parametrami.

### 2026-11-21 · gałąź `a/backend` · A5b-1 – stan działki bez uprawy, nawadnianie wg praktyki, zgodność gleby
**DLA FRONTENDU (B): panel działki ma pokazywać „Stan działki” od razu po wybraniu działki, bez wymagania uprawy.** Wywołaj `GET /api/analysis?parcel_id=&date=` (bez `crop`) i pokaż `field_state` (status, woda w profilu, przebieg od 1 XI z pasmem 10 lat, bilans 30 dni) + `soil` (z `consistency`) + rekomendacje (same retencyjne). Wybór uprawy = doprecyzowanie (pełna analiza jak dziś). `field_state` jest też w odpowiedzi z uprawą – sekcja (1) panelu może zostać.
**Zmiany (obie strony: `backend/app/schemas/analysis.py` + `frontend/src/api/types.ts`; przykłady w `frontend/src/mocks/`):**
- `GET /api/analysis` i `GET /api/report.pdf` – **`crop` opcjonalne** (bez niego: analiza „Stan działki”; nieznana uprawa nadal 422). PDF bez uprawy – „Stan wodny działki” (`stan-wodny-dzialki-….pdf`).
- `AnalysisResponse.crop: CropId | null`, **`crop_season: CropSeason | null`**, **`irrigation: IrrigationPlan | null`** – null bez uprawy (dla odpowiedzi z uprawą bez zmian).
- Nowe: **`field_state: FieldState | null`** – `status` (OverallStatus), `cover`, `soil_water_pct`, `soil_water_mm`, `soil_water` (opis, ranking 10 lat), `series_start`, `series[]` (%, dzień po dniu), `series_band[]` (min/max/średnia 10 lat), `balance_30d` (Indicator), `balance_30d_rank`, `source_tag`; null dla gruntu nierolnego.
- Nowe: **`suggestions: null`** – zarezerwowane na ranking „Co tu posiać?” (A5b-2), typ zostanie określony.
- `OverallStatus` + **`scope`** (`sezon` | `poza_sezonem` | `bez_uprawy`) i **`scope_label`** („w sezonie”, „poza sezonem”, „stan wody na działce”).
- `Soil` + **`consistency: SoilConsistency | null`** {`status` ok|conflict, `note`, `basis`, `category_used`, `by_source[]` (`SoilCategoryVote`: source, source_label, category, description)}. Przy konflikcie `soil.wod_mm` = WOD użyte w obliczeniach (np. z mapy glebowo-rolniczej), sekcja IUNG (`dominant_code`, `shares`) bez zmian.
- `IrrigationStatus` + **`nie_praktykowane`** (zboża, rzepak, strączkowe – bez dawek, komunikat „Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie”); `IrrigationPlan` + **`practice`** (`not_practiced` | `optional` | `common`).
- Dane (bez zmiany typu): `EcoScheme.code` tylko E_MPW, E_USU, E_WSG, E_PN, E_MIOD, E_EKSTUZ; `risk_7d.note` poza fazą wrażliwą: „<faza> – poza fazą wrażliwą na brak wody”.
- Przykłady: `mocks/analysis.sample.json` (Susza 2018 – nowa prawdziwa odpowiedź) i **nowy `mocks/analysis.no-crop.sample.json`** (ta sama działka bez uprawy) – oba walidowane w `test_contract.py`.
**Dla Mefju – pliki w `frontend/`, które zmieniła osoba A (za zgodą właściciela repo; tylko typy i zabezpieczenia null, bez zmian wyglądu – właściwy widok „Stan działki” to Twoje zadanie):**
- `src/api/types.ts` – kontrakt: `StatusScope` + `OverallStatus.scope/scope_label`; `IrrigationStatus` + `'nie_praktykowane'`, nowy `IrrigationPractice` + `IrrigationPlan.practice`; `Soil.consistency` + typy `SoilSourceKey`, `SoilCategoryVote`, `SoilConsistency`; nowy `FieldState`; `AnalysisResponse.crop: CropId | null`, `crop_season: CropSeason | null`, `irrigation: IrrigationPlan | null`, nowe `field_state?`, `suggestions?: null`.
- `src/mocks/analysis.sample.json` – nowa prawdziwa odpowiedź „Susza 2018” (z `field_state`, `soil.consistency`, `irrigation.status = nie_praktykowane`); `src/mocks/analysis.no-crop.sample.json` – NOWY, ta sama działka bez uprawy (2026-11-21). `useMockAnalysis.ts` bez zmian (nadal czyta tylko pierwszy plik).
- `src/features/parcel-panel/IrrigationCard.tsx` – wpis `nie_praktykowane: { label: 'Nie stosuje się', … }` w mapie `STATUS` (wymagany przez `Record<IrrigationStatus, …>`).
- `src/features/parcel-panel/ParcelPanel.tsx` – `CropSeasonCard` tylko gdy `analysis.crop_season`; `IrrigationCard` tylko gdy `analysis?.irrigation`.
- `src/features/passport/SectionD.tsx` – `IrrigationCard` tylko gdy `analysis.irrigation`.
- `src/layout/cards/AlertsCard.tsx` – `analysis.irrigation?.status === 'zalecane'`.
- `src/lib/storage.ts` – `rememberAnalysis`: analiza bez uprawy nie trafia do historii (`if (!a.crop) return`), bo `AnalysisRecord.crop` jest wymagane – do decyzji B, czy zapamiętywać „Stan działki”.
- `src/lib/i18n.en.ts` – nowy wpis `'Nie stosuje się': 'Not practised'`.
Weryfikacja: `npm run build` (tsc + vite) przechodzi – w kontenerze z aktualnym `npm install` (lokalne `node_modules` i obraz kontenera frontendu nie mają `@fontsource-variable/fraunces` z `package.json` – trzeba przebudować obraz: `docker compose build frontend`).
**Łamie zgodność:** dla TypeScript tak (pola mogą być null, nowa wartość enuma) – poprawione minimalnie, build przechodzi; dla odpowiedzi z uprawą – nie (pola dodane, opcjonalne).

### 2026-11-21 · gałąź `a/backend` · A6 – teren i spływ wody z NMT, warstwy Teren i Spływ wody
**Zmiany (addytywne; `backend/app/schemas/analysis.py`, `schemas/layers.py` + `frontend/src/api/types.ts`; przykłady w `frontend/src/mocks/`):**
- `AnalysisResponse` + **`terrain: Terrain | null`** i **`terrain_note: string | null`** (powód braku, np. „NMT GUGiK: usługa chwilowo ogranicza ruch”) – z uprawą i bez uprawy.
- `Terrain`: `zones[4]` (`TerrainZone`: key `sucha_gorka|stok|plasko|mokry_dolek`, label, share_pct, color, rating `dobrze|uwaga|zle|null`, sentence), `zone_share_pct`, `soil_group` + `soil_group_label`, **`summary`** (2–3 zdania), `relief_m`, `elev_min_m/max`, `slope_mean_pct`, `slope_max_pct`, `main_flow_direction(_short)`, `main_flow_azimuth_deg`, `outlets[]` (`TerrainOutlet`: direction, share_of_parcel_pct, location [lon,lat]), `inflow_from_outside_m2/ratio`, `depressions_count`, `depressions_volume_m3`, `largest_depression` (`TerrainDepression`), `details` (`TerrainDetails` – „dla dociekliwych”: siatka, TWI, metoda), `confidence`, `limitations`, `source_tag`.
- **`GET /api/layers/teren`** i **`GET /api/layers/splyw`** – działają (`LayerResponse`, format bez zmian; `features` = GeoJSON EPSG:4326). Pozostałe warstwy – nadal 501.
- Rekomendacje z terenu (nowe `rule_id`): `retencja.oczko_w_zaglebieniu`, `retencja.oczko_opcja` („Do rozważenia…”, z ostrzeżeniem), `retencja.zastawka_na_rowie`, `retencja.pas_buforowy_na_stoku`, `retencja.mokradlo_srodpolne`; własne `permit_note` dla oczka i zastawki.
- Przykłady: `mocks/analysis.sample.json` i `analysis.no-crop.sample.json` – z sekcją `terrain` (201305, teren z zapisanego wyniku NMT 21.11); **nowe** `mocks/layers.teren.sample.json`, `mocks/layers.splyw.sample.json` (walidowane w `test_contract.py`).

**Dla Mefju – jak to pokazać (frontendu A nie zmieniał w A6):**
- **Pasek stref** (panel „Stan działki” i paszport): jeden poziomy pasek z `terrain.zones` w podanej kolejności (górka → stok → płasko → dołek), szerokość = `share_pct`, kolor = `color` (górka **#8B6B4A**, stok **#E8B931**, płasko **#5BB37F**, dołek **#2F80C9**), % na segmencie, gdy się mieści. Pod paskiem `terrain.summary`, a niżej zdania `zones[].sentence` (tylko niepuste) z kropką/odznaką oceny `rating` (dobrze – zielony, uwaga – żółty, źle – czerwony). Szczegóły (`details`, TWI) – tylko w rozwijanym „Dla dociekliwych”. `terrain == null` → `terrain_note` szarym tekstem.
- **Warstwa „Teren”** (`/api/layers/teren`): poligony stref, `properties`: `kind` = `gorka|stok|plasko|dolek` (Twoje klucze z Terrain.tsx), `zone`, **`color`** (jak wyżej – proszę zmienić w legendzie Terrain.tsx kolory stoku i płasko na #E8B931 i #5BB37F, żeby mapa = pasek), `share_pct`, `label` (dymek „stok – woda ucieka · 56% działki”). `value_range` = wysokość min–max (m).
- **Warstwa „Spływ wody”** (`/api/layers/splyw`): `kind` = `flow` (linie – ścieżki spływu, niebieskie #2F7FC1), `outflow` (punkty – „tu woda ucieka”, czerwone #E5675C, `share_pct`, `direction`), `retencja` (punkt – proponowane miejsce na oczko, #2E5B3F), `pas_buforowy` (linia), `spot` (poligon – zagłębienie bez odpływu, #2F80C9). Każdy obiekt ma `color` i `label` – LayerData.tsx już je czyta. Legenda: „Kierunek spływu”, „Tu woda ucieka”, „Tu zbiera się woda”, „Miejsce na oczko”.
- Rekomendacja `retencja.oczko_opcja` ma `warning` i niski priorytet – nie powinna trafiać do panelu jako pierwsza (backend i tak daje `in_panel = false`).
**Łamie zgodność:** nie (pola dodane, opcjonalne; warstwy – dotąd 501).

### 2026-11-21 · gałąź `a/backend` · A5b-2a – ranking „Co tu posiać?”, historia upraw, powierzchnia
**Zmiany (addytywne; `backend/app/schemas/analysis.py` + `frontend/src/api/types.ts`; przykłady w `frontend/src/mocks/`):**
- `GET /api/analysis` i `GET /api/report.pdf` – nowe parametry: **`crop_history`** (1–3 uprawy po przecinku, pierwsza = rok temu; identyfikatory jak `RankingCropId` + 15 upraw `CropId` + `nie_wiem`; np. `crop_history=pszenica_ozima,rzepak`) i **`cultivated_area_ha`** (liczba > 0). Błędne → 422 z komunikatem.
- `AnalysisResponse` + **`suggestions: CropSuggestions | null`** (było zawsze null), **`crop_history: string[]`**, **`cultivated_area_ha: number | null`**. Ranking jest w odpowiedzi z uprawą i bez uprawy; null dla gruntu nierolnego albo gdy pogody jest mniej niż 5 pełnych sezonów.
- `CropSuggestions`: `seasons[]`, `groups[]` (`SuggestionGroup`: key `polowe` | `wieloletnie`, label, `items[]`), `area` (`CultivatedArea`: value_ha, estimated, note), `crop_history`, `rotation_hint`, `note`, `limitations`, `compute_ms`, `source_tag`.
- `CropSuggestion`: `crop_id` (`RankingCropId` – 17 upraw), `label`, `group_id`, **`category`** (`polecane` | `mozliwe` | `odradzane`) + `category_label`, `rank`, `score`, **`reason`** (jedno zdanie), **`yield_typical_t_ha`**, **`yield_weak_t_ha`** + **`weak_year`**, `yield_potential_t_ha`, `gus_mean_t_ha`, `relative_yield_median/weak`, **`drought_risk_years`** / `years_simulated`, **`total_typical_t`**, **`total_weak_t`**, `price` (null – na później), `soil_suitability` + label, `rotation` (`RotationCheck`: status `ok|plus|ostrzezenie|naruszenie|brak_historii`, notes[]), `irrigation_practice`, `drought_sensitivity`, `confidence` + `confidence_note`, `notes[]`, `yields_by_year[]` (`YearYield`: year, relative, yield_t_ha, water_deficit_mm), `source_tags[]`.
- `StatusScope` + **`zimowanie`** (`scope_label` „w polu – zimowanie”) – oziminy i uprawy wieloletnie zimą; `IrrigationPlan` przy `practice = optional` (kukurydza): bez dawek, `status = nie_praktykowane` albo `niepotrzebne`, treść w `message`.
- Przykłady: `analysis.sample.json`, `analysis.no-crop.sample.json` (z rankingiem), **nowy `analysis.no-crop-history.sample.json`** (historia: rok temu pszenica ozima, 2 lata temu rzepak; powierzchnia 0,5 ha) – wszystkie walidowane w `test_contract.py`.

**Dla Mefju – jak pokazać (frontendu A nie zmieniał):**
- **Ranking „Co tu posiać?”** od razu po wybraniu działki (z `GET /api/analysis` bez `crop`): dwie listy z `suggestions.groups` – „uprawy polowe” i osobno „uprawy wieloletnie”. Kolejność pozycji jak w odpowiedzi (już posortowane). Każda pozycja:
  - znak kategorii z `category`: ✅ polecane (zielony), 🟡 możliwe (żółty), ❌ odradzane (czerwony) + `label`,
  - plon: „typowo **{yield_typical_t_ha} t/ha** ({total_typical_t} t z {area.value_ha} ha)”, słaby rok: „w słabym roku ({weak_year}): {yield_weak_t_ha} t/ha ({total_weak_t} t)”,
  - ryzyko: „strata ponad 20% plonu w **{drought_risk_years} na {years_simulated} lat**”,
  - jedno zdanie `reason` pod spodem; `rotation.notes` (jeśli są) jako dopisek z ikoną: plus = zielony, ostrzezenie = żółty, naruszenie = czerwony,
  - `confidence = ograniczona` → mały dopisek „szacunek” z `confidence_note` w dymku; `notes` (np. „plon zielonej masy”) drobnym tekstem.
  - Kliknięcie pozycji z `crop_id` będącym jedną z 15 upraw `CropId` może ustawić uprawę do pełnej analizy; gatunki (pszenica_ozima, zyto, pszenzyto_ozime, jeczmien_ozimy → `zboza_ozime`; jeczmien_jary, owies → `zboza_jare`; lubin → `straczkowe`) – przez `group_id`.
  - Pod listą: `suggestions.note` („Plony bez nawadniania…”) i rozwijane `limitations`.
- **Historia pola:** 3 pola wyboru „rok temu / 2 lata temu / 3 lata temu” (opcjonalne, z „nie wiem”), lista = 22 uprawy (17 z rankingu + zboża ozime/jare ogólnie, rzepak jesień, chmiel, tytoń) – etykiety są w `label` pozycji rankingu. Wysyłaj `crop_history=a,b,c` (puste lata jako `nie_wiem`). Gdy `suggestions.rotation_hint` nie jest null – pokaż go nad listą jako zachętę.
- **Powierzchnia uprawy:** pole liczbowe (ha) wypełnione `suggestions.area.value_ha`; gdy `area.estimated` – dopisek z `area.note` („oszacowanie…”). Zmiana → ponowne zapytanie z `cultivated_area_ha`.
- **Status:** `status.scope_label` może być teraz „w polu – zimowanie”. **Nawadnianie kukurydzy:** nie ma dawek – pokaż samo `irrigation.message`.
**Łamie zgodność:** nie (pola dodane / opcjonalne, nowa wartość `StatusScope` – nigdzie niemapowana w `Record`; build przechodzi).
