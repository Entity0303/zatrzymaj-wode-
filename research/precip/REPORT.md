# C4 – opady z kilku źródeł (research) – raport

Data: 2026-11-21.
- **Pliki:** kod `precip.py`, analiza `analyze.py`, testy `test_precip.py` (offline, 15 testów), źródła `SOURCES.md`.
- **Wyniki:** `out/comparison.csv`, `out/big_differences.csv`, `out/stations.csv`, `out/summary.json`, wykresy `out/<działka>_opady.png`.

## Krok 0 – poprawka C3b (zrobiona wcześniej, commit `2fc1ca1`)
- Żyto ma z powrotem Ky 0,80, a pszenżyto ozime 0,90. Pozostałe zmiany C3 zostają (owies, jęczmień ozimy, rzepak, kiszonka).
- Uzasadnienie jest w `zrodla` obu wierszy i w `research/data/drought_report.md`: GUS nie rozdziela efektu gatunku od gleby, backend liczy glebę osobno (WOD), więc kalibracja jest tylko kierunkowa.

## Czego brakuje (wprost)
- **ERA5-Land – brak w tej analizie.** Archiwum Open-Meteo zwraca 429 „Daily API request limit exceeded” (limit 10 000/dzień wyczerpany z sieci hackathonu, `Retry-After` ~4,4 h). Kod jest gotowy, odpowiedzi trafiają do `data/cache/era5land_*.json`. Na innej sieci wystarczy uruchomić analizę z `P.ERA5_NETWORK = True`: jedno zapytanie na działkę, potem tylko cache.
- **Działka `143203_2.0027.112/11` (Kampinos) – pominięta.** ULDK z sieci hackathonu odpowiada 302 na `integracja01`. Obrysy pozostałych 4 działek wziąłem z wyników C1 (`research/terrain/out/*.geojson`), bez pytania ULDK. Kampinos dociągniemy z hotspotu po integracji.
- **Analizowane działki:** 4 województwa (podlaskie, lubelskie, kujawsko-pomorskie, małopolskie), 2016–2025, źródła IMGW i NASA POWER.

## Porównanie opadów (2016–2025)
| Działka | Stacje IMGW (IDW) | Śr. roczny IMGW / NASA [mm] | NASA vs IMGW rok / IV–IX | Lata NASA > IMGW | IV–IX 2018 (suchy) IMGW / NASA | IV–IX 2021 (mokry) IMGW / NASA | Korelacja dobowa IV–IX |
|---|---|---|---|---|---|---|---|
| podlaskie `201305_2.0038.6/1` | Burzyn (OPAD) 27 km | 613 / 704 | **+15,7 % / +21,6 %** | 10/10 | 329 / 396 | 518 / 548 | 0,59 |
| lubelskie `061704_2.0011.383/2` | Lublin-Radawiec 37 km, Zamość 46 km (SYNOP) – **brak stacji ≤ 30 km** | 591 / 692 | **+17,8 % / +15,3 %** | 10/10 | 297 / 379 | 494 / 482 | 0,64 |
| kujawsko-pomorskie `040703_5.0020.76` | Pakość (OPAD) 18 km, Kołuda Wielka (KLIMAT) 18 km, Toruń (SYNOP) 27 km | 528 / 650 | **+23,2 % / +16,5 %** | 10/10 | 240 / 265 | 352 / 454 | 0,68 |
| małopolskie `121601_5.0002.770` | Jastrzębia (KLIMAT) 7 km, Gorlice (OPAD) 19 km, Nowy Sącz (SYNOP) 21 km | 824 / 796 | −3,1 % / −6,4 % | 3/10 | 443 / 413 | 704 / 604 | 0,62 |

Etykiety zgodności dla sezonu IV–IX (próg rozrzutu ≤ 15 % zgodne, ≤ 35 % różnią się, > 35 % mocno się różnią):
- Małopolska: 9 z 10 lat „zgodne”.
- Nizinne działki: w 4–6 z 10 lat „różnią się”, a Podlasie w 2024 r. „mocno się różnią”.

**Przykłady dużych różnic dobowych** (pełna lista w `out/big_differences.csv`):
- **15 VII 2021, Podlasie:** IMGW 58 mm, NASA 3,5 mm. To dokładnie data przykładu demo „mokry rok 2021”: lokalna burza, której siatka 50 km nie widzi.
- **2 VII 2021, Podlasie:** IMGW 52 mm, NASA 9 mm.
- **21 VIII 2024, Lubelskie:** IMGW 66 mm, NASA 29 mm.
- **12 VII 2024, Kujawy:** odwrotnie, NASA 56 mm, a IMGW 18 mm (burza poza stacjami).
- **13–14 VII 2016, Podlasie:** NASA ok. 30 mm, IMGW 1–3 mm.

Na nizinnych działkach dni, w których źródła różnią się o ≥ 20 mm, jest 8–18 w 10 sezonach, w Małopolsce 22.

## Wnioski
1. **NASA POWER na nizinach systematycznie zawyża opad względem stacji IMGW, średnio o +16–23 % rocznie, i to w każdym z 10 lat.** W górach (Małopolska) jest blisko IMGW i lekko zaniża (−3 %). Model wody z samą NASA przeszacowuje wodę w glebie, więc niedoszacowuje suszy, szczególnie w latach suchych: w IV–IX 2018 NASA pokazuje o 25–80 mm więcej niż IMGW.
2. **Rok suchy i mokry wszystkie źródła rozróżniają.** IV–IX 2018 jest wyraźnie niższy od 2021 u IMGW (240–443 vs 352–704 mm) i u NASA. Ranking lat jest więc wiarygodny, ale wartości bezwzględne z NASA nie.
3. **Lokalnych burz NASA nie widzi.** Korelacja dobowa w sezonie wynosi tylko 0,59–0,68, a różnice 30–55 mm w jednym dniu zdarzają się co sezon. Działa to w obie strony: stacja może przegapić burzę nad działką, a model może ją „rozsmarować”.
4. **Sieć stacji z współrzędnymi jest nierówna.** Archiwum IMGW nie podaje współrzędnych, a API daje je dla 446 z 876 stacji z opadem (308 z pełną serią 2016–2025). Dla działki lubelskiej najbliższa stacja jest 37 km dalej, a działki podlaskiej 27 km. Stacje Zawady (13 km) i Tykocin (21 km) mają niepełne serie.
5. **Doba opadowa IMGW (6–6 UTC) nie pokrywa się z dobą kalendarzową modeli.** Korelacja z przesunięciem o dzień wynosi jeszcze 0,3–0,4. Zgodność trzeba więc oceniać na sumach z okien (30 dni, sezon), nie dzień po dniu. Tak działa `agreement()`.

## Propozycja dla backendu (nie zmieniam `backend/`)
- **Źródło główne opadu:** IMGW, IDW (waga 1/d²) z maks. 3 stacji w promieniu 30 km z danymi w okresie. Stacje mają mieć co najmniej 80 % miesięcy. Dla każdego dnia liczymy tylko ze stacji, które mają pomiar.
- **Reguła rezerwowa:**
  - brak stacji ≤ 30 km → stacje do 50 km i pewność o jeden poziom niżej,
  - brak stacji ≤ 50 km albo brak pomiaru w danym dniu → ERA5-Land (gdy dostępne), dalej NASA POWER.
- **Temperatura, promieniowanie, wiatr i wilgotność do ET0** zostają z NASA POWER (D1). Zmienia się tylko opad.
- **Korekta NASA (gdy jest jedynym źródłem):** nie stosować stałej korekty. Bias zależy od regionu (+23 % do −3 %). Zamiast tego liczyć go z najbliższych stacji za ostatnie 10 lat i podawać w ograniczeniach.
- **Wagi przy łączeniu źródeł** (opcjonalnie, gdy są oba): IMGW 0,7, ERA5-Land 0,3 przy stacjach ≤ 15 km, a IMGW 0,5, ERA5-Land 0,5 przy 15–30 km. NASA nie wchodzi do średniej, tylko do porównania. Do potwierdzenia po dociągnięciu ERA5-Land.
- **Progi zgodności:** rozrzut sum = (max − min) / max(średnia, 20 mm):
  - ≤ 15 % → „zgodne”,
  - ≤ 35 % → „różnią się” (pewność bez zmian, informacja),
  - > 35 % → „mocno się różnią” (pewność −1 poziom, sugestia sprawdzenia deszczomierza).

  Ocena liczona osobno dla sezonu (od 1 IV) i ostatnich 30 dni.
- **Jedno zdanie dla rolnika** (`precip.sentence()`), np.:
  - „Stacje IMGW i modele pogody są zgodne: od 1 kwietnia spadło ok. 90 mm.”
  - „Źródła różnią się: od 1 kwietnia od 82 do 104 mm – przyjmujemy pomiar ze stacji IMGW.”
  - „Źródła mocno się różnią (51–92 mm od 1 kwietnia) – możliwe lokalne burze; sprawdź deszczomierz na polu.”
- **Prognoza:** jedno zapytanie Open-Meteo z `models=icon_seamless,ecmwf_ifs025,gfs_seamless` (0,35 s). Rozrzut modeli pokazać jako niepewność („w 3 dni: 2–6 mm wg różnych modeli”).
- **Dane stacji w backendzie:**
  - katalog współrzędnych z API meteo (raz na tydzień),
  - pliki miesięczne OPAD/KLIMAT i roczne SYNOP z archiwum (cache 30 dni; archiwum aktualizuje się z opóźnieniem ok. 1–2 miesięcy),
  - bieżący miesiąc: API synop/meteo albo ERA5-Land/Open-Meteo `past_days`.
- **HTTP:** nigdy nie podążać za przekierowaniami i nie czytać treści 3xx. GUGiK przy limicie serwuje przez 302 plik ~126 MB, a NMT potrafi zwrócić strumień setek MB. W `research/` jest to już poprawione (`terrain.py`, `precip.py`, test z lokalnym serwerem 302).
