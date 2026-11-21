# Dziennik – osoba A (Dominik), backend

Nowe wpisy na górze. Wpis: data i godzina · gałąź · co zrobiono · zmienione pliki · czy zmieniono kontrakt API.

---

## 2026-11-22 01:10 · `a/backend` · A5b-2c: drobne poprawki PDF – nazwa Wodoskop, bez QR, „woda” = info
**Co:** nazwa produktu „Wodoskop” (nagłówek + podtytuł, stopka, `<title>`, metadane author/generator, tytuł API); QR tylko przy ustawionym `PUBLIC_URL` (domyślnie puste, `.env.example` zakomentowane); werdykt – pozycja `woda` ma `level = info` (ikona kropli #2F80C9 w PDF), poziom całości liczony bez niej; PDF obszaru przybliżonego – tylko nota „brak dokładnych granic działki” (usunięte „ULDK” z noty i ograniczeń, powód techniczny nie trafia do PDF); nowe PNG pierwszych stron. Testy: +3 (343).
**Pliki:** `core/config.py`, `.env.example`, `main.py`, `analysis/{verdict,approx_area,confidence}.py`, `schemas/analysis.py`, `report/{builder.py,report.css,templates/report.html}`, `tests/test_a5b2b.py`; frontend: `api/types.ts`, mocki.
**Kontrakt:** TAK (addytywnie) – `VerdictStatement.level` + `info`; wpis w `contract-changes.md`.

## 2026-11-22 00:30 · `a/backend` · A5b-2b: werdykt działki, spójność gleba × teren, analiza po punkcie, PDF z werdyktem
**Co:**
- **1. Werdykt** (`analysis/verdict.py`, `rules/verdict.yaml`, D68): nagłówek + 4–6 zdań, poziomy ok/warn/bad, ✅/❌ uprawy, deterministycznie. 201305 (bez uprawy): „Dobra działka z wilgotnym obniżeniem”; Puszcza Notecka (punkt): „Słaba, sucha działka – siej rośliny odporne na suszę”.
- **2. Spójność** (D66): `analysis/soil_label.py` – grupa gleby ważona udziałem (201305: 78% glp + 22% pgl → średnia); `teren_gleba.yaml` na grupach lekka/średnia/ciężka/organiczna; „obniżenie” zamiast „dołek”, bez „Nie ma zagłębień”; `retencja.prochnica` – z powrotem `light_soil`.
- **3. Ranking** (D67, D70): wieloletnie w `suggestions.perennials`; kukurydza `informacyjne`; kompleks przydatności przed kategorią IUNG.
- **4. Po punkcie** (D69): `lon`/`lat` w analizie i PDF, kwadrat 1 ha przy niedostępnym ULDK, pewność −15, KIEG pomijany. Test słabej ziemi (IUNG kod 1): Notecka 16,26/52,685 i Kurpie 21,43/53,27 → ❌ pszenica, rzepak, jęczmienie, kukurydza; ✅ żyto, łubin; owies ❌ (Ky 1,10, wrażliwość wysoka – nie zmieniane).
- **5. PDF** (D71): str. 1 werdykt, str. 2 ranking, dalej szczegóły; 6 stron; przykłady `reports/examples/dobra-bez-uprawy`, `dobra-zboza-ozime`, `slaba-bez-uprawy`, `slaba-zboza-ozime`, `slaba-kurpie-bez-uprawy` (.pdf + `-p1.png`).
- **6. Testy:** `tests/test_a5b2b.py` (20) + kontrakt werdyktu; poprawione asercje PDF w `test_a5b.py` (≤ 6 stron) i `test_a6.py`. 340 bez sieci.
**Pliki:** `backend/app/analysis/{verdict,soil_label,approx_area}.py` (nowe), `rules/verdict.yaml` (nowy), `rules/teren_gleba.yaml`, `rules/retencja.yaml`, `analysis/{terrain_interpret,facts,suggestions,water_balance,confidence,causes}.py`, `routers/{analysis,reports}.py`, `schemas/analysis.py`, `report/{builder.py,report.css,templates/report.html}`, testy; frontend: `api/types.ts`, `IrrigationCard.tsx`, `i18n.en.ts`, mocki.
**Kontrakt:** TAK (addytywnie) – `verdict`, `approximate_area`, `lon`/`lat`, `informacyjne`, `perennials` (`contract-changes.md`, „Dla Mefju”).
**Uwaga:** `vite build` nie przechodzi lokalnie ani w kontenerze – brak zainstalowanej `@fontsource-variable/fraunces` (z `package.json`, commit B); `tsc -b` przechodzi.

## 2026-11-21 22:40 · `a/backend` · A5b-2a: ranking „Co tu posiać?”, historia upraw, powierzchnia, status z percentyli
**Co:**
- **0. Dane C** (`git show origin/c/research:research/data/…`, bez merge) → `backend/app/data/crops/`. Ky żyta 0,80 i pszenżyta 0,90 – już zgodne. `uldk_demo.json` – brak. W kopii: + kolumny `root_depth_m`, `typ`; ziemniak `irrigation_practice` → common (decyzja Dominika), burak → not_practiced (z pliku C). `crops.py` czyta CSV; parametry 15 upraw bez zmian (sprawdzone asercją i 296 testami).
- **1. Ranking** (`suggestions.py`, `rules/ranking.yaml`): model wody × 17 upraw × 10 pełnych sezonów, FAO-33 (Ky faz tylko zweryfikowane), Ym = P90 GUS województwa × gleba, kalibracja do dobrego roku na przeciętnej glebie, kategorie, jedno zdanie, grupy polowe / wieloletnie, pewność. Kalibracja na żywo (NASA POWER, średnia symulowana vs średnia GUS, przeciętna gleba):

| Uprawa | podlaskie | lubelskie | wielkopolskie |
|---|---|---|---|
| pszenica ozima | +7% | −2% | −1% |
| żyto | +7% | −2% | +1% |
| pszenżyto | +6% | −4% | −2% |
| jęczmień ozimy / jary | +11% / +8% | −1% / −7% | +2% / 0% |
| owies | +6% | −8% | +1% |
| rzepak | +2% | +5% | −1% |
| kukurydza ziarno / kiszonka | −6% / −5% | −10% / −6% | −11% / −11% |
| ziemniak | −9% | −7% | −8% |
| burak cukrowy | +3% | −7% | −4% |
| strączkowe / łubin | −9% / −2% | −13% / −7% | −12% / −4% |
| warzywa | −1% | −8% | −7% |
| krzewy / truskawki | −3% / +17% | −7% / −1% | −5% / −10% |
| drzewa owocowe | +29% | +10% | +33% |

- **2–3.** `crop_history` (twarda przerwa → odradzane z powodem; miękkie ostrzeżenia / plusy), `cultivated_area_ha` (domyślnie działka × udział rolny IUNG), plon w tonach, `price = null`.
- **4.** Status poza sezonem / zimowanie / bez uprawy z porównania z tą samą datą w 10 latach; stan działki – goła gleba po 31 VII. 201305, 21.11.2026: bez uprawy 91% wody, „Dobrze” 70 (było „Ryzyko” 43); zboża ozime i rzepak – „w polu – zimowanie”, Dobrze 70; kukurydza – „poza sezonem”, Uwaga 50 (61% wody, mniej było w 1 z 10 lat; było „Ryzyko” 39 → 49); ziemniak, zboża jare – poza sezonem, Dobrze 70; drzewa owocowe – zimowanie, Uwaga 50; rzepak (jesień) – w sezonie, Dobrze 84.
- **5.** Kukurydza: bez dawek; 201305, 20.08.2019: „W tym sezonie brakuje ok. 62 mm wody; nawadnianie opłaca się tylko przy własnym źródle wody i deszczowni; pobór wody może wymagać pozwolenia wodnoprawnego – Wody Polskie”.
- Ranking 201305 (kat. III, kompleks 2, podlaskie, 0,58 ha, sezony 2017–2026): polecane – rzepak 3,5 t/ha, pszenica ozima 4,5 (słaby rok 2018: 3,8; ryzyko 1/10), jęczmień ozimy 4,2, jęczmień jary 4,1, pszenżyto 4,2, warzywa 22,1, kukurydza kiszonka 49,3, burak 64,7 (3/10), kukurydza ziarno 7,0 (3/10); możliwe – żyto 3,1 (gleba przeciętna dla żyta), łubin 1,9, owies 3,1, ziemniak 25,6 (4/10), strączkowe 1,9 (4/10); wieloletnie – drzewa 13,2, truskawki 5,8, krzewy 3,6. Z historią „rzepak 2 lata temu”: rzepak spada na koniec jako odradzany („…rosła tu 2 lata temu, a potrzeba 3 lat przerwy (kiła kapusty)”), reszta bez zmian.
- Kontrakt (addytywnie) + 3 przykłady; `npm run build` OK. Testy: **320 passed** bez sieci (+25 w `test_a5b2.py`, +1 przykład kontraktu; 1 nieaktualny test „dopisek optional” usunięty).
**Pliki:** `backend/app/data/crops/*`, `backend/app/analysis/{crops,suggestions,scoring,facts,field_state,water_balance}.py`, `backend/app/analysis/rules/{ranking,nawadnianie}.yaml`, `backend/app/routers/{analysis,reports}.py`, `backend/app/schemas/analysis.py`, `backend/tests/{test_a5b2,test_a5b,test_analysis,test_contract}.py`, `frontend/src/api/types.ts`, `frontend/src/mocks/analysis*.json`, `reports/examples/*.pdf`, `.ai/*`.
**Kontrakt API:** TAK (addytywnie) – `suggestions`, `crop_history`, `cultivated_area_ha`, `StatusScope.zimowanie` (osobny commit, `contract-changes.md`).

## 2026-11-21 21:50 · `a/backend` · A6: teren i spływ wody z NMT (port prototypu osoby C)
**Co:**
- Prototyp `research/terrain/` z `origin/c/research` pobrany przez `git show` (bez merge). Rdzeń (`analyze_surface`, D8 / D-infinity, priority-flood, strefy, odpływy, propozycje) – bez zmian w `analysis/terrain.py`; testy prototypu → `tests/test_terrain.py` (10, przechodzą). Pobieranie: `sources/nmt.py` (httpx async, POST ≤ 1000 punktów, x = PÓŁNOC, y = WSCHÓD, cache bez wygasania, bezpiecznik).
- Kontrakt (addytywnie): `terrain` + `terrain_note`, typy `Terrain*`; `/api/layers/teren` i `/api/layers/splyw` działają. Interpretacja (`terrain_interpret.py`): strefy z oceną gleba × teren (`rules/teren_gleba.yaml`), podsumowanie 2–3 zdania, fakty do reguł z progami oczka (D59), warstwy GeoJSON przycięte do działki i uproszczone.
- Reguły z terenu: oczko w zagłębieniu (główna) / „Do rozważenia: małe oczko przy odpływie”, zastawka (sprawdź rów), pas zieleni / zadrzewienie (E_MIOD), mokradło; `permit_note` w regule (oczko: „może wymagać zgłoszenia lub pozwolenia – Wody Polskie i starostwo”, bez niezweryfikowanych progów). Przyczyna „teren”, NMT w `reliability` i `/api/status`, PDF „Teren działki”.
- **Przekierowania (D56, dopisek do zadania):** wspólne `core/http.request` – bez `follow_redirects`, 3xx = blokada bez czytania treści, limity rozmiaru i czasu odczytu; ULDK, prognoza, NMT i `get_with_retry` przez nie. User-Agent „Wodoskop/0.1 (HackNation 2026)”. **Błąd znaleziony na żywo i naprawiony:** po odczycie strumieniowym odpowiedź gzip była dekodowana drugi raz (`/api/status` → 500, Open-Meteo / IUNG / mapa „DecodingError”) – testy na mockach tego nie łapały; dodane testy z prawdziwym gzip i uszkodzonym gzip.
- **NMT GUGiK odsyła 302 (jak ULDK i KIEG)** – porównania na żywo z wynikiem C nie było. Zapas: zapisane prawdziwe wyniki NMT osoby C z 21.11 (`app/data/terrain/`, 201305 i 061704), oznaczone w ograniczeniach, źródło „częściowo”; test sprawdza zgodność liczb z `facts.json`.
- Teren działek w cache (201305 – teren z zapisu C; 061704 – teren gotowy, działka czeka na ULDK):

| Działka | Strefy (górka / stok / płasko / dołek) | Gleba | Zdania dla rolnika | Rekomendacje z terenu |
|---|---|---|---|---|
| 201305_2.0038.6/1 (0,58 ha) | 0 / 56 / 12 / 32% | zwięzła (kat. III) | „56% działki to stok – po ulewie woda spływa po powierzchni i zabiera glebę.” · „12% działki jest płaska – tu są najlepsze warunki wodne.” · „32% działki to dołek – na zwięzłej glebie wiosną i po ulewach stoi tu woda, uprawy mogą wymakać.” | bez uprawy: „Sprawdź rów przy miejscu odpływu – zastawka” (ostrzeżenie), „Do rozważenia: małe oczko przy odpływie” (ostrzeżenie, nie w panelu); Susza 2018 – poza limitem 5 (pierwszeństwo: zatrzymanie wody zamiast nawadniania, odłóż nawożenie) |
| 061704_2.0011.383/2 (0,21 ha) | 0 / 49 / 48 / 3% | zwięzła (kat. IV) | „49% działki to stok – …zabiera glebę.” · „48% działki jest płaska – tu są najlepsze warunki wodne.” · „3% działki to dołek – …uprawy mogą wymakać.” | zastawka (odpływ 80%, dopływ 0,5 ha); oczko – brak (zlewnia 0,3 ha < 0,5 ha) |

- Ścieżka demo przy odciętej sieci (`--network none`, DEMO_OFFLINE, wolumen cache):

| Działka | Krok | HTTP | Czas | Wynik |
|---|---|---|---|---|
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Wyszukanie (id) | 200 | 0.00 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Wyszukanie (obręb numer) | 200 | 0.00 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Wyszukanie (punkt na mapie) | 200 | 0.00 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Analiza bez uprawy | 200 | 0.07 s | risk (43), pewność srednia; teren: stok 56%, płasko 12%, dołek 32% |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | PDF bez uprawy | 200 | 1.06 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Warstwa Teren | 200 | 0.06 s | 3 obiektów, 3 kB |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Warstwa Spływ wody | 200 | 0.03 s | 46 obiektów, 10 kB |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Analiza: Susza 2018 | 200 | 0.06 s | danger (8), pewność srednia; teren: stok 56%, płasko 12%, dołek 32% |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | PDF: Susza 2018 | 200 | 0.76 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Analiza: Mokry rok 2021 | 200 | 0.08 s | warn (59), pewność srednia; teren: stok 56%, płasko 12%, dołek 32% |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | PDF: Mokry rok 2021 | 200 | 0.78 s |  |

- Testy: **296 passed** bez sieci (+40: test_terrain 10, test_a6 27, test_contract 3 nowe – przykłady warstw i teren w przykładzie); `npm run build` OK.
**Pliki:** `backend/app/{analysis/{terrain,terrain_interpret,causes,confidence,facts,recommendations}.py,analysis/rules/{retencja,teren_gleba}.yaml,core/{http,config}.py,sources/{nmt,uldk,weather_openmeteo}.py,routers/{analysis,layers,status}.py,report/{builder,charts}.py,report/report.css,report/templates/report.html,schemas/{analysis,layers}.py,data/terrain/*}`, `backend/scripts/{warm_demo,demo_check}.py`, `backend/tests/{test_terrain,test_a6,conftest,test_a5,test_a5b,test_a5d,test_analysis,test_contract,test_demo_status_report}.py`, `backend/tests/fixtures/terrain_201305_research.facts.json`, `frontend/src/api/types.ts`, `frontend/src/mocks/{analysis.sample,analysis.no-crop.sample,layers.teren.sample,layers.splyw.sample}.json`, `reports/examples/*.pdf`, `.ai/*`.
**Kontrakt API:** TAK (addytywnie) – `terrain`, `terrain_note`, warstwy teren / spływ (osobny commit, `contract-changes.md`).

## 2026-11-21 21:00 · `a/backend` · A5d: odporność demo – trwały cache, działki bez ULDK, bezpiecznik, tryb offline
**Co:**
- **0. Trwały cache (D53):** `core/cache.py` – `TTLCache` = pamięć + jeden plik SQLite (`CACHE_DB`), wspólny dla wszystkich źródeł (ULDK, NASA POWER, Open-Meteo prognoza i archiwum, IUNG, KIEG, mapa glebowo-rolnicza, SoilGrids, ortofotomapa do PDF); czas ścienny; `ttl_s=None` = bez wygasania; plik niedostępny → sama pamięć (wcześniej wywracał start – znalezione na żywo: wolumen należał do roota, poprawione w Dockerfile). TTL: działki i gleba bez wygasania, pogoda zakończona > 7 dni temu bez wygasania, prognoza 1 h. NMT / BDOT10k / GUS – brak klientów (osoba C), warstwa gotowa.
- **1–2. Działki (D54):** indeks znanych działek (cache + `app/data/demo_parcels.json`: 5 działek, pełne dane 201305_2.0038.6/1, reszta `needs_fetch`); po id i po punkcie bez ULDK; „obręb numer” przy blokadzie – ze znanych.
- **3. Blokada ULDK:** 302 / 429 / HTML → ponowienia 1 s, 3 s → 502 + bezpiecznik 60 s; wspólny bezpiecznik na źródło; `/api/status` bez sondowania źródeł z otwartym bezpiecznikiem, „ograniczony (do HH:MM)” w czasie polskim; rozgrzewka nie pyta ULDK o znane działki.
- **4. DEMO_OFFLINE (D55):** zero zapytań zewnętrznych, brak w cache = 502 z komunikatem; `/api/demo/examples` filtruje niedziałające przykłady (offline / blokada ULDK). `scripts/warm_demo.py`, `scripts/demo_check.py`; `smoke_cached_uldk.py` usunięty. `docker-compose.yml`: wolumen `cache-data:/data`, `CACHE_DB`, `DEMO_OFFLINE`, montaż `scripts/` i `reports/`, `--reload-dir app`.
- **5. Testy:** `tests/test_a5d.py` (18) – zapis/odczyt i restart na tym samym pliku, TTL prognozy, pogoda bez wygasania, działka po punkcie z cache, działki demo bez sieci, blokada 302/429/HTML + bezpiecznik, status „ograniczony”, rozgrzewka bez ULDK, DEMO_OFFLINE (502, status bez sond, pełna ścieżka demo z cache bez żadnego zapytania), filtr przykładów; `conftest.py` – izolacja cache i bezpieczników między testami. **256 passed** w `docker run --network none`.
- **Na żywo:** `warm_demo.py` – ULDK zablokowany (061704: 3 próby → bezpiecznik, reszta pominięta bez zapytań); 201305: analiza bez uprawy + Susza 2018 + Mokry rok 2021 + PDF-y; cache: NASA 3, mapa glebowo-rolnicza 9, IUNG 1, SoilGrids 1, prognoza 1, ortofotomapa 1, ULDK 1, KIEG 0 (nie odpowiada). Restart kontenera – cache został (analiza 0,06 s). Kontener `--network none` + `DEMO_OFFLINE=true` + wolumen:

| Działka | Krok | HTTP | Czas | Wynik |
|---|---|---|---|---|
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Wyszukanie (id) | 200 | 0.00 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Wyszukanie (obręb numer) | 200 | 0.00 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Wyszukanie (punkt na mapie) | 200 | 0.00 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Analiza bez uprawy | 200 | 0.09 s | risk (43), pewność srednia |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | PDF bez uprawy | 200 | 0.99 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Analiza: Susza 2018 | 200 | 0.03 s | danger (8), pewność srednia |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | PDF: Susza 2018 | 200 | 0.59 s |  |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | Analiza: Mokry rok 2021 | 200 | 0.09 s | warn (59), pewność srednia |
| Wnory-Wandy 6/1 – przykłady „Susza 2018”, „Mokry rok 2021” | PDF: Mokry rok 2021 | 200 | 0.52 s |  |

  Przykłady offline: susza-2018, mokry-rok-2021.
- Zaległe z A5b-1 (smoke na wszystkich przykładach, PDF-y kukurydza/las, 061704) – nadal czekają na ULDK (status).
**Pliki:** `backend/app/core/{cache,config,http}.py`, `backend/app/sources/{uldk,weather_power,weather_openmeteo,iung,kieg,soil_map,soilgrids}.py`, `backend/app/routers/{status,demo}.py`, `backend/app/{demo,main}.py`, `backend/app/report/builder.py`, `backend/app/analysis/confidence.py`, `backend/app/data/demo_parcels.json`, `backend/scripts/{warm_demo,demo_check}.py` (−`smoke_cached_uldk.py`), `backend/tests/{conftest,test_a5d,test_demo_status_report}.py`, `backend/{Dockerfile,CLAUDE.md}`, `docker-compose.yml`, `.env.example`, `reports/examples/*.pdf`, `.ai/*`.
**Kontrakt API:** NIE (stan ULDK w istniejącym polu `ServiceStatus.error`; `/api/demo/examples` – ten sam format, krótsza lista offline).

## 2026-11-21 20:30 · `a/backend` · A5b-1: stan działki bez uprawy, nawadnianie wg praktyki, ekoschematy, status poza sezonem, zgodność gleby
**Co:**
- **1. Nawadnianie (D48):** `Crop.irrigation_practice` (not_practiced: zboża, rzepak, strączkowe; optional: kukurydza, burak, tytoń; common: ziemniak, warzywa, sady, owoce miękkie, chmiel). `not_practiced` → `irrigation.status = nie_praktykowane`, bez dawek; silnik pomija kategorię „nawadnianie”; 3 reguły zastępcze przy stresie ≤ 7 dni (`retencja.bez_nawadniania_zatrzymaj_wode`, `agrotechnika.bez_nawadniania_parowanie`, `agrotechnika.bez_nawadniania_termin_zabiegow`) ze zdaniem „Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie”. `optional` – dopisek w planie dawek.
- **2. Ekoschematy (D51):** katalog = E_MPW, E_USU, E_WSG, E_PN, E_MIOD, E_EKSTUZ; usunięte E_ZSU, plan nawożenia i TUZ bez kodu; „Odłóż nawożenie” bez ekoschematu; kod spoza listy = `RuleError`.
- **3. Status poza sezonem (D52):** `scoring.reserve_status` – 0,6 × woda w profilu + 0,4 × pozycja KBW 30 dni wśród 10 lat (`water_balance.recent_balance`); `OverallStatus.scope/scope_label`. „Kukurydza dziś” (zastępczo 201305): 39 → **49, „poza sezonem”**, bez kar za historię sezonu i stres.
- **4. Gleba (D49):** `analysis/soil_consistency.py` + `soil_map.soil_map_for_parcel` (9 punktów). Badanie 201305: działka na dwóch konturach (piasek gliniasty lekki – kompleks 6 / glina lekka pylasta – kompleks 2), IUNG 75% III / 25% I – **zgodne**; „konflikt” był skutkiem jednego punktu. Porównanie udziałów gleb lekkich (> 40 p.p. = konflikt), przy konflikcie kategoria i WOD z mapy, −10 pkt pewności; bez IUNG – mapa / SoilGrids.
- **5. Bez uprawy (D50):** `analysis/field_state.py` – pokrycie referencyjne FAO-56 (trawa, Kc 1, p 0,5, profil 1 m), przebieg od 1 XI z pasmem 10 lat, ranking dnia, KBW 30 dni; `/api/analysis` i `/api/report.pdf` bez `crop` (PDF „Stan wodny działki”, `stan-wodny-dzialki-….pdf`); `field_state` liczone zawsze; 3 reguły retencji bez uprawy wg pory roku; `suggestions = null` pod A5b-2.
- **Kontrakt** (wpis A5b-1, „Dla Mefju”) + minimalne poprawki typów w 5 plikach `frontend/` (za zgodą właściciela) – `npm run build` OK (w kontenerze po `npm install`; obraz frontendu nie ma Fraunces).
- **ULDK GUGiK odpowiadał 302 (ograniczenie ruchu) przez całą sesję** → `scripts/smoke_cached_uldk.py`: smoke w procesie z zapisaną odpowiedzią ULDK dla 201305 (fikstura), reszta źródeł na żywo. Działki wymagające ULDK – 502 (do powtórki, status „Do zrobienia na żywo”).
- Testy: 238 bez sieci (`docker run --network none`), w tym `tests/test_a5b.py` (29) i przykład bez uprawy w `test_contract`.
- Smoke A5b-1:

| Przykład | Uprawa | Status | Wynik | Zaleceń | Nawadnianie | Ekoschematy | soil.consistency |
|---|---|---|---|---|---|---|---|
| Susza 2018 | zboża ozime | danger – w sezonie | 8 | 5 | nie (nie_praktykowane) | E_MPW | ok |
| Mokry rok 2021 | zboża ozime | warn – w sezonie | 59 | 2 | nie (nie_praktykowane) | E_MPW, E_WSG | ok |
| Kukurydza – stan dziś | kukurydza_ziarno | błąd 502 | – | – | – | – | – |
| To nie jest pole | zboza_ozime | błąd 502 | – | – | – | – | – |
| Stan działki (bez uprawy) | — (bez uprawy) | risk – stan wody na działce | 43 | 2 | nie (brak sekcji) | E_USU, E_WSG | ok |
| Stan działki 10.06.2018 (bez uprawy) | — (bez uprawy) | danger – stan wody na działce | 18 | 2 | nie (brak sekcji) | E_USU, E_WSG | ok |
| 201305_2.0038.6/1 | zboża ozime | ok – poza sezonem | 71 | 3 | nie (nie_praktykowane) | E_WSG | ok |
| 061704_2.0011.383/2 | kukurydza_ziarno | błąd 502 | – | – | – | – | – |
| 040703_5.0020.76 | zboza_ozime | błąd 502 | – | – | – | – | – |
| 302114_5.0018.445 | zboza_ozime | błąd 502 | – | – | – | – | – |
| 160703_5.0011.945 | zboza_ozime | błąd 502 | – | – | – | – | – |
| 143203_2.0027.112/11 | zboza_ozime | błąd 502 | – | – | – | – | – |

  PDF-y: `reports/examples/susza-2018.pdf` (5 str.), `mokry-rok-2021.pdf` (4), **`stan-dzialki-bez-uprawy.pdf`** (4, nowy); `kukurydza-dzis.pdf` i `to-nie-jest-pole.pdf` – jeszcze z A5 (ULDK).
**Pliki:** `backend/app/analysis/{crops,facts,scoring,confidence,recommendations,water_balance,field_state,soil_consistency}.py`, `backend/app/analysis/rules/*.yaml`, `backend/app/sources/soil_map.py`, `backend/app/routers/analysis.py`, `backend/app/report/{builder,charts}.py`, `backend/app/report/templates/report.html`, `backend/app/schemas/analysis.py`, `backend/scripts/{smoke,smoke_cached_uldk}.py`, `backend/tests/{test_a5b,test_a5,test_analysis,test_contract,test_demo_status_report,test_water_model}.py`; `frontend/src/api/types.ts`, `frontend/src/mocks/{analysis.sample,analysis.no-crop.sample}.json`, `frontend/src/{features/parcel-panel/IrrigationCard,features/parcel-panel/ParcelPanel,features/passport/SectionD,layout/cards/AlertsCard}.tsx`, `frontend/src/lib/{storage,i18n.en}.ts`; `reports/examples/*.pdf`; `.ai/*`.
**Kontrakt API:** TAK – `crop`/`crop_season`/`irrigation` mogą być null, `field_state`, `suggestions`, `OverallStatus.scope(_label)`, `Soil.consistency`, `IrrigationStatus.nie_praktykowane`, `IrrigationPlan.practice` (osobny commit, `contract-changes.md`).

## 2026-11-21 19:30 · `integracja` · INT1: połączenie a/backend + b/frontend (bez main)
**Co:**
- Gałąź `integracja` od `origin/main` (kamień milowy 1) + `origin/b/frontend` (B10, B11 – bez konfliktów) + `origin/a/backend` (A5, `bb2df36`).
- Jedyny konflikt: `.ai/decisions.md` – obie strony zajęły D40. D40–D46 zostają u A, przełącznik języka B przenumerowany na **D47** (dopisek o historii numeru); odwołania „(D40)” w komentarzach `i18n.ts`, `i18n.en.ts`, `LanguageProvider.tsx`, `LanguageToggle.tsx` → „(D47)”. Status i dziennik B nadal piszą D40 – do poprawy przez B.
- `backend/`, `types.ts`, `analysis.sample.json` = dokładnie `a/backend`; `frontend/` (poza 4 komentarzami) i `design/` = dokładnie `b/frontend`. B nic własnego do kontraktu nie dodał.
- Weryfikacja: `pytest` w kontenerze bez sieci z zamontowanym `frontend/` – 210 passed (5 live pominięte); `npm run build` – OK bez poprawek; `docker compose up --build` lokalnie na 8001/5174 (8000/5173 zajęte przez drugi klon; override poza repo): `/api/health` 200, `/api/analysis` (201305_2.0038.6/1, zboza_ozime, 2018-06-10) 200 – „Susza”, 5 rekomendacji, nawadnianie zalecane; zimna analiza 2019-06-10 – 1,6 s; `/api/report.pdf` 200 (165 kB, 1,6 s); frontend 200, proxy `/api` 200. `/api/status`: KIEG i SoilGrids chwilowo niedostępne (zewnętrzne).
- Rozjazdy UI ↔ kontrakt A5 przekazane osobie B (lista w odpowiedzi INT1): rekomendacje bez `when_label`/`permit`/`warning`/`eco_scheme`, gleba bez `texture`/`permeability`/`soil_map`, brak wyboru przedplonu i `previous_crop` w zapytaniach, przykłady lokalne zamiast `/api/demo/examples`, `/api/status` nieużywane, 404 z `/api/report.pdf` pokazywane jako „w budowie”.
**Pliki:** `.ai/decisions.md`, `.ai/log/a-backend.md`, `.ai/status/a-backend.md`, 4 komentarze we `frontend/src/{lib,components}` + pliki obu gałęzi z merge.
**Kontrakt API:** nie (kontrakt bez zmian – wersja A5 z `a/backend`).

## 2026-11-21 18:30 · `a/backend` · A5: konsultacja z mentorem + gotowość do 3-minutowej oceny
**Co:**
- A0: `docs/kowr/*.pdf` (treść zadania, podstawy naukowe, regulamin); D40 – wnioski z konsultacji (prof. Gozdowski).
- A1–A7: reguły przejrzane wg „Podstaw naukowych” (23: retencja 13, agrotechnika 8, nawadnianie 2; 4 czekają na teren). Silnik: `timing` (teraz / po zbiorze / przed następnym sezonem), `permit` (none/maybe/required + Wody Polskie), `eco_scheme` (E_MPW, E_USU, E_WSG, E_ZSU, plan nawożenia), `fertilization`, operator `exists`; wybór: panel 3, paszport 5, niepewne z ostrzeżeniem i nigdy pierwsze. Retencja zawsze (test 15 upraw × 12 miesięcy). „Odłóż nawożenie” przy silnym stresie. Płodozmian z `previous_crop`.
- A8: SoilGrids (`sources/soilgrids.py`), klasa uziarnienia USDA po polsku, Ksat Saxton–Rawls, woda z ulewy (`analysis/soil_texture.py`); mapa glebowo-rolnicza GUGiK sprawdzona na żywo – działa (`sources/soil_map.py`): kompleks, gatunek, warstwy, typ, rok mapy.
- A9: kontrakt (osobny commit 798d5aa) + mock = prawdziwa odpowiedź „Susza 2018” z przedplonem.
- B1–B5: `app/demo.py`, `GET /api/demo/examples`, rozgrzewka w `lifespan` (co 6 h, `DEMO_WARMUP`), `GET /api/status`, `GET /api/report.pdf` (WeasyPrint + Jinja2 + segno, Inter OFL; Dockerfile: Pango, HarfBuzz). Cache: TTL na wpis, przeterminowany wpis przy awarii (pewność −1).
- Znalezione na żywo i naprawione: ULDK odsyła 302 → `resp/uldk.php` z pozornym „0” → było 404 „nie znaleziono działki” (teraz ponowienia na nowym połączeniu, 502 przy porażce); KIEG wisiał do 26 s (twardy limit na źródło + bezpiecznik); SoilGrids chwilami nie odpowiada (12 s, bezpiecznik 5 min); nagłówek „mniejszy zapas niż zwykle” przy bilansie lepszym niż zwykle (poprawione).
- C: `backend/scripts/smoke.py`, `reports/examples/*.pdf` (4). Smoke 10/10 OK (analiza po rozgrzewce 0,01–0,05 s, na zimno do 7,7 s; PDF 1,1–2,5 s).
**Pliki:** `backend/app/{demo.py,main.py}`, `backend/app/analysis/{facts,recommendations,confidence,scoring,soil_texture,water_balance}.py`, `backend/app/analysis/rules/*.yaml`, `backend/app/core/{cache,config}.py`, `backend/app/sources/{soilgrids,soil_map,uldk,iung,kieg,weather_power,weather_openmeteo}.py`, `backend/app/routers/{analysis,demo,status,reports}.py`, `backend/app/report/*`, `backend/app/schemas/{analysis,demo,status}.py`, `backend/{requirements.txt,Dockerfile}`, `backend/scripts/smoke.py`, `backend/tests/{conftest,test_a5,test_demo_status_report,test_analysis}.py`, `frontend/src/api/types.ts`, `frontend/src/mocks/analysis.sample.json`, `docs/kowr/*`, `reports/examples/*`, `.env.example`.
**Kontrakt API:** TAK – pola rekomendacji, gleby, `previous_crop`, nowe endpointy (osobny commit, `contract-changes.md`).

## 2026-11-21 17:18 · `a/backend` · A4: ocena, pewność, przyczyny, rekomendacje, pełne /api/analysis (kamień milowy 1)
**Co:**
- `requirements.txt` (osobny commit): PyYAML. Kontrakt (osobny commit 738415c): `Recommendation.priority`, `in_panel`. Mock (osobny commit 612509d): zapis prawdziwej odpowiedzi.
- `analysis/facts.py` – wspólne fakty (opis, jednostka, źródło) dla oceny, przyczyn i reguł; `water_balance.season_sums()` – opad i ET0 sezonu vs średnia 10 lat.
- `analysis/scoring.py` – wskaźnik 0–100 (woda 45/65%, ryzyko 35%, historia 20/35%), progi 70/50/30, poza fazami wrażliwymi najwyżej „risk” i nagłówki o zapasie wody w glebie; zdanie podsumowania z liczbami; grunt nierolny → no_data.
- `analysis/confidence.py` – pewność punktowa z jawnych przesłanek (satelita, teren, źródło i opóźnienie pogody, Hargreaves, prognoza, gleba), progi 75/50, bez satelity/terenu najwyżej „średnia”; źródła z datą i statusem, kompletność, ograniczenia.
- `analysis/causes.py` – opady, parowanie, gleba, wymagania uprawy (udziały, suma 100%), teren – brak danych bez udziału.
- `analysis/recommendations.py` + `analysis/rules/{retencja,agrotechnika,nawadnianie}.yaml` – 19 reguł (11/6/2), 4 wyłączone (`requires: terrain / water_nearby`); fakt None → warunek fałszywy, brak liczby w tekście → reguła pominięta; „Dlaczego?” i dane wejściowe z faktów, które uruchomiły regułę; kolejność grup, `in_panel` – najważniejsza z grupy.
- `routers/analysis.py` – pełne `GET /api/analysis` (budżet 27 s, limity na źródło, kroki z czasami, 422 bez uprawy / zła data, 502 tylko bez ULDK lub pogody); `/api/dev/*` zostają (tymczasowe).
- Testy: `tests/test_analysis.py` (35 + live), `test_contract` – zamiast 501 test walidacji (stary test wykonywał prawdziwe zapytanie sieciowe!). Cały pakiet sprawdzony w kontenerze bez sieci.
- Live:
  - 201305 · zboża ozime · 2018-06-10 – **danger (8)** „Susza – rośliny cierpią z braku wody”; „Gleba ma 17% wody dostępnej w strefie korzeni, a od 1 marca bilans wody wynosi −111 mm – o 90 mm mniej niż zwykle.”; przyczyny: opady 36%, gleba 24%, uprawa 21%, parowanie 19%, teren 0%; panel: odmiany odporne, „Nawadnianie teraz: 27,5 mm…, 3 dawki”; pewność średnia (3/6 źródeł); 2,5 s (pogoda 2,2 s).
  - 201305 · zboża ozime · dziś – **ok (71)** „zapas wody w glebie w normie” (98% profilu; bilans sezonu −228 mm, o 154 mm mniej niż zwykle); panel: odmiany odporne (27 vs 17,2 dni stresu); pewność średnia (4/7); 1,7 s.
  - 061704 · kukurydza · 2021-07-15 – **warn (69)**; 71% wody, stres za ok. 16 dni; przyczyny: uprawa 50%, gleba 27%, opady 23%; panel: „Przygotuj nawadnianie”; 2,0 s.
  - 143203 · las · dziś – **no_data** „Ocena suszy rolniczej nie dotyczy tej działki”, bez przyczyn i rekomendacji; 1,2 s.
**Pliki:** `backend/app/analysis/{facts,scoring,confidence,causes,recommendations,water_balance}.py`, `backend/app/analysis/rules/*.yaml`, `backend/app/routers/analysis.py`, `backend/tests/{test_analysis,test_contract}.py`, `backend/requirements.txt`; kontrakt i mock.
**Kontrakt API:** TAK – `Recommendation.priority`, `in_panel` (osobny commit, `contract-changes.md`).

## 2026-11-21 16:40 · `a/backend` · A3b: ciągły bilans, fazy upraw, realistyczne nawadnianie, stan wody poza sezonem
**Co:**
- Kontrakt (osobny commit acdf4da): `crop_season`, `soil_water` (zakres, opis, porównanie z tym samym dniem w 10 latach, podsumowanie zakończonego sezonu), `irrigation` (status, komunikat, dawka ≤ 35 mm, termin, częstotliwość, łączny niedobór 7 dni).
- `analysis/crops.py`: terminy zbioru (PL), fazy FAO przeskalowane do siew–zbiór, typ uprawy (jara / ozima / jesienna / wieloletnia), siew jesienny ozimin, `day_info()` na każdy dzień roku (Kc, Zr, faza, wrażliwość, goła gleba), liniowy wzrost korzeni.
- `analysis/water_balance.py`: ciągły bilans od 1 XI (1 VII) roku poprzedzającego sezon do dnia przed analizą; profil 1 m = strefa czynna + warstwa dolna (przenoszenie wody przy zmianie Zr); goła gleba Kc 0,35 × Kr (FAO-56 równ. 74); spoczynek Kc 0,4; nadmiar → warstwa dolna → przesiąkanie; stan początkowy z bilansu 92 dni przed oknem; dni stresu tylko w fazach wrażliwych; ryzyko i nawadnianie tylko w fazach wrażliwych; harmonogram dawek w 7 dniach (min. 2 dni odstępu); stan wody na każdą datę z opisem i rankingiem 10 lat; `history_range` od 1 VIII (rok − 12).
- `routers/analysis.py`: `/api/dev/water` w nowym formacie (`crop_season`, `soil_water`, `irrigation`).
- Testy: `tests/test_water_model.py` przepisany (42 przypadki + live).
- Live (dev/water):

| działka | uprawa | data | faza | woda % | mm | dni stresu | vs śr. 10 lat | ryzyko 7 dni | nawadnianie | czas |
|---|---|---|---|---|---|---|---|---|---|---|
| 201305 | zboża ozime | 2018-07-15 | dojrzewanie | 42 (strefa) | 70 | 35 | 35 vs 10,4 | nie dotyczy | nieuzasadnione w tej fazie | 2,0 s |
| 201305 | zboża ozime | 2021-07-15 | dojrzewanie | 59 (strefa) | 98 | 5 | 5 vs 13,2 | nie dotyczy | nieuzasadnione w tej fazie | 1,6 s |
| 201305 | zboża ozime | 2026-11-21 | spoczynek zimowy | 98 (profil) | 164 | 27 | 27 vs 17,2 | nie dotyczy | nieuzasadnione w tej fazie | 1,7 s |
| 201305 | kukurydza | 2018-07-15 | pełnia rozwoju | 69 (strefa) | 114 | 0 | 0 vs 1,3 | niskie | niepotrzebne | 0,03 s |
| 201305 | kukurydza | 2021-07-15 | pełnia rozwoju | 82 (strefa) | 136 | 0 | 0 vs 1,6 | niskie | niepotrzebne | 0,02 s |
| 201305 | kukurydza | 2026-11-21 | po zbiorze | 61 (profil) | 102 | 28 | 28 vs 16,0 | nie dotyczy | nieuzasadnione w tej fazie | 0,03 s |
| 061704 | zboża ozime | 2018-07-15 | dojrzewanie | 37 (strefa) | 76 | 29 | 29 vs 3,6 | nie dotyczy | nieuzasadnione w tej fazie | 2,1 s |
| 061704 | zboża ozime | 2021-07-15 | dojrzewanie | 50 (strefa) | 102 | 0 | 0 vs 6,4 | nie dotyczy | nieuzasadnione w tej fazie | 1,6 s |
| 061704 | zboża ozime | 2026-11-21 | spoczynek zimowy | 73 (profil) | 149 | 31 | 31 vs 9,1 | nie dotyczy | nieuzasadnione w tej fazie | 1,7 s |
| 061704 | kukurydza | 2018-07-15 | pełnia rozwoju | 80 (strefa) | 164 | 0 | 0 vs 0,5 | niskie | niepotrzebne | 0,02 s |
| 061704 | kukurydza | 2021-07-15 | pełnia rozwoju | 71 (strefa) | 145 | 0 | 0 vs 0,8 | niskie | niepotrzebne | 0,02 s |
| 061704 | kukurydza | 2026-11-21 | po zbiorze | 57 (profil) | 116 | 30 | 30 vs 19,1 | nie dotyczy | nieuzasadnione w tej fazie | 0,03 s |

  Dodatkowo: pszenica 2018-06-10 (pełnia, stres) → „27,5 mm teraz, powtórz za ok. 2 dni (w 7 dniach 3 dawki, niedobór ok. 70 mm)” (201305, kat. III) / 32,5 mm (061704, kat. IV). Kukurydza 2018 cały sezon (2018-10-11): 5 vs 20,8 (201305), 1 vs 18,8 (061704) – **niezgodne z oczekiwaniem „2018 > średnia”**: wilgotna jesień 2017 (bilans VIII–X +164 mm) wypełniła profil, kukurydza ma mały popyt do VII i korzenie sięgają wilgotnej warstwy dolnej → do kalibracji z IUNG SMSR (status, „Następne” 3).
**Pliki:** `backend/app/analysis/{crops,water_balance,soil}.py`, `backend/app/routers/analysis.py`, `backend/tests/{test_water_model,test_weather_history}.py`; kontrakt: `backend/app/schemas/analysis.py`, `frontend/src/api/types.ts`, `frontend/src/mocks/analysis.sample.json`.
**Kontrakt API:** TAK – `crop_season`, `soil_water`, `irrigation` (osobny commit, wpis w `contract-changes.md`).

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
