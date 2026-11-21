# Osoba C (Mikołaj) – stan prac i przekazanie (aktualizowane na bieżąco)

Gałąź `c/research`, tylko folder `research/`, **bez merge do main**. Testy: `python -m pytest research -q` (bez sieci).
Środowisko: Python 3.13 + `numpy`, `matplotlib`, `pytest`, `tifffile` (wszystkie BSD/PSF-podobne).

## Zasady sieci (obowiązkowe)
- **GUGiK zablokował IP sieci hackathonu.** Nie odpytywać ULDK, NMT, KIEG, BDOT10k ani Geoportalu.
- **Archiwum Open-Meteo:** limit dzienny wyczerpany.
- **Nigdy nie podążać za przekierowaniami.** Każdy klient HTTP w `research/` ma opener bez przekierowań; treści 3xx nie czytamy.

## Zrobione (commit → plik)
| Zadanie | Gdzie | Najważniejsze |
|---|---|---|
| C1 teren | `research/terrain/` | priority-flood, D8/D∞, TWI, strefy, oczko, pas buforowy; port w backendzie (A6) |
| C2/C2b uprawy | `research/data/crops.csv` (22 wiersze), `gus_*.csv` | Ky, Kc, gleby, płodozmian; kopia w `backend/app/data/crops/` (różnica celowa: ziemniak `irrigation_practice`, backend poprawi) |
| C3 | `research/data/do_mentora.md`, `drought_report.md`, `mentor_odpowiedzi.md` (szablon) | kalibracja Ky z GUS tylko kierunkowa; żyto 0,80 / pszenżyto 0,90 zostają |
| C4 opady | `research/precip/` (`REPORT.md`) | NASA zawyża opad o +16–23 % vs IMGW (niziny); 15.07.2021 Podlasie: IMGW 58 mm vs NASA 3,5 mm; ERA5-Land – kod gotowy, brak danych (limit) |
| C5 działki demo | `research/demo/out/candidates.json`, `research/demo_candidates.md` | 8 punktów w środku pól (≥ 38 m od krawędzi), pola `why`/`expected`; numery działek dociągnąć z innej sieci (A8) |
| C6 zgłoszenie | `research/submission/` (`wymagania.md`, `opis.md`, `slajdy.md`, `film.md`, `pytania_jury.md`) | lista kontrolna KOWR: **brakuje README, Sentinel-2, danych hydrologicznych, PDF prezentacji, filmu** |
| C7 IUNG SMSR | `research/validation/` (`smsr.md`) | zgodność 1725/1728 (kat. gleby działek); kat. I: susza IUNG 171 → IMGW wykrywa 61, NASA 12; nasz KBW ~30 mm (IMGW) wilgotniejszy niż IUNG; SMSR ma tylko lata 2020–2026 |

## W toku
- **C9 Sentinel-2** (`research/satellite/`):
  - **gotowe:** `sentinel.py` (STAC Earth Search, własny odczyt kafli COG przez HTTP Range + `tifffile`, SCL, NDVI, NDMI, UTM bez pyproj) i `run_satellite.py`,
  - **pomiar:** STAC 1,9 s; kafel 10 m ≈ 1,4 MB, kafel SCL ≈ 30 kB, więc najpierw SCL, pasma tylko dla czystych scen (maks. 1 na 15 dni),
  - **do zrobienia:** wynik dla Podlasia (pełny szereg 2 lata), kandydaci (ostatnia scena + rok wcześniej), testy offline, commit.
- **C8 hydrologia** (`research/hydro/`), jeszcze nie zaczęte. Źródła spoza GUGiK:
  - MPHP (Wody Polskie/KZGW),
  - IMGW `api/data/hydro` + archiwum dobowe,
  - OSM Overpass (dane na licencji ODbL – wymagane przypisanie).

## Kluczowe liczby do zgłoszenia
NASA vs IMGW +16–23 %; 58 mm vs 3,5 mm (15.07.2021); kalibracja GUS ±7–13 % (D61); test słabej ziemi Notecka (❌ pszenica/rzepak, ✅ żyto/łubin); IUNG SMSR: IMGW wykrywa 5× więcej susz niż NASA (61 vs 12 z 171).
