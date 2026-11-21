# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21_

## Zrobione
- Wyszukiwanie działki ULDK: pełny identyfikator, „obręb numer”, punkt; `GET /api/parcel` (409 lista kandydatów, 404, 502 z nazwą źródła), timeout 10 s + jedna ponowna próba, cache 24 h.
- Prognoza pogody: `GET /api/forecast` (Open-Meteo: pogoda teraz + 7–16 dni, opad, ET0, bilans dnia i okresu; brak danych ≠ 0), cache 30 min.
- Kontrakt `GET /api/analysis` w `schemas/analysis.py` (SPEC 6, 7, 15.2); endpoint zwraca 501 „w budowie”. Szkielety: `/api/layers`, `/api/reports`, `/api/infra-reports`.
- Struktura `core/ schemas/ sources/ analysis/ routers/ report/`, wspólny `TTLCache`.
- Gotowy kod do użycia w analizie (z testami): NASA POWER (`sources/weather_power.py`), ET0 FAO-56 PM + Hargreaves (`analysis/et0.py`), kategorie gleb IUNG (`sources/iung.py`).
- Testy: 42 (bez sieci) + 1 live; `test_contract.py` pilnuje zgodności z `frontend/src/api/types.ts`.

## W trakcie (gałąź)
- — (brak)

## Następne
1. Pogoda 10 lat z NASA POWER w analizie (tylko dane sprzed daty analizy), ET0 (PM, fallback Hargreaves – oznaczanie metody), bilans wody KBW narastająco + pasmo z 10 lat → `analysis/water_balance.py`.
2. Gleba IUNG → WOD (`analysis/soil.py`), model wody w glebie FAO-56, dni stresu w latach.
3. Pierwsza wersja `/api/analysis` zwracająca prawdziwe `indicators` i `history` (reszta: `brak_danych`).

## Blokery / pytania do drugiej osoby
- B: czy w panelu „Woda w glebie” ma pokazywać `soil_water_pct` czy `soil_water_mm` jako dużą liczbę (kontrakt ma oba)?
