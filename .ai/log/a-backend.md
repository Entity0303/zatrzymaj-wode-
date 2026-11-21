# Dziennik – osoba A (Dominik), backend

Nowe wpisy na górze. Wpis: data i godzina · gałąź · co zrobiono · zmienione pliki · czy zmieniono kontrakt API.

---

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
