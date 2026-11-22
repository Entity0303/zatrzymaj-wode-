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
- **C9 Sentinel-2** (`research/satellite/`).
  - **Kod gotowy i przetestowany (88 testów w `research/` przechodzi):**
    - `sentinel.py`: STAC Earth Search; własny odczyt kafli COG przez HTTP Range + `tifffile`, bez przekierowań; maska SCL; NDVI i NDMI; UTM bez pyproj,
    - `run_satellite.py`: mapy PNG z legendą, warstwa na mapę (PNG ~300 B + bbox EPSG:4326 zamiast siatki GeoJSON ~16 kB), wykres szeregu.
  - **Pomiar (Podlasie, 201305):**
    - STAC 2,0 s, 66 dat w 24 miesiącach,
    - kafel 10 m ≈ 1,1–1,4 MB, kafel SCL ≈ 30 kB,
    - pełny szereg 2 lata (30 czystych scen + 66 masek): **879 s, 127 MB** – za ciężkie na żywo (wymóg KOWR < 30 s).
  - **Dla backendu:** ostatnia czysta scena + scena sprzed roku ≈ 8–15 MB i ok. 20–40 s → liczyć w tle i cache'ować (np. raz na 5 dni); szereg tylko z cache.
  - **Naprawiony błąd:** metadane STAC podają offset −0,1, ale pliki COG są już zharmonizowane (DN czerwieni nad roślinnością = 356). Z offsetem wychodziło NDVI > 1, teraz `APPLY_STAC_OFFSET = False`. Błędne wyniki usunięte.
  - **DO ZROBIENIA:** ponownie przeliczyć wyniki: `python research/satellite/run_satellite.py` (Podlasie ok. 15 min z szeregiem, kandydaci po ok. 1 min), obejrzeć `out/*_mapa.png`, potem commit `research/satellite/out/`.
- **C8 hydrologia** (`research/hydro/`) – rozpoznanie źródeł (kodu jeszcze nie ma):
  - **IMGW `https://danepubliczne.imgw.pl/api/data/hydro` – DZIAŁA:** 0,3 s, stacje wodowskazowe z `lon`, `lat`, `rzeka`, `stan_wody`, `stan_ostrzegawczy`, `stan_alarmowy`. Archiwum dobowe: `.../dane_hydrologiczne/dobowe/{rok}/codz_{rok}.zip` (format `CODZ_publiczne_format.txt`), stąd norma (percentyle stanu w tym samym miesiącu).
  - **OSM Overpass – NIE DZIAŁA z tej sieci:** overpass-api.de, kumi.systems i mail.ru – brak połączenia po 21–45 s. Zapytanie gotowe: `way["waterway"~"ditch|drain|canal|stream|river"](around:500,lat,lon); way["natural"="water"](around:500,lat,lon)`. Licencja ODbL – wymagane „© OpenStreetMap contributors”.
  - **MPHP (Wody Polskie/KZGW) – nie sprawdzone,** wyszukiwarka niedostępna (limit). Znaleźć adres WMS/WFS albo plik do pobrania.
  - **Następny krok:** `hydro.py` – najbliższy wodowskaz + stan vs norma (IMGW); cieki i zbiorniki z OSM, gdy Overpass działa (inna sieć); zdanie dla rolnika z kierunkiem odpływu z `research/terrain/out/*.facts.json`.

## Kluczowe liczby do zgłoszenia
NASA vs IMGW +16–23 %; 58 mm vs 3,5 mm (15.07.2021); kalibracja GUS ±7–13 % (D61); test słabej ziemi Notecka (❌ pszenica/rzepak, ✅ żyto/łubin); IUNG SMSR: IMGW wykrywa 5× więcej susz niż NASA (61 vs 12 z 171).
