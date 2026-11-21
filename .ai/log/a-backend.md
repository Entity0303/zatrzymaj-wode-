# Dziennik – osoba A (Dominik), backend

Nowe wpisy na górze. Wpis: data i godzina · gałąź · co zrobiono · zmienione pliki · czy zmieniono kontrakt API.

---

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
