# Status – osoba A (Dominik), backend

_Stan na: 2026-11-21 17:18_

## Zrobione
- Wyszukiwanie działki ULDK: pełny identyfikator, „obręb numer”, punkt; `GET /api/parcel` (409 lista kandydatów, 404, 502 z nazwą źródła), timeout 10 s + jedna ponowna próba, cache 24 h.
- Prognoza pogody: `GET /api/forecast` (Open-Meteo), cache 30 min.
- Kontrakt `GET /api/analysis` w `schemas/analysis.py`; endpoint zwraca 501. Szkielety: `/api/layers`, `/api/reports`, `/api/infra-reports`.
- **A1 (scalone, PR #1):** historia pogody 10 lat – NASA POWER (+ zapasowo archiwum Open-Meteo), ET0 FAO-56 z metodą na każdy dzień, `analysis/water_balance.py` → sekcja `history` (bilans narastająco od 1 marca, pasmo 10 lat, opady miesięczne, braki/opóźnienie w ograniczeniach). Tymczasowy `GET /api/dev/weather-history`.
- **Kontrakt:** `History` rozszerzone o `balance_deviation_mm`, `balance_rank`, `longest_dry_spell`, `band_years` (uzgodnione z B) – wypełniane przez `build_history`.
- **A2 (gałąź `a/gleba`):** gleba – IUNG przez WCS (kody komórek 5 m), zapasowo GetFeatureInfo; klasy EGiB z KIEG; `analysis/soil.py` → `indicators.soil_capacity`, flaga „to nie jest grunt rolny”. Tymczasowy `GET /api/dev/soil`.
- **Kontrakt:** `History` + 4 pola (A1→A2); **nowa sekcja `soil`** (A3, uzgodnione z B) – wypełniana przez `analysis/soil.to_contract`.
- **A3 + A3b (gałąź `a/backend`):** `analysis/crops.py` – 15 upraw (Kc, fazy przeskalowane do siew–zbiór w PL, Zr, p, terminy zbioru, kalendarz całego roku: przed siewem / fazy / dojrzewanie / po zbiorze / wschody jesienne / spoczynek zimowy). Model wody w glebie FAO-56 w `analysis/water_balance.py` jako **ciągły bilans** od 1 XI (1 VII dla rzepaku jesiennego): profil 1 m w dwóch warstwach, korzenie rosną od siewu, goła gleba – parowanie dwuetapowe, siew nie resetuje zapasu, zimowa odbudowa z przesiąkaniem. Dni stresu tylko w fazach wrażliwych; w dojrzewaniu / po zbiorze / spoczynku brak alarmu i nawadniania. Nawadnianie: dawka wg kategorii gleby (17,5–32,5 mm, ≤ 35), harmonogram w 7 dniach, częstotliwość, łączny niedobór. Stan wody na każdą datę (także listopad) z opisem i porównaniem z 10 latami. Tymczasowy `GET /api/dev/water`.
- **Kontrakt:** `soil`, `crop_season`, `soil_water`, `irrigation` (A3, A3b – uzgodnione z B).
- **A4 – KAMIEŃ MILOWY 1 (gałąź `a/backend`):** pełne `GET /api/analysis?parcel_id=&crop=&date=` zgodne z kontraktem – ULDK → równolegle pogoda 10 lat, gleba IUNG, klasy EGiB, prognoza (dla dziś) → bilans i model wody → ocena (`analysis/scoring.py`) → pewność i `reliability` (`analysis/confidence.py`) → przyczyny z udziałami (`analysis/causes.py`) → rekomendacje z 19 reguł YAML (`analysis/recommendations.py`, `analysis/rules/*.yaml`; 4 wyłączone do A6/A7) z `in_panel` (maks. 3). Kroki z czasami, budżet 27 s, 502 tylko bez ULDK/pogody, 422 bez uprawy. Wspólne fakty: `analysis/facts.py`. Mock frontendu = zapis prawdziwej odpowiedzi.
- Testy: 150 bez sieci (sprawdzone w kontenerze bez sieci) + 5 live. Live A4: 1,2–2,5 s na analizę.

## W trakcie (gałąź)
- `a/backend` – **kamień milowy 1 gotowy do merge do `main`** (decyzja właściciela repo; B może już teraz `git merge origin/a/backend`).

## Następne
1. Teren z NMT (`sources/nmt.py`, `analysis/terrain.py`) + rowy BDOT10k – włączy reguły `requires: terrain / water_nearby` i parametry spływu w modelu (A6/A7).
2. Sentinel-2 NDVI/NDMI (`sources/sentinel.py`) – wskaźniki `crop_health`, `plant_moisture`, warstwy mapy; pewność może wtedy dojść do „wysokiej”.
3. **Kalibracja do IUNG SMSR** (kukurydza 2018 – model pokazuje mniej stresu niż średnia; porównać z komunikatami SMSR 2018/2019/2021).
4. `/api/layers`, raport PDF; końcowe sprzątanie `/api/dev/*`.

## Blokery / pytania do drugiej osoby
- **B: `/api/analysis` działa** (pytanie z Waszego statusu) – `git merge origin/a/backend`. Kontrakt bez zmian poza `Recommendation.priority` i `in_panel`.
- **B: panel „Co zrobić?” powinien filtrować po `in_panel`** (maks. 3, po jednej z grupy), a nie brać pierwszych 3 z listy; pełna lista – paszport.
- B: czy w panelu „Woda w glebie” duża liczba to `soil_water_pct` czy `soil_water_mm`? (`soil_water.scope` mówi, czy to strefa korzeni, czy profil).
- B: `stress_days_by_year` – `null` = „Brak danych”, nie 0. Poza fazami wrażliwymi `risk_7d.value = null`, `label = "Nie dotyczy"`.
- B: `crop_health` i `plant_moisture` mają `value: null` i `source_tag.kind = brak_danych` (satelita w przygotowaniu); kroki `satellite` i `terrain` mają `state = pending`.
