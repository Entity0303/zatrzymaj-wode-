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

### 2026-11-21 · gałąź `a/backend` · A5b-2b – werdykt działki, obszar przybliżony, wieloletnie, „informacyjne”
**Zmiany (addytywne; `backend/app/schemas/analysis.py` + `frontend/src/api/types.ts`; przykłady w `frontend/src/mocks/`):**
- `AnalysisResponse` + **`verdict: Verdict | null`** (z uprawą i bez; null – grunt nierolny / brak WOD) i **`approximate_area: ApproximateArea | null`**.
- `Verdict`: `headline` (jedno zdanie), `level` (`ok|warn|bad`), `statements[]` (4–6 × `VerdictStatement`: `kind` `gleba|opady|teren|uprawy|woda|uprawa_wybrana`, `level`, `text`, `numbers{}`), `crops_good[]` / `crops_bad[]` (`VerdictCrop`: `crop_id` = `RankingCropId`, `label`, `reason` – przy ❌ jeden powód), `note`.
- `ApproximateArea`: `center` [lon, lat], `side_m` (100), `area_ha` (1), `reason`, `note` („Obszar przybliżony – brak granic działki z ULDK…”), `voivodeship_note`.
- `GET /api/analysis` i `GET /api/report.pdf`: **`parcel_id` opcjonalne, nowe `lon`, `lat`** (punkt na mapie). Bez żadnego z nich → 422; punkt poza Polską → 404.
- `IrrigationStatus` + **`informacyjne`** (kukurydza / tytoń z niedoborem – bez dawek, treść w `message`).
- `CropSuggestions` + **`perennials: PerennialSection | null`** (`label` „Uprawy wieloletnie – inwestycja na lata”, `note`, `items[]` `PerennialSuggestion` – plony, ryzyko, `note` z „Wymaga osobnej analizy opłacalności”); **`groups` ma teraz tylko „polowe”**.
- `Terrain.soil_group` + wartości `lekka|srednia|ciezka|organiczna` (`zwiezla` zostaje w typie dla zgodności, backend już jej nie zwraca).
- Przykłady: `analysis.sample.json` i `analysis.no-crop.sample.json` z werdyktem dobrej działki (201305); **nowy `verdict.weak.sample.json`** – werdykt słabej działki (piasek, Puszcza Notecka, obszar przybliżony). Walidowane w `test_contract.py`.

**Dla Mefju – jak pokazać:**
- **Karta „Werdykt” na samej górze panelu działki** (przed stanem wody, od razu po wybraniu działki): duży `verdict.headline` z lewym paskiem w kolorze `verdict.level`; pod spodem `statements` w podanej kolejności – okrągła ikona w kolorze `level` (ok **#5BB37F** ✓, warn **#E8B931** !, bad **#C8453B** ✕), mała etykieta z `kind` (Gleba / Opady / Teren / Co siać / Woda / Wybrana uprawa) i `text` dużą czcionką. Niżej dwa rzędy chipów: „Siej” – `crops_good` (zielone ✓), „Nie siej” – `crops_bad` (czerwone ✕, `reason` w dymku albo jedną linią pod spodem). Gdy `crops_bad` puste – zdanie jest już w statements („…żadna z popularnych upraw nie jest odradzana”). `note` drobnym szarym tekstem.
- **Pasek stref terenu** w karcie Werdykt pod zdaniem „Teren” (te same dane i kolory co w A6: `terrain.zones`, szerokość = `share_pct`).
- **Obszar przybliżony:** gdy `approximate_area != null` – żółty pasek nad werdyktem z `approximate_area.note` (+ `reason` mniejszym), na mapie kwadrat zamiast obrysu działki (geometria jak zwykle w `parcel`), zamiast numeru działki „Obszar przybliżony (lat, lon)”. Klik na mapie, gdy wyszukanie działki zwróci 502 z ULDK → `GET /api/analysis?lon=&lat=`.
- **Nawadnianie:** `irrigation.status = informacyjne` – etykieta „Informacja” (dodana w `IrrigationCard.tsx`), pokaż samo `message`.
- **Ranking:** uprawy wieloletnie z `suggestions.perennials` – osobna, zwinięta sekcja pod rankingiem, mniejszym drukiem, bez ✅/🟡/❌.
- **Pliki frontendu zmienione przez A (minimalnie, żeby typy się zgadzały):** `src/api/types.ts` (typy powyżej), `src/features/parcel-panel/IrrigationCard.tsx` (`informacyjne: { label: 'Informacja', cls: 'bg-surface-2 text-text-muted' }`), `src/lib/i18n.en.ts` (`'Informacja': 'Information'`), mocki (`analysis.sample.json`, `analysis.no-crop.sample.json`, nowy `verdict.weak.sample.json`).
Weryfikacja: `tsc -b` przechodzi; `vite build` – lokalnie i w kontenerze brak paczki `@fontsource-variable/fraunces` z `package.json` (trzeba `npm install` / `docker compose build frontend`).
**Łamie zgodność:** nie (pola dodane / opcjonalne; nowa wartość `IrrigationStatus` obsłużona w `Record`; `groups` bez „wieloletnie” – frontend dostaje je w `perennials`).

### 2026-11-22 · gałąź `a/backend` · A5b-2c – pozycja „woda” w werdykcie = `info`
**Zmiana (addytywna; `schemas/analysis.py` + `types.ts` + mocki):** `VerdictStatement.level` ma teraz wartości `ok | warn | bad | info` (`VerdictStatementLevel`); `Verdict.level` (całość) zostaje `ok | warn | bad`. Pozycja `kind = woda` zawsze ma `level = "info"` – to lista działań, nie ocena. Zmienione mocki: `analysis.sample.json`, `analysis.no-crop.sample.json`, `verdict.weak.sample.json`; `approximate_area.note` bez „ULDK” („Obszar przybliżony – brak dokładnych granic działki. Analiza dla kwadratu 1 ha wokół wskazanego punktu.”).
**Dla Mefju:** w karcie „Werdykt” pozycja `woda` – ikona kropli w kolorze **#2F80C9** (zamiast ✓ / ! / ✕); `Record<VerdictLevel,…>` użyte dla `statements[].level` trzeba rozszerzyć o `info`. `approximate_area.reason` zawiera komunikat techniczny (np. „ponowna próba za X s”) – **nie pokazywać w UI**, wystarczy `note`.
**Łamie zgodność:** nie (nowa wartość enuma; frontend jeszcze nie renderuje werdyktu).

### 2026-11-21 · gałąź `a/backend` · A5c – wyszukiwanie `GET /api/search`, działka z kliknięcia, własny obrys pola
**Zmiany (addytywne; `backend/app/schemas/search.py`, `schemas/analysis.py`, `schemas/parcel.py` + `frontend/src/api/types.ts`; przykłady w `frontend/src/mocks/`):**
- **`GET /api/search?q=`** → `SearchResponse` { `query`, `interpreted_as` (`parcel_id|obreb_numer|name|empty|unrecognized`), `results[]` (maks. 10), `total`, `truncated`, `hint`, `notices[]`, `attribution` }. `SearchResult`: `kind` (`parcel` | `place`), `id`, `label` („Tczów, gm. Tczów, pow. zwoleński, mazowieckie”), `name`, `lon`, `lat`, `parcel_id` (tylko parcel), `type` (`miejscowosc|gmina|obreb`, tylko place), `type_label` („wieś”, „miasto”), `gmina`, `powiat`, `wojewodztwo`, `bbox` [lon_min, lat_min, lon_max, lat_max], `bbox_approx`, `area_ha` (tylko parcel), `source`. **Brak wyników = 200 + pusta lista + `hint`** (nie 404); awarie źródeł tylko w `notices`.
- **`GET /api/parcel?lon=&lat=`** – bez zmian formatu (istniało); zwraca teraz też `source` i `name`.
- **`Parcel`** + `source` (`uldk|drawn|approximate`, domyślnie `uldk`) i `name` (np. „Pole narysowane przez rolnika”, null dla działki ULDK).
- **`POST /api/analysis`** i **`POST /api/report.pdf`** – treść `AnalysisRequest` (dokładnie jedno z: `parcel_id`, `lon`+`lat`, `geometry` = GeoJSON Polygon WGS84; plus `crop`, `date`, `previous_crop`, `crop_history`, `cultivated_area_ha`). Odpowiedź jak GET; dla `geometry`: `parcel.source = "drawn"`, `parcel.name = "Pole narysowane przez rolnika"`, `parcel.id = narysowane_…`, powierzchnia z kształtu, gmina / powiat / województwo z działki ULDK w środku pola albo geokodera (`parcel.zrodlo.uwagi`). Błędny obrys → 422 z `detail.message` po polsku („Pole jest za małe (0,028 ha) – najmniejsze obsługiwane to 0,05 ha…”, „…za duże…”, „Obrys leży poza Polską…”, „Obrys przecina sam siebie…”, „…odwróconą kolejność – w GeoJSON najpierw długość (lon)…”).
- Przykłady: **`mocks/search.sample.json`** (klucze `parcel_id`, `obreb_numer`, `name`, `empty` – prawdziwe odpowiedzi), **`mocks/drawn.sample.json`** (`request` + `parcel` pola narysowanego). Walidowane w `test_a5c.py`.

**Różnice względem propozycji B (`api/places.proposal.ts`, `mocks/places.sample.json`):**
- Endpoint **`/api/search`** (jedno pole wyszukiwania, backend sam rozpoznaje format), nie `/api/places`; **nie trzeba** reguły `isPlaceQuery` (bez cyfr = miejsce) – wysyłaj całe `q`, odpowiedź mówi `interpreted_as`. Dla działki (id / „obręb numer”) wyniki `kind = parcel` z `parcel_id` – nie trzeba osobnego `GET /api/parcel?id=` ani obsługi 409 (kilka obrębów o tej nazwie = kilka pozycji z gminą i powiatem).
- Koperta: `results` (nie `places`), `total` jak u Was, plus `truncated`, `hint`, `notices`, `attribution`. **Brak wyników = 200** (nie 404) – komunikat weź z `hint`.
- Pozycja: zamiast `kind: 'obreb' | 'gmina'` mamy `kind: 'parcel' | 'place'` i dla miejsc **`type: 'miejscowosc' | 'gmina' | 'obreb'`** (+ `type_label`); PRNG zwraca miejscowości (wieś ≈ obręb ewidencyjny), gminy pojawiają się tylko z rezerwy Nominatim; `obreb` na razie nieużywany. `id` to id źródła („prng:139271”), nie TERYT obrębu; `wojewodztwo`, `gmina`, `powiat` i kolejność `bbox` – jak u Was. Dodane: `label`, `lon`, `lat`, `bbox_approx`, `source`.
- **`bbox` dla miejscowości z PRNG jest przybliżony** (PRNG daje tylko punkt): `bbox_approx = true` – przybliżając mapę ustaw maks. zoom ~14–15; dla działki bbox to dokładny obrys.
- `places.proposal.ts` i `places.sample.json` można usunąć po przejściu na `/api/search`.

**Dla Mefju – jak to pokazać (frontendu A nie zmieniał):**
- **Lista podpowiedzi pod wyszukiwarką:** zapytanie po ~300 ms przerwy w pisaniu (debounce), minimum 2 znaki; anuluj poprzednie żądanie. Wyniki w dwóch grupach: **„Działki”** (`kind = parcel`: `label`, obok `area_ha`) i **„Miejscowości”** (`kind = place`: `label`, mały znacznik `type_label`). Brak wyników → `hint` szarym tekstem (nie błąd); `notices` – mała ikona ostrzeżenia z dymkiem („Nie udało się sprawdzić…”); `attribution` (gdy jest) – drobny dopisek na dole listy; `truncated` + `hint` („dopisz gminę”). Pierwsze zapytanie do PRNG trwa 2–6 s – pokaż stan „Szukam…”; kolejne z cache są natychmiastowe.
- **Wybór działki** → `GET /api/analysis?parcel_id=` (jak dotąd) i zbliżenie do `bbox`. **Wybór miejscowości** → `map.fitBounds(bbox, { maxZoom: bbox_approx ? 14 : 16 })` + podpowiedź „{name}: kliknij swoje pole na mapie” → klik = `GET /api/parcel?lon=&lat=` (działka z ULDK; przy 502 – `GET /api/analysis?lon=&lat=` daje obszar przybliżony).
- **„Narysuj swoje pole” – opcja dodatkowa, nie główna** (mały, drugorzędny przycisk obok mapy / pod listą, nie w pasku wyszukiwarki): rysowanie wielokąta (np. leaflet-geoman, MIT) → `POST /api/analysis` z `{ geometry }` (GeoJSON Polygon, [lon, lat]) i dalej jak dla działki; PDF: `POST /api/report.pdf` z tą samą treścią (odpowiedź = plik). Błąd 422 → pokaż `detail.message` pod rysunkiem. Oznaczenie w panelu: gdy `parcel.source === 'drawn'` – „Pole narysowane przez rolnika”, powierzchnia z kształtu (`powierzchnia_ha`), bez numeru działki i obrębu (`numer` = „—”); linku do udostępnienia nie ma (obrys nie mieści się w adresie). Limity: 0,05–200 ha, jeden wielokąt.
**Pliki frontendu zmienione przez A:** tylko `src/api/types.ts` (typy powyżej) i nowe mocki `src/mocks/search.sample.json`, `src/mocks/drawn.sample.json`. (`tsc -b` zgłasza jedynie brak `maplibre-gl` w `features/map3d/Terrain3D.tsx` – kod B, wymaga `npm install`.)
**Łamie zgodność:** nie (nowe endpointy i pola opcjonalne; `Parcel.source` / `name` z wartościami domyślnymi).

### 2026-11-21 · gałąź `a/backend` · A5e – „co planuję posiać”, raport krótki / pełny, słupki „Na tle 10 lat”, jeden stan wody
**Zmiany (addytywne; `backend/app/schemas/analysis.py` + `frontend/src/api/types.ts`; przykład `frontend/src/mocks/analysis.choice.sample.json`):**
- **Parametry:** `planned_crops` (GET `/api/analysis` i `/api/report.pdf`: 1–3 `RankingCropId` po przecinku, np. `planned_crops=pszenica_ozima,rzepak`; POST: `planned_crops: string[]`) – nieznana / więcej niż 3 → 422. **`report_type`** (`short` domyślnie | `full`) – GET `/api/report.pdf` i POST (`AnalysisRequest.report_type`).
- **`AnalysisResponse`:** `planned_crops`, **`seasonal_balance_by_year[]`** (`SeasonalBalanceYear`: `rok`, `bilans_mm`, `biezacy`) – 10 lat + bieżący, **`seasonal_balance_mean_mm`**, **`seasonal_balance_label`** („od 1 marca do 18 listopada”), **`weather_data_until`** (data ostatniego dnia pogody).
- **`CropSuggestions`:** **`choice[]`** (`ChoiceItem`: crop_id, label, category (null = wieloletnia), category_label, perennial, yield_typical_t_ha, total_typical_t, yield_weak_t_ha, total_weak_t, weak_year, drought_risk_years, years_simulated, rotation, **why**, confidence), **`choice_summary`**, **`alternatives[]`** (`AlternativeItem`: …, **relation** `lepsza|podobna`, **why**), **`not_recommended[]`** (`NotRecommendedItem`: crop_id, label, **reason**), **`top_ids[]`** (5 nieodradzanych).
- **`History`:** `summary` = proste zdanie („Ten rok jest suchszy niż zwykle – suszej było tylko w 2 z ostatnich 10 lat.”), nowe **`details`** = dawny tekst liczbowy.
- **Zmiany znaczenia (bez zmiany typów):** mm bilansów zaokrąglone do całości (jedna liczba wszędzie); poza sezonem wybranej uprawy (przed siewem / po zbiorze) `status` = stan działki (`status.scope = bez_uprawy`, równy `field_state.status`), `indicators.soil_water_*` = stan działki, `irrigation = null`; `irrigation` tylko w fazach wzrostu (także null przy zimowaniu); zero rekomendacji `nawadnianie` poza sezonem; ziemniak `irrigation_practice = optional`; `status.summary`: „W ostatnich 30 dniach spadło minus wyparowało: …”.

**Dla Mefju – jak to pokazać:**
- **Formularz „Przygotuj raport”** (przycisk „Pobierz raport” otwiera mały formularz zamiast od razu pobierać): (1) **Co planujesz posiać?** – do 3 upraw, opcjonalnie (lista 17 z `suggestions.groups[0].items` + `suggestions.perennials.items`: `label` / `crop_id`); (2) **Co rosło na tym polu?** – rok temu / 2 lata temu / 3 lata temu, każde z „nie wiem” (22 uprawy jak w A5b-2a, `crop_history=a,b,c`); (3) **Powierzchnia uprawy** – pole liczbowe wstępnie wypełnione `suggestions.area.value_ha` (`cultivated_area_ha`); (4) **Raport krótki (5 stron) / pełny** → **Generuj** = `GET /api/report.pdf?…&planned_crops=…&crop_history=…&cultivated_area_ha=…&report_type=short|full` (albo POST z tymi polami – dla narysowanego pola).
- **Ten sam blok 1–3 w panelu działki** (sekcja „Co tu posiać?”): po zmianie – `GET /api/analysis` z `planned_crops`, `crop_history`, `cultivated_area_ha`. Widok:
  - z wyborem: nagłówek „Twój wybór” + `choice_summary` (pogrubione); karta na każdą `choice[]`: nazwa + chip kategorii (✅ polecane #5BB37F, 🟡 możliwe #E8B931, ❌ odradzane #C8453B; wieloletnia – szary „uprawa wieloletnia”), trzy liczby („Typowo X t/ha – ok. T t z A ha”, „Słaby rok Y t/ha (rok)”, „Ryzyko suszy N na 10 lat”), pod spodem `why` (jedno zdanie) i `rotation.notes` („Płodozmian: …”, czerwone przy `naruszenie`); niżej „Lepsze możliwości” – `alternatives[]` (chip `relation`, nazwa, typowo t/ha, ryzyko, `why`); gdy pusta i wybór dobry – nic (choice_summary to mówi);
  - bez wyboru: „Najlepsze na tej działce” – pozycje z `top_ids` (w tej kolejności, dane z `groups[0].items`) + zachęta „Podaj, co planujesz posiać…”;
  - zawsze: jedna linijka **„Nie siej:”** z `not_recommended[]` („rzepak i rzepik (za mało wody na tej glebie); …”) albo „żadna z popularnych upraw nie jest tu odradzana”; pełna tabela 14 upraw pod „Pokaż wszystkie”.
- **Wykres słupkowy „Na tle 10 lat”** (zamiast pasma narastającego w widoku podstawowym): `seasonal_balance_by_year` – 11 słupków (oś X = `rok`), wartości ujemne w dół od zera, bieżący (`biezacy = true`) wyróżniony: czerwony #C8453B, gdy poniżej średniej, zielony #2F6B47 – gdy powyżej; poprzednie lata szare #B8BDB9; linia przerywana #2F80C9 = `seasonal_balance_mean_mm` z podpisem „średnia −74 mm”; nad wykresem `history.summary`, pod nim „ile wody zostało {seasonal_balance_label} w każdym roku (spadło minus wyparowało, mm)”; pod kartą wody „Dane pogodowe do {weather_data_until DD.MM}”. Słowo „bilans” w UI zastąpić „ile wody zostało: spadło minus wyparowało”.
- **Jeden stan wody:** gdy `crop` jest wybrana, ale `crop_season.phase` ∈ {`przed_siewem`, `po_zbiorze`} – nie pokazuj drugiego statusu uprawy; panel ma jeden status (`status`, równy `field_state.status`) i dopisek „{uprawa}: {phase_label} – uprawy nie ma w polu” (tekst jest w werdykcie). `irrigation == null` → bez karty nawadniania.
- **Rekomendacje:** etykieta „Najważniejsze” tylko przy pierwszej (w panelu nadal `in_panel`, maks. 3).
**Pliki frontendu zmienione przez A:** `src/api/types.ts` (typy powyżej), nowy mock `src/mocks/analysis.choice.sample.json`. (`tsc -b`: jedyny błąd – brak `maplibre-gl` w `features/map3d/Terrain3D.tsx`, kod B, wymaga `npm install`.)
**Łamie zgodność:** nie dla typów (pola dodane / opcjonalne). Zmiana znaczenia: poza sezonem uprawy `status` i woda w glebie pochodzą ze stanu działki, a `irrigation` jest null – frontend już obsługuje null.

### 2026-11-22 · gałąź `a/backend` · A5e-2 – raport skrócony 2 strony, alternatywy, grupy upraw, nazwy pól wykresu
**Zmiany (`backend/app/schemas/analysis.py` + `frontend/src/api/types.ts` + `mocks/analysis.choice.sample.json`):**
- **ZMIANA NAZW (łamie A5e – frontend jeszcze ich nie używał):** `seasonal_balance_by_year[]` → `{ year, balance_mm, current }` (było `rok`, `bilans_mm`, `biezacy`).
- `planned_crops` przyjmuje też **grupy** (`zboza_ozime`, `zboza_jare`, `straczkowe`, `rzepak_jesien`, …) i uprawy spoza rankingu (chmiel, tytoń) – bez 422; `AnalysisResponse.planned_crops: string[]`. `crop` i `previous_crop` przyjmują gatunki (np. `pszenica_ozima`) – w odpowiedzi `crop` = grupa modelu (`zboza_ozime`).
- `ChoiceItem` + **`requested_id`** (co podał rolnik) i **`group_note`** („Z grupy zboża ozime najlepiej wypada: żyto.”); `CropSuggestions` + **`choice_notes[]`** (uprawy bez danych w rankingu).
- `AlternativeItem.relation`: „lepsza” = mniej lat ze stratą > 20% przy podobnym plonie względnym; „podobna” – tylko gdy wybór jest ❌ wyłącznie przez płodozmian. Lista może być pusta (wybór najlepszy).
- `report_type`: `short` = **Raport skrócony (2 strony)**, `full` = **Raport szczegółowy**; nazwy plików `…-skrocony.pdf` / `…-szczegolowy.pdf`.

**Dla Mefju:**
- Wykres „Na tle 10 lat”: czytaj `year` (oś X), `balance_mm` (wysokość słupka), `current` (wyróżnienie) – zamiast `rok` / `bilans_mm` / `biezacy`.
- Formularz „Przygotuj raport”: opcje „**Raport skrócony** (2 strony)” i „**Raport szczegółowy**” (zamiast „krótki / pełny”). Lista „Co planujesz posiać?” może zawierać grupy (np. „zboża ozime”, „zboża jare”, „rośliny strączkowe”) obok gatunków – wysyłaj `crop_id` grupy, backend wybierze najlepszy gatunek.
- Karta wyboru: pod nazwą pokaż `group_note` (gdy jest), potem `why`; `rotation.notes` – nie powtarzaj, gdy `why` już mówi o płodozmianie (zawiera „po sobie”). `choice_notes` – drobnym szarym tekstem pod kartami.
- „Lepsze możliwości”: chip `relation` (lepsza – zielony, podobna – szarozielony), nazwa, „X na 10 lat”, `why` (mówi, w czym lepsza). Pusta lista = nie pokazuj nagłówka.
**Łamie zgodność:** tak – tylko nazwy pól `seasonal_balance_by_year` (dodane w A5e, nieużywane jeszcze przez frontend); reszta addytywna.

### 2026-11-22 · gałąź `a/backend` · A7 – opad ze stacji IMGW, `precip_sources`
**Zmiany (addytywne; `backend/app/schemas/analysis.py` + `frontend/src/api/types.ts`; przykład w `mocks/analysis.choice.sample.json`):**
- `AnalysisResponse` + **`precip_sources: PrecipSources | null`**: `main` (`imgw` | `imgw_daleko` | `nasa`), `main_label`, `stations[]` (`PrecipStation`: code, name, kind `synop|klimat|opad`, kind_label, distance_km, weight, coverage_pct, lon, lat), `nasa_factor`, `nasa_vs_imgw_pct`, `common_days`, `filled_days`, `filled_from`, `filled_earlier_days`, `agreement` (`zgodne` | `roznia_sie` | `mocno_sie_roznia` | `brak_danych`), `agreement_label`, `windows[]` (`PrecipWindow`: key `sezon|ostatnie_30_dni|wielolecie`, label, start, end, imgw_mm, nasa_mm, difference_pct, rating), **`sentence`**, `confidence_lowered`, `source_tag`.
- **Zmiana wartości (bez zmiany typów):** opad, bilans, status, `seasonal_balance_by_year`, ranking i werdykt liczone z opadu IMGW (suchszy o ok. 14–23% niż NASA) – liczby w odpowiedziach się zmieniły; w `reliability.sources` nowy wiersz „IMGW-PIB (stacje)”, a wiersz pogody nazywa się „IMGW-PIB (opad) + NASA POWER (parowanie)”; `verdict` – zdanie o opadach z porównaniem do normy („…pomiar ze stacji IMGW”).
- `suggestions.choice[].why` przy płodozmianie: „Pszenica ozima rosła tu rok temu – lepiej zrobić rok przerwy.”

**Dla Mefju:**
- **Zdanie o źródłach opadów** (`precip_sources.sentence`) – w paszporcie (sekcja „Skąd te dane”) i drobnym tekstem w karcie Werdyktu pod pozycją „Opady”: np. „Opady liczymy ze stacji IMGW Burzyn (27 km). Dane satelitarno-modelowe NASA pokazują o 14% więcej – przyjmujemy pomiar ze stacji.”
- **Stacja i odległość:** w paszporcie lista `stations[]` – „{name} ({kind_label}) · {distance_km} km · waga {weight × 100}%”; na mapie można pokazać znaczniki stacji (`lon`, `lat`). `main = imgw_daleko` → żółty dopisek „stacje dalej niż 30 km – opad mniej pewny”; `main = nasa` → „brak stacji IMGW w pobliżu – opad z modelu NASA”.
- **Zgodność źródeł:** odznaka z `agreement_label` (zgodne – zielona, różnią się – żółta, mocno się różnią – czerwona; `brak_danych` – szara); w rozwinięciu tabelka `windows[]` (okno, IMGW mm, NASA mm, różnica %). `filled_days > 0` → dopisek „ostatnie {filled_days} dni (od {filled_from}) – dane NASA przeliczone do poziomu stacji”.
**Pliki frontendu zmienione przez A:** `src/api/types.ts`, mock `src/mocks/analysis.choice.sample.json`.
**Łamie zgodność:** nie (pole dodane, opcjonalne).

### 2026-11-22 · gałąź `a/backend` · A11 – satelita Sentinel-2: `/api/satellite`, `satellite` w analizie, warstwy kondycja / wilgotność
**Zmiany (addytywne; `backend/app/schemas/{analysis,layers}.py` + `frontend/src/api/types.ts`; przykłady w `mocks/`):**
- **Nowy endpoint `GET /api/satellite?parcel_id=&date=`** (też `lon`/`lat`) i **`POST /api/satellite`** (treść jak `POST /api/analysis`, np. z `geometry`) → `Satellite`. Liczy na żywo (ok. 6–15 s, do ok. 10 MB), potem cache. Brak sceny / awaria = HTTP 200 ze `status: "brak_danych"` i `warning`.
- **`AnalysisResponse.satellite: Satellite | null`** – tylko z cache; gdy brak: `{ status: "pending", sentence: "Pobieram zdjęcie satelitarne…" }` (analiza nie czeka).
- **`Satellite`**: `status` (`ok` | `pending` | `brak_danych`), `date` (data sceny), `scene_id`, `ndvi`, `ndmi`, `ndvi_class` (`gleba` | `slaba` | `umiarkowana` | `gesta`) + `ndvi_label`, `ndmi_class` (`sucho` | `srednio` | `dobrze`; tylko w sezonie IV–IX przy NDVI ≥ 0,5) + `ndmi_label`, `valid_pct`, `cloud_pct`, `last_year: SatelliteScene` (date, scene_id, ndvi, ndmi, valid_pct, cloud_pct), `ndvi_change`, `trend` (`lepiej` | `podobnie` | `gorzej`), `level` (ok / warn / bad / info), `in_season`, **`sentence`** (z datą sceny), `warning`, `series: SatelliteSeriesPoint[]` (date, ndvi, ndmi, valid_pct – tylko z cache, 12 mies.), `series_note`, `layers` (`kondycja`, `wilgotnosc`), `downloaded_mb`, `compute_s`, `cached`, `note`, `source_tag`.
- **`VerdictKind` + `"rosliny"`** – pozycja werdyktu z satelity (tekst = `satellite.sentence`), tylko gdy jest zdjęcie; nie zmienia nagłówka.
- `indicators.crop_health` / `plant_moisture` wypełnione z satelity (NDVI → 0–100, NDMI −0,4…0,4 → 0–100; `index_value` = surowy wskaźnik, `note` „NDVI 0.86 · zdjęcie z 16.11.2026”); `reliability.sources` – Sentinel-2 `ok` z `data_date`.
- **`/api/layers/kondycja`** i **`/api/layers/wilgotnosc`** działają (wcześniej 501): `raster.image_url` = `data:image/png;base64,…`, `raster.bbox` = [lon_min, lat_min, lon_max, lat_max]; **nowe opcjonalne pola `LayerResponse`**: `legend: LegendStop[]` (value, color, label), `legend_title`, `legend_left`, `legend_right`, `value` (mediana), `scene_date`, `note`. Brak sceny → 404. `gleba` nadal 501.

**Dla Mefju:**
- **Ładowanie osobno:** po `/api/analysis` sprawdź `satellite.status`; `pending` → w karcie „Z satelity” i przy pigułkach warstw pokaż „Pobieram zdjęcie satelitarne…” (spinner) i wywołaj `GET /api/satellite` z tymi samymi `parcel_id` / `lon`,`lat` / `date` (dla obrysu – `POST` z `geometry`); po odpowiedzi podmień `satellite` i odśwież warstwy. `brak_danych` → szary tekst `warning` / `sentence`, pigułki Kondycja / Wilgotność nieaktywne.
- **Warstwa „Kondycja upraw”** = `/api/layers/kondycja`, **„Wilgotność roślin”** = `/api/layers/wilgotnosc` – `LayerData` już obsługuje `raster.image_url` + `bbox` (Leaflet `ImageOverlay`, `bounds = [[lat_min, lon_min], [lat_max, lon_max]]`); obrazowi daj `image-rendering: pixelated`. Legenda: `legend_left` / `legend_right` i gradient z `legend` (te same kolory co w CropHealth.tsx / PlantMoisture.tsx), pod spodem `note` (data zdjęcia). Białe piksele = chmury / brak danych.
- **Karta „Z satelity” w paszporcie:** `sentence` (duże), `ndvi` + `ndvi_label`, `ndmi` + (`ndmi_label` albo „oceniamy w sezonie IV–IX przy gęstym łanie”), „Rok temu: NDVI {last_year.ndvi} ({last_year.date})”, „Widoczna część działki {valid_pct}%”, `warning` na żółto; wykres liniowy `series` (NDVI zielona #3F8E4E, NDMI niebieska #2F80C9) z `series_note`; źródło i data z `source_tag`.
- **Wskaźnik „Wilgotność roślin”** poza sezonem ma wartość, ale `label` = „ocena tylko w sezonie przy gęstym łanie” – pokaż etykietę zamiast oceny (nie „niska wilgotność”).
- **Werdykt:** pozycja `kind = "rosliny"`, etykieta „Rośliny (z satelity)”, ikona wg `level` (`info` = niebieskie „i”).
- Przykłady: `mocks/satellite.sample.json`, `mocks/layers.kondycja.sample.json`, `mocks/layers.wilgotnosc.sample.json`, `analysis.choice.sample.json` (z `satellite`).
**Pliki frontendu zmienione przez A:** `src/api/types.ts`, mocki powyżej. (`tsc`: jedyny błąd – brak `maplibre-gl` w `features/map3d/Terrain3D.tsx`, kod B.)
**Łamie zgodność:** nie (pola i endpoint dodane; warstwy kondycja / wilgotnosc zamiast 501 zwracają dane albo 404).

### 2026-11-22 · `main` · A9+ – teren w tle, adresy, woda w okolicy, zgłoszenia (kontrakt F3 – zgodny z UI drugiej sesji)
**Zmiany (addytywne; `backend/app/schemas/{analysis,search,layers}.py` ↔ `frontend/src/api/types.ts` – typy F3 już były; mocki dopasowane do prawdziwych odpowiedzi API bez zmiany nazw pól):**
- `AnalysisResponse.terrain: Terrain | TerrainPending | null` – `{status: "pending"}` = liczony w tle; **`GET /api/terrain?parcel_id=`** (lon/lat, **POST** `{geometry}`) → `Terrain` (jak dotąd).
- `AnalysisResponse.hydro: Hydro | null` – `{status: "pending" | "ok" | "none", sentence, features[{kind: rzeka|ciek|row|kanal|zbiornik, name, distance_m, toward_outflow}], gauge{name, river, distance_km, level_cm, state: niski|sredni|wysoki, date} | null, sources[{name, url}]}`; pending → **`GET /api/hydro?parcel_id=`** (lon/lat, **POST** `{geometry}`). `none` = brak wody w 500 m (wodowskaz może być).
- `LayerKey + "woda"` – **`GET /api/layers/woda?parcel_id=&date=`** → GeoJSON (LineString / Polygon, `properties: kind, color, label, toward_outflow`) + `legend` (5 rodzajów), `note` z atrybucją OSM.
- **`POST /api/layers/kondycja|wilgotnosc`** z `{geometry, date}` (pole narysowane).
- `SearchResult.kind = "address"` + `locality`, `street`, `house_number`; `source` = `"prg"` | `"osm"`; `SearchResponse.attribution` („Adresy: PRG GUGiK” albo OSM).
- `/api/infra-reports` działa (POST 201, GET w prostokącie, `/{id}/confirm`, `/{id}/letter` – tekst).
- `/api/demo/examples`: `less-drzewce` zamiast `mady-zulawy`.

**Dla Mefju:**
- Teren i woda ładują się osobno jak satelita: `terrain.status === "pending"` → `api.terrain(q)`; `hydro.status === "pending"` → `api.hydro(q)` (może trwać do ok. 60 s – Overpass; przy 502 pokaż „Nie udało się sprawdzić wody w okolicy – spróbuj za chwilę” i przycisk ponów). Po terenie warto odświeżyć analizę (werdykt „teren” i reguła zastawki biorą teren / wodę z cache).
- Mocki `terrain.sample.json`, `hydro.sample.json` (Pożarowo 70/4), `layers.woda.sample.json`, `search.address.sample.json` („Drwinia 1”: działka + adres) – prawdziwe odpowiedzi.
- Wyszukiwarka: grupa „Adresy” pod „Działki”, ikona domu; klik adresu = przybliżenie do `bbox` (bez analizy – rolnik klika pole); pod listą `attribution` drobnym tekstem.
- Warstwa „Rowy i zbiorniki” = `woda`: linie w `color` (rów jaśniejszy niebieski, rzeka ciemny), zbiorniki – wypełnienie; dymek `label`; `toward_outflow` – można pogrubić.
**Łamie zgodność:** nie (pola i endpointy dodane; nazwy jak w typach F3).
