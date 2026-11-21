# Projekt: „Zatrzymaj wodę” – HackNation 2026, zadanie KOWR

Aplikacja webowa dla rolnika (bez wiedzy GIS): podaje działkę ewidencyjną (numer / klik na mapie / GPS), uprawę i datę analizy → w < 30 s dostaje ocenę sytuacji wodnej (dane z 10 lat), przyczyny i rekomendacje w kolejności: **RETENCJA → AGROTECHNIKA → NAWADNIANIE**, plus raport PDF.

## Twarde wymagania KOWR (ocena jury)

- Działa dla DOWOLNEJ działki w Polsce i DOWOLNEJ daty z ostatnich 10 lat (jury samo wpisuje i porównuje z danymi referencyjnymi). Dla daty historycznej używamy **tylko danych sprzed tej daty**.
- Wynik < 30 s. Wszystkie źródła pobieramy równolegle, z timeoutem i cache; awaria jednego źródła obniża „pewność”, ale nie wywraca analizy.
- Wszystko LICZONE z pobranych danych – żadnych gotowych tekstów rekomendacji. LLM nie liczy niczego.
- Przy każdym wyniku: źródło, data danych, ograniczenia i niepewność; braki danych komunikowane wprost.
- Raport do zapisania jako PDF / wydruk. Działa w przeglądarce bez instalacji, mile widziany telefon.
- Bez danych osobowych. Tylko licencje permisywne (MIT/BSD/Apache) – bez GPL/AGPL; czcionki – dopuszczalna licencja SIL OFL 1.1 (Inter).
- Kryteria: wartość praktyczna 25%, dane i wiarygodność 25%, innowacyjność 20%, prostota obsługi 15%, prototyp/jakość 15%.

## Stack

- **Backend:** Python 3.12, FastAPI, httpx (async), numpy, shapely, pyproj, rasterio (Sentinel), SQLite (cache, zgłoszenia), WeasyPrint (PDF).
- **Frontend:** React + Vite + TypeScript + Tailwind v4 + shadcn/ui + Leaflet (react-leaflet) + Recharts.
- **Uruchamianie:** wyłącznie `docker compose up` (backend :8000, frontend :5173, proxy `/api`).

## Źródła danych (sprawdzone na żywo – trzymaj się tych szczegółów)

1. **ULDK GUGiK** https://uldk.gugik.gov.pl/ – działki.
   - `request=GetParcelById` (pełny id, np. `143203_2.0027.112/11`), `GetParcelByIdOrNr` (np. „Szczytno 112/11”, może zwrócić kilka wyników), `GetParcelByXY` (`xy=lon,lat,4326`).
   - `result=geom_wkt,id,voivodeship,county,commune,region,parcel`, `srid=2180`.
   - Odpowiedź tekstowa: 1. linia kod (>= 0 OK, -1 = brak wyników), dalej rekordy z polami rozdzielonymi `|`. WKT może mieć prefiks `SRID=2180;`.
   - Geometria w 2180 jako (wschód, północ). CORS `*`.
2. **NASA POWER** https://power.larc.nasa.gov/api/temporal/daily/point – pogoda 10 lat (ok. 1,6 s).
   - `parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN`, `community=AG`, `format=JSON`.
   - Braki = `-999`. Rozdzielczość ~50 km.
3. **Open-Meteo** https://api.open-meteo.com/v1/forecast – prognoza 16 dni (`precipitation_sum`, `et0_fao_evapotranspiration`).
   - Archiwum (archive-api.open-meteo.com, ERA5-Land ~10 km) ma limit dzienny na IP – w sieci hackathonu zwraca 429; traktuj jako źródło opcjonalne z fallbackiem na NASA POWER.
4. **ET0 liczymy sami:** FAO-56 Penman-Monteith; gdy brak promieniowania/wilgotności/wiatru – Hargreaves (oznacz metodę). **KBW = opad − ET0.**
5. **IUNG – gleby:** WMS https://sgeo.iung.pl/geoserver/Susza/wms, warstwa `Susza:katgl_landuse2024`, GetFeatureInfo (WMS 1.3.0, CRS EPSG:4326 ⇒ BBOX w kolejności **lat,lon**, `INFO_FORMAT=application/json`, wartość w `properties.GRAY_INDEX`).
   - Kody: 1 kat. I bardzo podatna (WOD < 127,5 mm), 2 kat. II (127,5–169,9), 3 kat. III (170–202,5), 4 kat. IV (> 202,5), 5 gleby organiczne, 11 lasy, 12 wody, 13 zabudowa, 14 drogi/nieużytki, 19/99 niesklasyfikowane, 0/255 brak.
   - Działkę próbkujemy kilkoma punktami w obrysie → udziały kategorii. Kody 11–14 = „to nie jest grunt rolny”.
6. **EGiB / KIEG** https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow – klasy bonitacyjne (GetFeatureInfo, warstwy `kontury,uzytki`, `text/html`, pole „Oznaczenie konturu”, np. `RIIIa`, `PsIII`). Tylko część powiatów – informacja dodatkowa, nie podstawa obliczeń.
7. **NMT GUGiK** https://services.gugik.gov.pl/nmt/ – wysokości ±0,1 m.
   - `request=GetHByPointList&list="x y,x y,..."` w EPSG:2180 z kolejnością **x = PÓŁNOC, y = WSCHÓD (odwrotnie niż ULDK!)**.
   - GET do ~400 punktów (dłuższy URL → 414), POST z `list=...` zwraca max 1000 punktów (~2,5 s).
   - Służy do: spadki, górki, dołki (zagłębienia bez odpływu), kierunki spływu, miejsce odpływu z działki, TWI. Liczymy sami w numpy (bez bibliotek GPL).
8. **BDOT10k WMS** https://mapy.geoportal.gov.pl/wss/service/pub/guest/kompozycja_BDOT10k_WMS/MapServer/WMSServer
   - Warstwy: `row` (rów melioracyjny), `rz` (rzeka/strumień), `kan` (kanał), `rzOk`, `kanOkr` (okresowe), `WPow` (woda powierzchniowa).
   - GetMap PNG wokół działki (0,3–1,5 s) → odległość do najbliższego obiektu; GetFeatureInfo `INFO_FORMAT=text/xml` zwraca `x_kod` (np. `SWRS` = rzeka/strumień, `SWRM` = rów melioracyjny) i datę aktualizacji.
9. **Sentinel-2:** Earth Search STAC https://earth-search.aws.element84.com/v1/search, kolekcja `sentinel-2-l2a`, assety `red`, `nir`, `swir16`, `scl` (COG, odczyt fragmentów przez rasterio).
   - Dane od 2017 – rok 2016 brak; dla 2016 Copernicus Data Space STAC https://stac.dataspace.copernicus.eu/v1.
   - NDVI, NDMI, maska chmur SCL, anomalia względem tych samych okresów z poprzednich lat.
10. **IUNG SMSR** https://susza.iung.pulawy.pl – oficjalna metodyka suszy (KBW, kategorie gleb, 15 upraw: zboża ozime, zboża jare, kukurydza na ziarno, kukurydza na kiszonkę, rzepak i rzepik, rzepak i rzepik (jesień), ziemniak, burak cukrowy, rośliny strączkowe, warzywa gruntowe, drzewa owocowe, krzewy owocowe, truskawki, chmiel, tytoń). Używamy tej listy upraw i kalibrujemy wyniki do tej metodyki.
11. **GUS BDL API** https://bdl.stat.gov.pl/api/v1 – plony z ha i ceny skupu wg województw (np. zmienna 4332 = plony pszenicy dt/ha; temat P2967 = miesięczne ceny pszenicy zł/dt). `/data/by-variable/{id}?unit-level=2&year=...&format=json`.
12. **Ortofotomapa Geoportal** (WMS) jako podkład mapy.

## Funkcje (kolejność budowy)

- **P0:** wyszukanie działki (numer, obręb+numer, klik, GPS) → pogoda 10 lat + ET0/KBW → gleba IUNG → model wody w glebie FAO-56 (bucket: % wody dostępnej, dni stresu w każdym z 10 lat, „stres za X dni” z prognozy) → ocena + pewność + przyczyny → silnik reguł (YAML: warunek → rekomendacja → dane, które ją uruchomiły) → raport PDF.
- **P1:** Sentinel-2 NDVI/NDMI + wskaźnik pewności (zgodność modelu z satelitą).
- **P2:** teren z NMT (strefy: sucha górka / stok / mokry dołek, strzałki spływu, miejsce odpływu) + woda w okolicy (BDOT10k) + zgłoszenia rolników o stanie rowów i zbiorników (formularz, mapa stanu, generowane pismo do pobrania: ciek → Wody Polskie, rów → właściciel/spółka wodna; nic nie jest wysyłane automatycznie).
- **P3:** symulator „co jeśli” (międzyplony → więcej próchnicy → mniej dni stresu), porównanie upraw, kontekst plonów z GUS, wiele działek, tryb rolnik/doradca.

## Docelowy wygląd (`design/ref-desktop.png`, `design/ref-mobile.png`, `design/ref-style.png`)

- Jasny, czysty interfejs: lewy wąski pasek nawigacji; u góry wyszukiwarka działki, przycisk „Moja lokalizacja”, pogoda i wybór DATY ANALIZY.
- Pełnoekranowa ortofotomapa z obrysem działki i kolorową mapą NDVI/strefami w obrysie.
- Przełączniki warstw jako „pigułki”: Kondycja upraw, Wilgotność, Teren, Spływ wody, Gleba, Rowy i zbiorniki.
- Prawy panel działki: status (dobry / umiarkowany / wysoki / ekstremalny stres), wilgotność gleby z paskiem, ryzyko wodne na 7 dni, rekomendacje, przycisk „Pobierz raport”.
- Dolny pasek kart: przegląd gospodarstwa, trend, alerty, prognoza.
- Wersja mobilna: mapa na pełnym ekranie, legendy warstw jako małe ciemne karty, panel działki wysuwany od dołu.
- Zielona, spokojna kolorystyka, duże czytelne elementy. Własna marka „Zatrzymaj wodę” – nie kopiujemy nazw z grafik.

## Wygląd

Wygląd i zachowanie interfejsu definiuje **`design/SPEC_UI.md`** razem z grafikami w `design/` (`ref-desktop.png`, `ref-mobile.png`, `ref-style.png`). Przy każdej zmianie UI trzymaj się go dokładnie – niczego nie upraszczaj ani nie pomijaj. Jeśli czegoś nie da się zrobić, napisz to wprost.

## Pamięć projektu (obowiązkowe)

Katalog `.ai/` to wspólna pamięć między sesjami i osobami. Zasady szczegółowe: `backend/CLAUDE.md`, `frontend/CLAUDE.md`.

- **Jeśli nie wiesz, która osoba pracuje (A – Dominik, backend / B – Mefju, frontend) – zapytaj na początku sesji.**
- **NA POCZĄTKU każdego zadania** przeczytaj: `.ai/status/` (oba pliki), ostatnie 5 wpisów z `.ai/log/<twoja-osoba>.md` (wpisy od najnowszego), `.ai/decisions.md`, a przy pracy z API – `.ai/contract-changes.md`. Działki do testów: `.ai/test-parcels.md`.
- **NA KOŃCU każdego zadania (przed commitem):** zaktualizuj `.ai/status/<twoja-osoba>.md`, dopisz wpis na górze `.ai/log/<twoja-osoba>.md` (data i godzina, gałąź, co zrobiono, zmienione pliki, czy zmieniono kontrakt API). Jeśli podjęto decyzję projektową – dopisz do `.ai/decisions.md`. Jeśli zmieniono kontrakt – dopisz do `.ai/contract-changes.md` i zaktualizuj oba pliki kontraktu (`backend/app/schemas/`, `frontend/src/api/types.ts`).
- Osoba A edytuje tylko pliki `*a-backend.md`, osoba B tylko `*b-frontend.md` – żeby nie było konfliktów. `decisions.md` i `contract-changes.md` zmieniane w osobnym małym commicie.

## Praca zespołowa

- **Osoba A (Dominik) = `backend/`**, **osoba B (Mefju) = `frontend/`**.
- **Kontrakt API** = `backend/app/schemas/` + `frontend/src/api/types.ts`. Zmiany tylko po uzgodnieniu i **w obu miejscach naraz**. Przykład odpowiedzi analizy: `frontend/src/mocks/analysis.sample.json` – test `backend/tests/test_contract.py` sprawdza go modelem Pydantic (`extra="forbid"`) i czy każde pole jest w `types.ts`.
- **1 komponent / warstwa / sekcja = 1 plik.**
- Każde zadanie na **osobnej gałęzi** (`a/...` lub `b/...`) i **Pull Request** – nigdy push na `main`.
- Pliki wspólne (`backend/app/main.py`, `frontend/src/App.tsx`, `frontend/package.json`, `backend/requirements.txt`, `docker-compose.yml`, `CLAUDE.md`) zmieniane tylko w **osobnym małym commicie**.
- Claude Code **nie używa przeglądarki bez wyraźnej prośby**. Weryfikacja: `pytest` (backend, bez sieci; testy na żywo tylko `pytest -m live`) i `npm run build` (frontend).

### Struktura

```
backend/app/
  main.py            tylko utworzenie app i rejestracja routerów
  core/              config.py, http.py (klient, błędy źródeł, 404/502/501), cache.py (TTL), geo.py (2180 ↔ 4326)
  schemas/           KONTRAKT: parcel.py, analysis.py, layers.py, reports.py, weather.py
  sources/           jeden moduł na źródło: uldk, weather_power, weather_openmeteo, iung, kieg, nmt, bdot, sentinel, gus
  analysis/          et0, crops, water_balance, soil, terrain, scoring, recommendations, rules/*.yaml
  routers/           parcel, weather (działają); analysis, layers, reports, infra_reports (501 „w budowie”)
  report/            raport PDF (WeasyPrint)
frontend/src/
  api/               client.ts (zapytania, błędy po polsku), types.ts (KONTRAKT)
  mocks/             analysis.sample.json + useMockAnalysis – tylko `npm run dev` z `?dane=przykladowe`, z napisem „DANE PRZYKŁADOWE”
  theme/             index.css (tokeny SPEC 2), status.ts, recommendations.ts
  layout/            Sidebar, BottomTabs, TopBar, BottomCards (+ cards/), BottomCardsStack, MobileSheet
  components/        komponenty wielokrotnego użytku (SPEC 14), components/ui = shadcn
  features/          search, map (+ map/layers: CropHealth, PlantMoisture, Terrain, WaterFlow, Soil),
                     parcel-panel, passport (SectionA–E), timeline, reports, infra-reports, weather
  pages/             Start, MyParcels, Reports, Settings
  lib/               utils (cn), dates, format, hooks, crops
```

## Zasady pracy

- To jest działający prototyp na hackathon, nie produkt komercyjny. NIE twórz: polityki prywatności, regulaminu, banera cookies, zgód RODO, logowania/rejestracji, kont użytkowników, panelu admina ani stron typu „O nas”/„Kontakt”. Każdy widoczny element ma działać na prawdziwych danych i służyć ścieżce: Szukaj działki → Zobacz pole → Zrozum stan → Rekomendacje → Raport.
- Każda zmiana: testy (`pytest` dla backendu, `npm run build` dla frontendu) muszą przechodzić, potem commit z opisem po polsku na gałęzi zadania i Pull Request (patrz „Praca zespołowa”).
- Kod źródeł danych w `backend/app/sources/<źródło>.py`, obliczenia w `backend/app/analysis/`, endpointy w `backend/app/routers/`, kontrakty w `backend/app/schemas/`.
- UI po polsku, prostym językiem dla rolnika.
- Nie publikujemy niczego na serwerze bez zgody właściciela repo.
