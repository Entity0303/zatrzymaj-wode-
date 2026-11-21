# C5 – kandydaci na działki demo (bez ULDK)

Stan na 2026-11-21. **Numerów działek nie pobierałem**, bo ULDK i NMT z sieci hackathonu odpowiadają 302. Dociągniemy je z hotspotu:
- **ULDK:** `GetParcelByXY` z `xy=lon,lat,4326`, bez śledzenia przekierowań.
- **Analiza terenu:** potem `research/terrain/run_examples.py <ID>`.

Skrypt: `research/demo/candidates.py`. Ortofotomapy (600 × 600 m, środek = punkt): `research/demo/out/<id>_orto.jpg`. Surowe wyniki: `research/demo/out/candidates.json`.

Sprawdzone na żywo (czasy w `candidates.json`):
- **kategoria IUNG:** WMS `katgl_landuse2024`, ~0,35 s,
- **kompleks, typ i gatunek gleby:** mapa glebowo-rolnicza WMS Geoportalu, 0,15–3 s,
- **ortofotomapa:** Geoportal `ORTO/StandardResolution`, 0,5–1,9 s,
- **najbliższe stacje IMGW:** indeks offline z C4.

Każdy punkt obejrzałem na ortofotomapie i w razie potrzeby przesunąłem na pole.

**Teren (NMT) nie jest sprawdzony.** NMT zwraca 302, a kod za tym nie idzie. Kolumna „Teren – oczekiwany” to opis geograficzny regionu, a nie pomiar.

| # | id | Scenariusz demo | Region | lon, lat | IUNG | Kompleks · typ · gatunek | Teren – oczekiwany | Najbliższe stacje IMGW |
|---|---|---|---|---|---|---|---|---|
| 1 | `piasek-zyto` | Piasek: „nie siej pszenicy, siej żyto” | mazowieckie, Kurpie | 21.4590, 53.2205 | **I** (bardzo podatna) | **5** żytni dobry · Dz · pgl | płasko, sandr | Dobrylas (OPAD) 26 km, Rozogi 31 km |
| 2 | `czarnoziem-pszenica` | Najlepsza gleba: pszenica; susza mimo dobrej gleby | lubelskie, Grzęda Horodelska | 23.8650, 50.8200 | **IV** (mało podatna) | **1** pszenny b. dobry · **Cz** (czarnoziem) · li | falisto, łagodne stoki | Strzyżów (KLIMAT) 12 km, Zamość 48 km |
| 3 | `kujawy-susza` | Dobra gleba, mało deszczu (najsuchszy region PL) | kujawsko-pomorskie, k. Inowrocławia | 18.2400, 52.7300 | III | **1** pszenny b. dobry · D (czarna ziemia) · glp | płasko | **Kołuda Wielka (KLIMAT) 6 km**, Pakość 13 km |
| 4 | `less-erozja` | Lessowy stok: erozja, pas buforowy w poprzek spływu | lubelskie, Płaskowyż Nałęczowski | 22.1700, 51.3155 | III | 2 pszenny dobry · Bw · **l (less)** | pola między zadrzewionymi wąwozami lessowymi – stoki | Puławy (KLIMAT) 18 km, Lublin-Radawiec 19 km |
| 5 | `pojezierze-oczko` | Zagłębienia bez odpływu: oczko w dołku | warmińsko-mazurskie, Pojezierze Mrągowskie | 21.3870, 53.8709 | IV | 3 pszenny wadliwy · B · gs | morena, obok zadrzewione zagłębienie | Mikołajki (SYNOP) 16 km, Kętrzyn 22 km |
| 6 | `zulawy-mady` | Ciężkie mady: płasko, nadmiar wody, melioracja | pomorskie, Żuławy Wiślane | 19.0300, 54.1600 | III | 3 · **F (mady)** | płasko, rowy melioracyjne | Gdańsk-Świbno (SYNOP) 20 km |
| 7 | `pogorze-stok` | Stok na Pogórzu: spływ, sucha górka, retencja | podkarpackie, Pogórze Dynowskie | 22.3000, 49.8400 | III | 2 · Dd · płz | pasy pól na stoku | **Dynów (KLIMAT) 5 km** |

**Działki już sprawdzone (z numerem, C1/C4):**
- `121601_5.0002.770`: małopolskie, stok. Spadek średnio 15 %, różnica wysokości 39 m, pas buforowy. Stacje IMGW 7–21 km.
- `040703_5.0020.76`: kujawsko-pomorskie. Zagłębienie 662 m³, propozycja oczka, 3 stacje IMGW 18–27 km.
- `201305_2.0038.6/1` (demo, podlaskie): przykład lokalnej burzy 15.07.2021 (IMGW 58 mm, NASA 3,5 mm).

## Lista do pobrania z hotspotu (A8: ULDK GetParcelByXY)
Plik: **`research/demo/out/candidates.json`**. Pola `lon` i `lat` to punkt **w środku pola**, wyznaczony przez `research/demo/field_center.py`:
- **Rozrost obszaru po kolorze** na ortofotomapie. Wyznacza jednolite pole wokół punktu; obrysy obejrzałem, a progi koloru poprawiłem dla Kurpi i Pogórza.
- **Nowy punkt** to miejsce w tym polu najdalej od krawędzi, w promieniu 150 m od punktu startowego.
- **Gleba w nowym punkcie** sprawdzona ponownie (IUNG, mapa glebowo-rolnicza).
- **Pozostałe pola w JSON:** stare współrzędne są w `lon_start` i `lat_start`, zapas od krawędzi w `odleglosc_od_krawedzi_m`.

| id | lon, lat (środek pola) | Zapas od krawędzi | Pole (szac.) | IUNG | Kompleks · gatunek | Środek pola OK |
|---|---|---|---|---|---|---|
| `notecka-slaba` | 16.26185, 52.68508 | 90 m | ~28.8 ha | **1** | 6 · ps | tak |
| `piasek-zyto` | 21.45847, 53.21966 | 52 m | ~7.1 ha | 2 | 5 · pgl | tak |
| `czarnoziem-pszenica` | 23.86583, 50.82115 | 57 m | ~19.8 ha | **4** | 1 · li | tak |
| `kujawy-susza` | 18.23933, 52.73062 | 150 m | ~20.8 ha | 3 | 1 · glp | tak |
| `less-erozja` | 22.17122, 51.31662 | 82 m | ~11.1 ha | 3 | 2 · l | tak |
| `pojezierze-oczko` | 21.38672, 53.87180 | 202 m | ~25.8 ha | 4 | 3 · gs | tak |
| `zulawy-mady` | 19.02959, 54.16038 | 98 m | ~14.3 ha | 3 | 2 · mady | tak |
| `pogorze-stok` | 22.29981, 49.84002 | 38 m | ~5.7 ha | 3 | 2 · płz | tak (wąskie pasy pól ~30–40 m) |
| `kurpie-slaba` | 21.42990, 53.26979 | 23 m | ~1.4 ha | 1 | 7 · pl | **nie** |

**Uwaga dla backendu.** Punkt testu słabej ziemi „Kurpie 21,43 / 53,27” (D69/D70) leży na ortofotomapie na skraju lasu przy drodze, a nie na polu. Do demo „słaba ziemia” lepiej użyć **Puszczy Noteckiej** (`notecka-slaba`): duże pole, IUNG I, kompleks 6, 90 m od krawędzi.

Po przesunięciu do środka pola `piasek-zyto` ma kategorię IUNG II zamiast I (kompleks 5 bez zmian), więc jako przykład słabej ziemi jest słabszy od Noteckiej.

## Rekomendacja na demo (3 minuty)
1. **`notecka-slaba` vs `czarnoziem-pszenica`:** ta sama data, skrajne gleby, czyli werdykt rankingu „Co tu posiać?”. IUNG I + kompleks 6 (❌ pszenica, rzepak; ✅ żyto, łubin) kontra IUNG IV + kompleks 1.
2. **`kujawy-susza`:** dobra gleba w najsuchszym regionie, z najbliższą stacją IMGW (6 km). Najlepiej pokazuje porównanie opadów z C4.
3. **`less-erozja` albo `121601_5.0002.770`:** teren, czyli spływ, wyjście wody i pas buforowy. 121601 ma już policzony teren, a less trzeba dopiero przeliczyć z hotspotu.

## Do zrobienia z hotspotu
- **ULDK `GetParcelByXY`** dla 8 punktów z `candidates.json` (bez `kurpie-slaba`). Sprawdzić, czy działka ma ≥ 0,5 ha i nie jest drogą, a jeśli punkt trafi na granicę, przesunąć go o 20–50 m w głąb pola.
- **`research/terrain/run_examples.py <ID>`:** potwierdzić teren:
  - spadek dla `less-erozja` i `pogorze-stok`,
  - zagłębienie dla `pojezierze-oczko`,
  - płaskość dla `zulawy-mady`.
- **Opady:** dopisać działki do `research/precip/analyze.py` (stacje IMGW są już w indeksie offline).
