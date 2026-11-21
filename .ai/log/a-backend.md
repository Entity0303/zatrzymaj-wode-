# Dziennik – osoba A (Dominik), backend

Nowe wpisy na górze. Wpis: data i godzina · gałąź · co zrobiono · zmienione pliki · czy zmieniono kontrakt API.

---

## 2026-11-21 16:21 · `a/backend` · A3: uprawy i model wody w glebie FAO-56 (+ sekcja gleby w kontrakcie)
**Co:**
- Kontrakt (osobny commit 0f7b511): sekcja `soil` w `AnalysisResponse` (dominująca, udziały IUNG, WOD, klasy EGiB + powód braku, `non_agricultural` + powód + komunikat); `analysis/soil.to_contract()`.
- `CLAUDE.md` (osobny commit ff22747): jedna długa gałąź na osobę, merge do `main` przy kamieniach milowych.
- `analysis/crops.py`: 15 upraw – Kc ini/mid/end (FAO-56 tab. 12), fazy (tab. 11, dopasowane do PL), Zr i p (tab. 22), start sezonu PL; Kc wg faz (rys. 25), nazwy faz; założenia oznaczone w komentarzach (kiszonka, rzepak jesień, tytoń, terminy strączkowych/warzyw, fazy wieloletnich).
- `analysis/water_balance.py`: model „wiadra” FAO-56 – TAW = WOD × min(Zr, 1 m), RAW = p·TAW; zapas na start z bilansu P − ET0 przed sezonem (1 XI, dla siewu letniego 1 VII); Ks (równ. 84), spływ 20% opadu > 20 mm, przesiąkanie; dni stresu w sezonie i w tych samych dniach 10 poprzednich lat; luka opóźnienia NASA uzupełniana Open-Meteo `past_days` (albo scenariuszem); horyzont 16 dni: prognoza (dziś) / mediana 10 lat (data historyczna); ryzyko niskie/średnie/wysokie (≤ 3 / 4–7 / > 7 dni); nawadnianie (dawka do pojemności polowej, co 5 mm, podpowiedź podziału > 40 mm); przed sezonem – brak, po sezonie – tylko podsumowanie; `to_contract_indicators()` → `soil_water_pct`, `soil_water_mm`, `risk_7d`, `stress_days_by_year`, rekomendacja „nawadnianie”. `history_range` od 1 XI (rok − 11).
- `sources/weather_openmeteo.fetch(..., past_days=)`.
- `routers/analysis.py`: TYMCZASOWY `GET /api/dev/water?parcel_id=&crop=&date=` (ULDK → pogoda, IUNG, KIEG, prognoza równolegle; grunt nierolny → bez modelu).
- Testy: `tests/test_water_model.py` (25 + live); A1 – nowy początek zakresu danych.
- Live (dev/water):

| działka | uprawa | data | woda % | mm | dni stresu | ten rok vs śr. 10 lat | ryzyko 7 dni | nawadnianie | czas |
|---|---|---|---|---|---|---|---|---|---|
| 201305 | zboża ozime | 2018-07-15 | 36 | 60 | 52 | 52 vs 19,3 | wysokie (stres trwa) | 105 mm od razu | 2,0 s |
| 201305 | zboża ozime | 2021-07-15 | 44 | 74 | 13 | 13 vs 24,1 | wysokie (stres trwa) | 95 mm od razu | 1,5 s |
| 201305 | zboża ozime | 2026-11-21 | – | – | 70 | 70 vs 44,7 | po sezonie | – | 1,5 s |
| 201305 | kukurydza | 2018-07-15 | 73 | 122 | 0 | 0 vs 0,6 | niskie (stres za ok. 15 dni) | niepotrzebne | 0,01 s |
| 201305 | kukurydza | 2021-07-15 | 84 | 140 | 0 | 0 vs 0,6 | niskie | niepotrzebne | 0,01 s |
| 201305 | kukurydza | 2026-11-21 | – | – | 79 | 79 vs 44,4 | po sezonie | – | 0,01 s |
| 061704 | zboża ozime | 2018-07-15 | 31 | 63 | 48 | 48 vs 12,8 | wysokie (stres trwa) | 140 mm od razu | 5,5 s |
| 061704 | zboża ozime | 2021-07-15 | 39 | 80 | 3 | 3 vs 17,6 | wysokie (stres trwa) | 125 mm od razu | 1,6 s |
| 061704 | zboża ozime | 2026-11-21 | – | – | 75 | 75 vs 39,8 | po sezonie | – | 0,7 s |
| 061704 | kukurydza | 2018-07-15 | 84 | 170 | 0 | 0 vs 0,0 | niskie | niepotrzebne | 0,01 s |
| 061704 | kukurydza | 2021-07-15 | 75 | 152 | 0 | 0 vs 0,0 | niskie | niepotrzebne | 0,01 s |
| 061704 | kukurydza | 2026-11-21 | – | – | 82 | 82 vs 49,7 | po sezonie | – | 0,01 s |

  Ścieżka z prognozą (dziś, rzepak jesień – w sezonie): `horizon_kind = prognoza`, 2 dni luki NASA uzupełnione z Open-Meteo, 100% wody (jesień).
**Pliki:** `backend/app/analysis/{crops,water_balance,soil}.py`, `backend/app/sources/weather_openmeteo.py`, `backend/app/routers/analysis.py`, `backend/tests/{test_water_model,test_weather_history}.py`; kontrakt: `backend/app/schemas/analysis.py`, `frontend/src/api/types.ts`, `frontend/src/mocks/analysis.sample.json`.
**Kontrakt API:** TAK – sekcja `soil` (osobny commit, wpis w `contract-changes.md`).

## 2026-11-21 16:06 · `a/gleba` · A2: gleba IUNG + klasy EGiB (+ rozszerzenie kontraktu)
**Co:**
- Kontrakt (osobny commit 9838d55): `History` + `balance_deviation_mm`, `balance_rank {lower_years, of_years}`, `longest_dry_spell {days, end_date}`, `band_years`; `build_history` je wypełnia (commit 3597440).
- `sources/iung.py`: metoda główna WCS 2.0.1 GetCoverage `text/plain` (osie PL: x = północ, y = wschód; wiersz 0 = północ – sprawdzone 6/6 z GetFeatureInfo), zliczanie komórek 5 m ze środkiem w obrysie (`shapely.contains_xy`), SCALEFACTOR powyżej 250 tys. komórek, działka mniejsza od komórki → komórka z punktem w obrysie; zapasowo GetFeatureInfo w ≤ 16 punktach równolegle; timeout 8 s + 1 ponowna próba; cache 24 h (klucz: WKT geometrii). Wynik: udziały, dominująca, udział gruntów mineralnych, WOD ważona, kod „nierolny” (> 50%).
- `sources/kieg.py`: GetFeatureInfo `text/html` w środku + 3 punktach, tylko wiersze naszej działki, klasy z „Oznaczenie konturu”, użytek z „Oznaczenie użytku”; brak klas = notka, nie błąd; nie przenosimy pól o właścicielach.
- `analysis/soil.py`: `assess_soil()` → `indicators.soil_capacity` (WOD, `pomiar`/IUNG, status wg kategorii), `reliability.sources`, ograniczenia, `degrades_confidence`; błąd IUNG → brak danych + obniżona pewność; błąd KIEG → tylko informacja.
- `routers/analysis.py`: TYMCZASOWY `GET /api/dev/soil?parcel_id=` (IUNG i KIEG równolegle, czasy).
- Testy: `tests/test_soil.py` (21 + live) na prawdziwych odpowiedziach zapisanych w `tests/fixtures/` (WCS, GFI, KIEG z klasami i bez).
- Live (6 działek): wszystkie metodą WCS, 0,5–0,8 s; 302114 okazała się w 100% wodą (kod 12) – tabela w `.ai/test-parcels.md`.
**Pliki:** `backend/app/sources/{iung,kieg}.py`, `backend/app/analysis/soil.py`, `backend/app/routers/analysis.py`, `backend/app/core/{config,http}.py`, `backend/tests/{test_soil,test_core}.py`, `backend/tests/fixtures/{iung_wcs_201305.txt,iung_gfi_code3.json,kieg_201305_klasy.html,kieg_040703_bez_klas.html}`.
**Kontrakt API:** TAK (4 pola w `History`, osobny commit). Dalej brakuje sekcji gleby (udziały, klasy, flaga nierolna) – propozycja w statusie, NIE wprowadzona.

## 2026-11-21 15:40 · `a/pogoda-bilans` · A1: historia pogody 10 lat, ET0 FAO-56, bilans wody
**Co:**
- `sources/weather_power.py`: zakres od 1 stycznia (rok początku sezonu − 10) do dnia przed datą analizy, -999 → NaN, wysokość z odpowiedzi, `get_with_retry` (timeout 9 s, 1 ponowna próba przy sieci/timeoucie/5xx, 429 bez ponawiania), cache 6 h (klucz: lat/lon zaokrąglone do 0,1° + zakres dat; zapytanie też idzie z zaokrąglonymi współrzędnymi).
- `sources/weather_openmeteo.py`: archiwum Open-Meteo (`fetch_archive`) jako źródło zapasowe; prognoza bez zmian.
- `analysis/et0.py`: wspólny `DailyWeather` (ciągła seria `datetime64[D]`, `densify`), `apply_et0` – PM → ET0 ze źródła (OM) → Hargreaves → brak, metoda zapamiętana dla każdego dnia.
- `analysis/water_balance.py`: `build_history()` → `History` z kontraktu + `WaterBalanceResult` (odchylenie, percentyl, lata porównawcze, najdłuższy okres bez opadu, braki, ograniczenia).
- `routers/analysis.py`: `load_weather_history()` (NASA → Open-Meteo) i TYMCZASOWY `GET /api/dev/weather-history`.
- `core/http.py`: `get_with_retry`; `core/config.py`: timeouty i URL archiwum.
- Testy: `tests/test_weather_history.py` (22 + live), fikstury syntetyczne `tests/fixtures/` (+ generator).
- Live 15.07.2018, 52,9 N 22,6 E: bilans 1.03–14.07 = −145,1 mm, średnia 2008–2017 = −39,2 mm, odchylenie −105,9 mm, niższy w 1/10 lat; najdłużej bez opadu 17 dni (do 28.03); ET0: 136 dni PM; pobieranie 1,84 s.
**Pliki:** `backend/app/analysis/{et0,water_balance}.py`, `backend/app/sources/{weather_power,weather_openmeteo}.py`, `backend/app/core/{http,config}.py`, `backend/app/routers/analysis.py`, `backend/tests/test_weather_history.py`, `backend/tests/test_core.py`, `backend/tests/fixtures/*`.
**Kontrakt API:** NIE. Braki w `History` (do uzgodnienia z B): `balance_deviation_mm`, ranking względem 10 lat (`lower_years` / liczba lat), `longest_dry_spell_days` + data końca, `band_years`. Dziś te liczby są tylko w `summary` i w odpowiedzi endpointu deweloperskiego.

## 2026-11-21 15:20 · `main` · commit f31e94c
**Co:** struktura pod pracę zespołową; `main.py` tylko rejestruje routery; `core/` (config, http, cache, geo), `schemas/` (parcel, analysis, layers, reports, weather), szkielety źródeł (kieg, nmt, bdot, sentinel, gus) i obliczeń (crops, water_balance, soil, terrain, scoring, recommendations, rules/), routery-szkielety 501, `report/`. Usunięte nieużywane endpointy `/api/soil`, `/api/weather` (NASA), `/api/meta/today` (kod źródeł zostaje). Test kontraktu.
**Pliki:** `backend/app/**` (39), `backend/tests/test_contract.py`, testy – nowe importy.
**Kontrakt API:** TAK – utworzenie schematu `/api/analysis` (+ parcel, weather, layers, reports) → `.ai/contract-changes.md`.

## 2026-11-21 15:03 · `main` · commit 0bff78f
**Co:** `GET /api/forecast` – Open-Meteo (pogoda teraz, prognoza dobowa, opad, ET0, bilans; suma okresu tylko przy pełnych danych), cache, testy.
**Pliki:** `backend/app/sources/open_meteo.py`, `backend/app/main.py`, `backend/tests/test_forecast.py`.
**Kontrakt API:** nowy endpoint `/api/forecast` (przed formalnym kontraktem).

## 2026-11-21 14:21 · `main` · commit 265b6a7
**Co:** klient ULDK (pełny id, „obręb numer”, punkt; timeout 10 s, ponowna próba, cache 24 h, `NotFoundError`), `GET /api/parcel` z polami po polsku, 409/404/502; testy respx + test live.
**Pliki:** `backend/app/sources/uldk.py`, `backend/app/http.py`, `backend/app/main.py`, `backend/app/config.py`, `backend/tests/test_uldk.py`, `backend/pyproject.toml`, `docker-compose.yml` (polling).
**Kontrakt API:** format odpowiedzi `/api/parcel` (przed formalnym kontraktem).

## 2026-11-21 13:44 · `main` · commit 0dc3fe4
**Co:** szkielet backendu FastAPI: ULDK, IUNG (kategorie gleb), NASA POWER + ET0 FAO-56 (PM, Hargreaves), testy.
**Pliki:** `backend/**`, `docker-compose.yml`.
**Kontrakt API:** nie (brak formalnego kontraktu).
