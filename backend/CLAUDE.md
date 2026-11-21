# Backend – zasady (osoba A: Dominik)

Uzupełnia główny `CLAUDE.md` (źródła danych, wymagania KOWR, praca zespołowa, pamięć projektu w `.ai/`).
Python 3.12, FastAPI, httpx (async), numpy, shapely, pyproj. Uruchamianie: `docker compose up` (port 8000).

## Struktura `app/`

| Katalog | Co tu jest |
|---|---|
| `main.py` | tylko utworzenie app, middleware i rejestracja routerów (plik wspólny – osobny mały commit) |
| `core/` | `config.py` (ustawienia z env), `http.py` (wspólny klient, `SourceError`/`NotFoundError`, 404/502/501, `in_poland`), `cache.py` (`TTLCache`), `geo.py` (EPSG:2180 ↔ 4326, WKT, punkty w obrysie) |
| `schemas/` | **KONTRAKT API** (Pydantic): `parcel.py`, `analysis.py`, `layers.py`, `reports.py`, `weather.py` |
| `sources/` | **jeden plik na źródło danych**: `uldk`, `weather_power` (NASA POWER), `weather_openmeteo`, `iung`, `kieg`, `nmt`, `bdot`, `sentinel`, `gus` |
| `analysis/` | obliczenia: `et0`, `crops`, `water_balance`, `soil`, `terrain`, `scoring`, `recommendations`, reguły w `rules/*.yaml` |
| `routers/` | endpointy: `parcel`, `weather` (działają); `analysis`, `layers`, `reports`, `infra_reports` (501 „w budowie”) |
| `report/` | raport PDF (WeasyPrint) |

Źródło danych nie liczy niczego poza parsowaniem odpowiedzi; obliczenia są w `analysis/`; router tylko składa wynik w model ze `schemas/`.

## Źródła danych: timeouty i błędy

- Każde zapytanie ma **timeout** (domyślnie `settings.http_timeout_s`, ULDK `uldk_timeout_s` = 10 s, Open-Meteo 10 s). Przy błędzie połączenia (np. chwilowy DNS) – jedna ponowna próba.
- Błąd źródła = `SourceError(źródło, komunikat po polsku)`; brak obiektu (działki, punktu) = `NotFoundError`.
  Mapowanie w routerach przez `core.http.http_error`: `NotFoundError` → 404, `SourceError` → 502 z nazwą źródła.
- **Analiza nigdy się nie wywraca przez jedno źródło.** Źródła pobieramy równolegle (`asyncio.gather(..., return_exceptions=True)`); `SourceError` z jednego źródła → wskaźnik z `value: null` i `source_tag.kind = "brak_danych"`, wpis w `reliability.sources` ze statusem `brak`/`czesciowo`, **obniżona pewność** i ograniczenie w `reliability.limitations`. HTTP 502 tylko wtedy, gdy bez tego źródła nie da się nic policzyć (np. ULDK – brak działki).
- Limit < 30 s na całą analizę: suma timeoutów równoległych źródeł musi się w tym mieścić.

## Cache

- `core.cache.TTLCache` w module źródła (klucz = parametry zapytania). ULDK 24 h, prognoza Open-Meteo 30 min.
- Każde źródło z cache ma `clear_cache()` – testy czyszczą cache w fixture.
- TODO: trwały cache w SQLite (dane historyczne nie zmieniają się – można trzymać długo).

## Data analizy

- Parametr `date` (domyślnie dziś, maks. 10 lat wstecz). **Dla daty historycznej używamy wyłącznie danych sprzed tej daty** (pogoda do `date − 1`, zdjęcie satelitarne najbliższe *przed* datą, prognoza nie istnieje dla przeszłości).
- `historical = date < dziś`. Okno 10 lat liczone od daty analizy, nie od dziś.

## Testy

- `pytest` – **bez sieci**, na zapisanych przykładowych odpowiedziach źródeł (stałe w testach, mock `respx`). Każdy nowy klient źródła: test sukcesu, braku wyników, błędu/timeoutu.
- Testy „na żywo” oznaczone `@pytest.mark.live` – domyślnie pomijane (`addopts = -m 'not live'`), uruchamiane ręcznie: `pytest -m live`.
- W Dockerze: `docker compose run --rm -v "$(pwd)/backend/tests:/app/tests" -v "$(pwd)/backend/pyproject.toml:/app/pyproject.toml" -v "$(pwd)/frontend/src:/frontend/src:ro" backend pytest -q` (montaż `frontend/src` jest potrzebny do testu kontraktu).

## Kontrakt API

- `schemas/` = kontrakt z frontendem (`frontend/src/api/types.ts`). Zmiana **tylko po uzgodnieniu z osobą B**, w obu miejscach naraz, z wpisem w `.ai/contract-changes.md` (osobny mały commit).
- `tests/test_contract.py` musi przechodzić: przykład `frontend/src/mocks/analysis.sample.json` waliduje się modelem (`extra="forbid"`), każde pole modelu jest w `types.ts`, szkielety zwracają 501.
- Brak danych = `null` + `brak_danych`, nigdy 0. Każda liczba ma `source_tag`. Rekomendacje w kolejności retencja → agrotechnika → nawadnianie, teksty z reguł wypełniane liczbami (LLM nie liczy niczego).
