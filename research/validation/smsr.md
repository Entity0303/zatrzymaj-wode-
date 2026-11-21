# C7 – walidacja z IUNG SMSR (2026-11-21)

**Dla jury, w jednym zdaniu:**
> Z oceną suszy IUNG zgadzamy się w **1725 z 1728** porównań (99,8 %) dla gleb naszych działek. Na glebach lekkich, gdzie susza zdarza się często, opad ze stacji IMGW wykrywa ją **5 razy częściej** niż model NASA (61 vs 12 okresów suszy IUNG). Dlatego opad bierzemy ze stacji.

Skrypt: `research/validation/smsr.py`.
- **Wyniki:** `out/smsr_porownanie.csv` (każde porównanie), `out/kbw_okresy.csv` (nasze KBW w każdym okresie), `out/smsr_podsumowanie.json`, `out/smsr_przesuniecie.json`.
- **Dane IUNG:** progi w `data/smsr_progi.json`, flagi gmin w `data/smsr_gminy.json`. Surowe strony leżą w `data/smsr_raw/` (w `.gitignore`).

## Co da się pobrać z IUNG SMSR
- **Serwis odpowiada** (`susza.iung.pulawy.pl`, 0,2–0,3 s na stronę, bez przekierowań). Ma tylko lata **2020–2026**, więc **2018 i 2019 są niedostępne**.
- **Dla gminy, roku i okresu 60-dniowego** (14 okresów, 21.III–20.V … 1.VIII–30.IX) serwis podaje:
  - ocenę „zagrożenie suszą” + / − dla 15 upraw i 4 kategorii gleby: `/wykazy/{rok},{TERYT gminy}/`,
  - procent zagrożonej powierzchni.
- **Progi KBW** pochodzą z Rozporządzenia MRiRW z 11.04.2019 (`/progi/`).
- **Liczbowego KBW nie ma.** Serwis pokazuje tylko mapy PNG (`/static/smsr_maps/{rok}/KBW_{rok}_{okres}.png`), a geoserver IUNG ma tylko warstwy kategorii gleb.

## Metoda porównania
- **Nasz KBW:** Σ(P − ET0) w tym samym oknie 60 dni, w punkcie działki.
  - **ET0:** FAO-56 Penman-Monteith z NASA POWER, liczony tą samą funkcją co backend (`backend/app/analysis/et0.py`).
  - **Opad P:** wariant A to NASA POWER, wariant B to stacje IMGW (IDW, C4).
- **Nasza ocena:** „+”, gdy KBW < próg IUNG dla uprawy, kategorii gleby i okresu.
- **Porównanie:** z oceną IUNG dla gminy działki.
- **Zakres:** 4 działki (podlaskie, lubelskie, kujawsko-pomorskie, małopolskie), lata 2020–2025, 15 upraw.
  - **Test A:** tylko kategoria gleby działki (III lub IV) – 1728 porównań.
  - **Test B:** wszystkie kategorie I–IV – 6744 porównania. Sprawdza, czy poziom KBW jest właściwy.

## Wyniki
| Zakres | Porównań | Susza wg IUNG | Zgodne – NASA | Susze wykryte – NASA | Zgodne – IMGW | Susze wykryte – IMGW |
|---|---|---|---|---|---|---|
| A: kategoria gleby działki | 1728 | 3 | 1725 (99,8 %) | 0 | 1725 (99,8 %) | 0 |
| B: wszystkie kategorie | 6744 | 243 | 6505 (96,5 %) | 14 | 6532 (96,9 %) | 71 |
| – kategoria I (gleby lekkie) | 1560 | 171 | 1393 (89,3 %) | 12 | 1422 (91,2 %) | 61 |
| – kategoria II | 1728 | 67 | 1661 (96,1 %) | 2 | 1659 (96,0 %) | 10 |
| – kategoria III | 1728 | 5 | 1723 (99,7 %) | 0 | 1723 (99,7 %) | 0 |
| – kategoria IV | 1728 | 0 | 1728 (100 %) | 0 | 1728 (100 %) | 0 |

Fałszywe alarmy (my „+”, IUNG „−”), wszystkie kategorie: NASA 10, IMGW 40.

## Wnioski
1. **Wysoka zgodność w teście A to głównie zgodność „brak suszy”.** Na glebach kat. III–IV progi są niskie (np. zboża ozime: −188 do −306 mm) i w latach 2020–2025 IUNG ogłosił tam suszę tylko 3 razy, a my ani razu. Uczciwiej mierzy test B.
2. **Opad ze stacji IMGW jest dużo bliżej IUNG niż model NASA.** Z 171 okresów suszy na glebach lekkich IMGW wykrywa 61, a NASA 12. Potwierdza to wniosek z C4: NASA zawyża opad, więc zaniża suszę.
3. **Nasz KBW jest nadal „wilgotniejszy” niż IUNG.**
   - Najlepszą zgodność z oceną IUNG (kat. I–II) daje obniżenie naszego KBW o **ok. 30 mm (IMGW)** albo **ok. 50 mm (NASA)** w oknie 60 dni, przy średnim ET0 okna ok. 200 mm (`out/smsr_przesuniecie.json`).
   - Prawdopodobne przyczyny: inna metoda ETP w IUNG i ocena dla gminy (interpolacja), a nie dla punktu.
   - **Nie poprawiamy tego na siłę.** Wniosek dla backendu: progi suszy liczone z naszego KBW będą łagodniejsze niż IUNG, co trzeba napisać w ograniczeniach. Ewentualną korektę ETP ustalić z IUNG.
4. **Nasze KBW w latach suchych 2018 i 2019** (bez porównania z IUNG, `out/kbw_okresy.csv`, opad IMGW):
   - **2018:** Podlasie −174 mm (1.V–30.VI), Lubelskie −164 mm (11.IV–10.VI). Poniżej progu zbóż ozimych dla gleb kat. I (i II na Lubelszczyźnie).
   - **2019:** Kujawy −239 mm (1.VI–31.VII), poniżej progu dla kat. I–II.
   - Działki mają kat. III–IV, więc dla nich progów nie przekroczono.
5. **NASA vs IMGW w KBW:** różnica w oknie 60 dni wynosi średnio +9,5 mm, mediana +11 mm (448 okresów, 2016–2025). To ta sama nadwyżka opadu NASA co w C4, tylko w mniejszym oknie.

## Ograniczenia
- **Skala:** IUNG ocenia gminę, my punkt. Działka w Lubelskiem ma stacje IMGW dopiero w 37–46 km.
- **Lata:** brak 2018 i 2019 w SMSR.
- **Kategoria gleby:** porównanie opiera się na dominującej kategorii działki (`.ai/test-parcels.md`).
