# Wodoskop – prześwietl swoją działkę pod kątem suszy

Projekt zespołu **Molekuły** na HackNation 2026, zadanie Krajowego Ośrodka Wsparcia Rolnictwa (KOWR) „Zatrzymaj wodę”.

<!-- SEKCJE: 1 opis · 2 uruchomienie · 3 architektura · 4 dane · 5 biblioteki · 6 AI · 7 licencja · 8 ograniczenia · 9 weryfikacja · zespół -->

## 1. Co to jest i jaki problem rozwiązuje

Rolnik podaje swoją działkę (numer z ewidencji, kliknięcie na mapie albo lokalizację telefonu), opcjonalnie uprawę
i datę. Po kilkunastu sekundach dostaje ocenę sytuacji wodnej pola: jak gleba trzyma wodę, ile wody ubyło w tym
sezonie na tle ostatnich 10 lat, gdzie na działce woda spływa i gdzie się zbiera, co warto tu siać i co zrobić –
w kolejności **zatrzymanie wody (retencja) → zmiany w uprawie → nawadnianie**. Wynik można pobrać jako raport PDF.

Problem: susza rolnicza w Polsce narasta, a dane, które pozwalają ją ocenić dla jednego pola (gleba, opady, teren,
zdjęcia satelitarne), są rozproszone w wielu publicznych serwisach i wymagają wiedzy GIS. Wodoskop zbiera je
w jednym miejscu i tłumaczy na proste zdania. Wszystkie wyniki są **liczone z danych** (bez gotowych tekstów i bez
modeli językowych w obliczeniach); przy każdej liczbie jest źródło, data danych i informacja o niepewności.

Działa dla dowolnej działki w Polsce i dowolnej daty z ostatnich 10 lat (dla daty historycznej – tylko dane sprzed tej
daty), w przeglądarce, także na telefonie.

## 2. Uruchomienie

Wymagany Docker (Docker Desktop na Windows/macOS).

```bash
docker compose up --build
```

- frontend: <http://localhost:5173>
- backend (API): <http://localhost:8000>, dokumentacja API: <http://localhost:8000/docs>
- stan źródeł danych: <http://localhost:8000/api/status>

Frontend przekazuje zapytania `/api` do backendu (proxy Vite). Cache wszystkich źródeł jest w wolumenie Dockera
(`cache-data`, plik `/data/cache.sqlite`) i przeżywa restart.

### Tryby sieci

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `OFFLINE_SOURCES` | `uldk,nmt,kieg,uug,bdot` | wymienione źródła GUGiK tylko z cache (sieć hackathonu blokowała GUGiK); pusty napis = wszystkie źródła na żywo |
| `DEMO_OFFLINE` | `false` | `true` = żadnych zapytań zewnętrznych, wszystko z cache (pokaz bez internetu) |

Wszystkie źródła na żywo (np. w domu albo z VPN):

```powershell
# PowerShell
$env:OFFLINE_SOURCES=""; docker compose up --build
```

```bash
# bash
OFFLINE_SOURCES="" docker compose up --build
```

Pokaz bez internetu (tylko dane z cache):

```powershell
# PowerShell
$env:DEMO_OFFLINE="true"; docker compose up --build
```

```bash
# bash
DEMO_OFFLINE=true docker compose up --build
```

Publiczne wdrożenie (Vercel + Render): [DEPLOY.md](DEPLOY.md).

Testy: backend `docker compose exec backend pytest` (bez sieci; testy na żywo: `pytest -m live`),
frontend `cd frontend && npm run build`.

## 3. Architektura

```
 przeglądarka (komputer / telefon)
 ┌──────────────────────────────────────────────┐
 │ frontend: React + Vite + TypeScript          │   mapa (Leaflet), panel działki, paszport wodny,
 │ Tailwind, shadcn/ui, Recharts                │   wykresy, raport PDF do pobrania
 └──────────────────────┬───────────────────────┘
                        │ /api (JSON, PDF)
 ┌──────────────────────▼───────────────────────┐
 │ backend: Python 3.12, FastAPI                │
 │  sources/   jeden moduł na źródło danych     │──► GUGiK (ULDK, NMT, BDOT10k, KIEG, PRNG, adresy,
 │  analysis/  obliczenia (numpy):              │    ortofotomapa, mapa glebowo-rolnicza)
 │    ET0 FAO-56, bilans wody w glebie,         │──► IUNG (kategorie podatności gleb na suszę)
 │    teren z NMT, ranking upraw, werdykt,      │──► IMGW-PIB (opad ze stacji), NASA POWER (pogoda 10 lat)
 │    reguły rekomendacji (YAML)                │──► Open-Meteo (prognoza), GUS BDL (plony, ceny)
 │  report/    raport PDF (WeasyPrint)          │──► Sentinel-2 (Earth Search), SoilGrids
 │  cache SQLite (wszystkie źródła, TTL)        │
 └──────────────────────────────────────────────┘
```

Każde źródło jest pobierane równolegle, z limitem czasu i cache; awaria jednego obniża „pewność” wyniku, ale nie
przerywa analizy. Wolniejsze części (zdjęcie satelitarne, teren z NMT) liczą się w tle – wynik pokazuje się od razu,
a te sekcje dochodzą po kilku sekundach.

## 4. Dane – źródła, zakresy, daty, licencje

**Pobierane na bieżąco** (przy analizie, z cache – dane trwałe bez wygasania, pogoda z ostatnich 7 dni 6 h, prognoza 1 h):

| Źródło | Co z niego bierzemy | Zakres / rozdzielczość | Warunki korzystania |
|---|---|---|---|
| ULDK GUGiK | granice i powierzchnia działki ewidencyjnej | cała Polska | usługa publiczna GUGiK, z podaniem źródła |
| IUNG-PIB (WMS/WCS `Susza:katgl_landuse2024`) | kategoria podatności gleby na suszę (I–IV, organiczne, nierolne), woda dostępna dla roślin | piksel ok. 5 m | dane publiczne IUNG-PIB, z podaniem źródła |
| Mapa glebowo-rolnicza (GUGiK, WMS) | kompleks przydatności, gatunek gleby | mapa z lat 1960–1980 | usługa przeglądania GUGiK |
| NMT GUGiK | wysokości terenu: spadki, górki, zagłębienia, spływ | siatka 3–15 m, dokładność 0,1 m | usługa publiczna GUGiK |
| KIEG / EGiB (GUGiK) | klasy bonitacyjne (tylko informacyjnie) | tylko część powiatów | usługa publiczna GUGiK |
| PRNG i UUG/PRG (GUGiK) | wyszukiwanie miejscowości i adresów | cała Polska | usługi publiczne GUGiK |
| Ortofotomapa (GUGiK, WMTS) | podkład mapy | — | © GUGiK |
| NASA POWER | parowanie (temperatura, wilgotność, wiatr, promieniowanie), opad zapasowy | 10 lat dziennie, siatka ok. 50 km | dane NASA, wolne do użytku z podaniem źródła |
| Open-Meteo | prognoza 16 dni; archiwum ERA5-Land jako źródło zapasowe | ok. 10 km | CC BY 4.0 |
| Sentinel-2 L2A (Earth Search, AWS) | kondycja roślin (NDVI) i wilgotność roślin (NDMI), porównanie z rokiem wcześniej | piksel 10 m, od 2017 r. | dane Copernicus – wolne i otwarte |
| SoilGrids (ISRIC) | uziarnienie i węgiel organiczny (uzupełniająco) | model globalny 250 m | CC BY 4.0 |
| OpenStreetMap Nominatim | zapasowe wyszukiwanie miejsc i adresów | — | ODbL, © autorzy OpenStreetMap |
| EOX Sentinel-2 cloudless, AWS Terrain Tiles, kafle OSM | podkład poza Polską, rzeźba w widoku 3D, podkład zapasowy | — | CC BY 4.0 (EOX) / dane otwarte / ODbL |

**Pobrane wcześniej i zapisane w repo** (`backend/app/data/`):

| Plik | Co | Data pobrania | Warunki |
|---|---|---|---|
| `imgw/opady.npz`, `stations.json`, `index.json` | opad dobowy z 449 stacji IMGW-PIB (319 opadowych, 70 klimatologicznych, 60 synoptycznych), 2016-01-01 – 2026-10-31 | 2026-11-21 | dane publiczne IMGW-PIB, z podaniem źródła |
| `crops/*.csv` | plony GUS BDL wg województw 2016–2025 (3149 wierszy), wrażliwość upraw na suszę | 2026-11-21 | GUS BDL, z podaniem źródła |
| `demo_parcels.json` | granice 15 działek przykładowych z ULDK | 2026-11-21 i 22 | GUGiK |
| `terrain/*.geojson`, `*.facts.json` | zapisane wyniki terenu z NMT dla 4 działek (zapas, gdy NMT nie odpowiada) | 2026-11-21 | GUGiK |

Ostatnie dni bez danych ze stacji (IMGW publikuje je z opóźnieniem 1–2 miesięcy) uzupełniamy danymi NASA przeliczonymi
do poziomu stacji – aplikacja mówi to wprost przy opadach.

## 5. Biblioteki i komponenty

**Frontend** (licencje z `node_modules/*/package.json`): React, React DOM (MIT), Vite (MIT), TypeScript (Apache-2.0),
Tailwind CSS (MIT), Radix UI / shadcn/ui (MIT), class-variance-authority (Apache-2.0), clsx, tailwind-merge,
tw-animate-css (MIT), Leaflet (BSD-2-Clause), MapLibre GL (BSD-3-Clause, widok 3D), Recharts (MIT),
lucide-react (ISC), oxlint (MIT), czcionki Inter i Fraunces (SIL OFL 1.1).

**Backend** (Python 3.12): FastAPI (MIT), Uvicorn (BSD-3), httpx (BSD-3), pydantic-settings (MIT), NumPy (BSD-3),
Shapely (BSD-3), pyproj (MIT), PyYAML (MIT), WeasyPrint (BSD-3), Jinja2 (BSD-3), segno (BSD-3, kod QR),
tifffile (BSD-3), pypdf (BSD-3); testy: pytest (MIT), respx (BSD-3). Czcionka w PDF: Inter z pakietu `fonts-inter`
(SIL OFL 1.1).

**Sprawdzenie wszystkich zależności frontendu** (całe drzewo z `package-lock.json`, pole `license` każdego pakietu,
22.11.2026): 290 pakietów – MIT 209, ISC 27, Apache-2.0 23, BSD-3-Clause 7, BSD-2-Clause 3, 0BSD 2, BlueOak-1.0.0 2
(licencja permisywna), SIL OFL 1.1 2 (czcionki), „MIT AND ISC AND BSD-3-Clause” 1. **Wyjątki:**

| Pakiet | Licencja | Gdzie | Plan |
|---|---|---|---|
| `react-leaflet` 5.0.0, `@react-leaflet/core` 3.0.0 | **Hippocratic License 2.1** – nie jest licencją permisywną (MIT/BSD/Apache) | w aplikacji (komponenty mapy dla Reacta) | w kolejnej wersji zastąpimy je cienką własną warstwą nad Leafletem (BSD-2-Clause) – mapa, warstwy, rysowanie pola i pinezki korzystają z niego w kilku plikach `features/map`, `features/draw`, `features/infra-reports` |
| `lightningcss` (13 pakietów dla różnych systemów) | MPL-2.0 | tylko narzędzie budowania (przez Tailwind CSS), nie trafia do aplikacji | bez zmian – wynikowy CSS nie podlega MPL |

**Backend i obraz Dockera – zależności przechodnie i systemowe:** `certifi` (MPL-2.0, przez httpx), `Pyphen`
(do wyboru GPL/LGPL/MPL – przez WeasyPrint; korzystamy z MPL), biblioteki systemowe Pango i GLib (LGPL, łączone
dynamicznie w obrazie Dockera). Żadna z nich nie jest wkompilowana w nasz kod na licencji GPL/AGPL.

## 6. Narzędzia AI

- **Claude Code** (Anthropic) z modelami **Claude** – asystent programowania: pisanie i poprawianie kodu frontendu
  i backendu, testy, przegląd tekstów interfejsu, dokumentacja (w tym ten plik), streszczenia materiałów źródłowych
  w `research/`. Pracowały dwie sesje (frontend i backend) z pamięcią projektu w katalogu `.ai/` (decyzje, dziennik,
  zmiany kontraktu API). Zmiany przeglądał i akceptował członek zespołu.
- **W samej aplikacji AI niczego nie liczy.** Oceny, werdykt, ranking upraw i rekomendacje wynikają z obliczeń na danych
  i z jawnych reguł (`backend/app/analysis/rules/*.yaml`); teksty dla rolnika są składane z wyników, a nie generowane
  przez model językowy.

## 7. Licencja projektu

**Do uzupełnienia przez zespół** (propozycja: MIT – plik `LICENSE` w katalogu głównym). Dane zewnętrzne pozostają na
licencjach ich dostawców (tabela w punkcie 4).

## 8. Znane ograniczenia

- Model wody w glebie (FAO-56) korzysta z tabelarycznych parametrów upraw – nie zna odmiany, nawożenia ani chorób.
- **Model nie uwzględnia wód gruntowych** – na terenach z płytką wodą (np. Żuławy, doliny rzek, obniżenia) rośliny
  mogą mieć więcej wody, niż pokazuje ocena.
- Spływ powierzchniowy jest uproszczony (20% opadu powyżej 20 mm na dobę). Model nie zna drenażu, rowów ani przepustów.
- Ile wody zmieści gleba: wartość typowa dla kategorii IUNG, nie pomiar na działce. Mapa glebowo-rolnicza pochodzi
  z lat 1960–1980; klasy EGiB są dostępne tylko w części powiatów.
- Opad ze stacji IMGW: burza może ominąć stację; dane IMGW mamy od 2016 r. NASA POWER ma rozdzielczość ok. 50 km
  i na nizinach pokazuje o 16–23% więcej opadu niż stacje.
- Teren: siatka 3–15 m (bruzdy niewidoczne), przy bardzo małych spadkach kierunek spływu jest niepewny, objętości
  zagłębień to rząd wielkości.
- Zdjęcia satelitarne: piksel 10 m, chmury, brak roku 2016; progi kondycji i wilgotności roślin są orientacyjne
  (bez kalibracji z pomiarami w polu).
- Ranking „Co tu posiać?”: plon potencjalny to rząd wielkości, część współczynników wrażliwości upraw na suszę to
  szacunki; wynik nie uwzględnia nawożenia, odmian ani chorób.
- Dla dat historycznych używamy aktualnego modelu terenu i plonów GUS 2016–2025 – to jawne wyjątki od zasady
  „tylko dane sprzed daty analizy”.
- Nasz bilans wody wychodzi łagodniejszy niż w systemie IUNG SMSR (ok. 30 mm na 60-dniowe okno).
- Bez granic działki z ULDK analiza dotyczy kwadratu ok. 1 ha wokół wskazanego punktu („obszar przybliżony”).
- Usługi GUGiK (ULDK, NMT) bywają chwilowo blokowane – dlatego cache i tryby `OFFLINE_SOURCES` / `DEMO_OFFLINE`.
- **W trakcie** (uzupełnimy po skończeniu): woda w okolicy – cieki, rowy i zbiorniki oraz stany wód z wodowskazów IMGW
  (interfejs gotowy, backend w budowie); adresy w wyszukiwarce – UUG/PRG GUGiK z rezerwą Nominatim (backend wdrożony,
  w trakcie sprawdzania); ceny skupu i przychód z pola (interfejs gotowy, dane w budowie).

## 9. Jak weryfikujemy wyniki

- **Opad NASA a stacje IMGW** (`research/precip/REPORT.md`): 4 działki w 4 województwach, 2016–2025. Na nizinach NASA
  pokazuje więcej opadu niż stacje: +15,7% (podlaskie), +17,8% (lubelskie), +23,2% (kujawsko-pomorskie) – w każdym
  z 10 lat; korelacja dobowa w sezonie 0,59–0,68. Dlatego głównym źródłem opadu są stacje IMGW (dla działki średnia
  ważona z maks. 3 stacji do 30 km), a różnica źródeł jest pokazywana przy wyniku.
- **Zgodność z metodyką IUNG SMSR** (`research/validation/smsr.md`): klimatyczny bilans wody z 60-dniowych okien
  porównany z oceną suszy IUNG dla gminy; 4 działki, lata 2020–2025, 15 upraw. Zgodność 99,8% (1725 z 1728) dla kategorii
  gleby działki i 96,9% dla wszystkich kategorii (6744 porównania, opad IMGW). Na najsłabszych glebach (kat. I) z opadem
  IMGW wykrywamy 61 ze 171 okresów suszy ogłoszonych przez IUNG (z samym NASA – 12).
- **Kalibracja rankingu upraw z plonami GUS** (`.ai/decisions.md` D61, D84; `backend/scripts/calibrate_ranking.py`):
  średni plon z symulacji porównany ze średnią GUS 2016–2025 w województwach podlaskim, lubelskim, wielkopolskim
  i kujawsko-pomorskim – po poprawce plonu potencjalnego 3 upraw największe odchylenie to 14% (17 upraw × 4 województwa).
- **Test słabej ziemi** (D70): piaski w Puszczy Noteckiej i na Kurpiach – pszenica, rzepak, jęczmień i kukurydza
  odradzane, żyto i łubin polecane (zgodnie z oczekiwaniem). Owies wyszedł odradzany (w symulacji traci > 20% plonu
  w 5–6 z 10 lat) – współczynników nie dopasowywaliśmy pod wynik.
- **Zgodność źródeł gleby** (D43, D49): mapa glebowo-rolnicza sprawdzona w 7 punktach w 6 województwach; na działce
  testowej wynik zgodny z kategoriami IUNG.
- **Testy automatyczne:** backend – 490 testów bez sieci i 5 testów na żywo (`pytest`, `pytest -m live`), w tym test
  zgodności przykładowych odpowiedzi z kontraktem API; frontend – kontrola typów i budowanie (`npm run build`).
- Przy każdym wyniku aplikacja pokazuje źródło, datę danych, pewność (wysoka / średnia / ograniczone dane) i braki
  danych – nigdy nie wstawia zera ani wartości wymyślonej.

## Koszty i aktualizacja

Wszystkie źródła danych są bezpłatne. Przy większej liczbie użytkowników kosztem jest serwer backendu i miejsce na
cache (kilkanaście MB na kilkadziesiąt działek). Dane pogodowe i satelitarne odświeżają się same (cache z czasem
ważności); magazyn opadów IMGW i plony GUS aktualizujemy skryptami z `backend/scripts/` (opady – co miesiąc,
plony – raz w roku).

## Zespół

**Molekuły** – HackNation 2026:
- Dominik – backend, dane i obliczenia,
- Mefju – frontend i wygląd,
- Mikołaj – research i prototypy (teren, satelita, walidacja).

Konsultacja merytoryczna: mentor KOWR (SGGW).
