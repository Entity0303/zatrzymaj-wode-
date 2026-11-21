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

## Rekomendacja na demo (3 minuty)
1. **`piasek-zyto` vs `czarnoziem-pszenica`:** ta sama data, skrajne gleby, czyli werdykt rankingu „Co tu posiać?”. IUNG I + kompleks 5 kontra IUNG IV + kompleks 1.
2. **`kujawy-susza`:** dobra gleba w najsuchszym regionie, z najbliższą stacją IMGW (6 km). Najlepiej pokazuje porównanie opadów z C4.
3. **`less-erozja` albo `121601_5.0002.770`:** teren, czyli spływ, wyjście wody i pas buforowy. 121601 ma już policzony teren, a less trzeba dopiero przeliczyć z hotspotu.

## Do zrobienia z hotspotu
- **ULDK `GetParcelByXY`** dla 7 punktów. Sprawdzić, czy działka ma ≥ 0,5 ha i nie jest drogą, a jeśli punkt trafi na granicę, przesunąć go o 20–50 m w głąb pola.
- **`research/terrain/run_examples.py <ID>`:** potwierdzić teren:
  - spadek dla `less-erozja` i `pogorze-stok`,
  - zagłębienie dla `pojezierze-oczko`,
  - płaskość dla `zulawy-mady`.
- **Opady:** dopisać działki do `research/precip/analyze.py` (stacje IMGW są już w indeksie offline).
