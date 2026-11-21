# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 15:40_

## Zrobione
- Wyszukiwanie działki ULDK: pełny identyfikator, „obręb numer”, punkt; `GET /api/parcel` (409 lista kandydatów, 404, 502 z nazwą źródła), timeout 10 s + jedna ponowna próba, cache 24 h.
- Prognoza pogody: `GET /api/forecast` (Open-Meteo), cache 30 min.
- Kontrakt `GET /api/analysis` w `schemas/analysis.py`; endpoint zwraca 501. Szkielety: `/api/layers`, `/api/reports`, `/api/infra-reports`.
- **A1 (gałąź `a/pogoda-bilans`, PR do zrobienia):** historia pogody 10 lat – NASA POWER (timeout 9 s + 1 ponowna próba, cache 6 h, klucz 0,1°), zapasowo archiwum Open-Meteo (429 = niedostępność); `DailyWeather` + ET0 FAO-56 PM / Hargreaves / ET0 źródła z metodą na każdy dzień (`analysis/et0.py`); `analysis/water_balance.py` buduje sekcję `history` kontraktu: bilans narastająco od 1 marca, pasmo min/max/średnia z 10 lat, odchylenie, percentyl, opady miesięczne vs średnia, najdłuższy okres bez opadu, braki i opóźnienie źródła w ograniczeniach; `stress_days_by_year` puste (A3). Tymczasowy `GET /api/dev/weather-history`.
- Testy: 64 bez sieci + 2 live. Live 15.07.2018 (52,9 N 22,6 E): bilans −145,1 mm vs średnia 2008–2017 −39,2 mm (−105,9 mm), niższy tylko w 1 z 10 lat; NASA POWER 1,84 s.

## W trakcie (gałąź)
- `a/pogoda-bilans` – czeka na Pull Request / review.

## Następne
1. A2: gleba IUNG → WOD (`analysis/soil.py`), „to nie jest grunt rolny” dla kodów 11–14.
2. A3: model wody w glebie FAO-56 (Kc upraw w `analysis/crops.py`), % wody dostępnej, **dni stresu w każdym roku** (wypełni `history.stress_days_by_year`), „stres za X dni” z prognozy.
3. Pierwsza wersja `/api/analysis` z prawdziwymi `indicators.water_balance_season`, `history`, `reliability` (reszta `brak_danych`); usunięcie `/api/dev/weather-history`.

## Blokery / pytania do drugiej osoby
- B: czy w panelu „Woda w glebie” duża liczba to `soil_water_pct` czy `soil_water_mm` (kontrakt ma oba)?
- B: `stress_days_by_year` będzie pustą listą do czasu A3 – UI powinien pokazać „Brak danych”, nie zera.
