# Wodoskop – prześwietl swoją działkę pod kątem suszy

*Szkic opisu zgłoszenia (HackNation 2026, zadanie KOWR „Zatrzymaj wodę”). Dominik zatwierdza przed użyciem. Przy liczbach podany plik źródłowy.*

## 1. Problem
- **Susza powtarza się co roku.** Dane, które mogą pomóc (opady, gleby, teren, plony), są publiczne, ale rozproszone i wymagają wiedzy GIS.
- **Rolnik nie wie, czy susza na jego polu to wyjątek,** czy norma tego miejsca.
- **Brakuje odpowiedzi na trzy pytania:** co siać, żeby mniej tracić, i co zrobić z wodą bez kosztownych inwestycji i pozwoleń.

## 2. Dla kogo
- **Rolnik z jedną lub kilkoma działkami,** bez wiedzy GIS i hydrologii. Wystarczy telefon albo komputer z przeglądarką.
- **Doradca rolniczy:** dostaje raport PDF ze źródłami i ograniczeniami.

## 3. Jak działa
1. **Wyszukanie działki:** numer ewidencyjny, „obręb numer”, klik na mapie albo GPS. Bez dokładnych granic – analiza dla 1 ha wokół punktu, z ostrzeżeniem.
2. **Stan działki bez wybierania uprawy:** woda w glebie dziś na tle tej samej daty w 10 latach i bilans 30 dni.
3. **Werdykt w prostych zdaniach:** nagłówek i 4–6 zdań z liczbami (gleba, opady, teren, co siać, a czego nie).
4. **„Co tu posiać?”:** 17 upraw. Dla każdej typowy plon, plon w słabym roku (z rokiem), ryzyko suszy „X na 10 lat” i płodozmian.
5. **Teren:** górki (przesychają najszybciej), stoki, obniżenia i zagłębienia bez odpływu, kierunki spływu, miejsce, gdzie woda ucieka z pola.
6. **Co zrobić z wodą:**
   - **kolejność:** retencja → agrotechnika → nawadnianie,
   - **najpierw bez pozwoleń:** międzyplony, resztki pożniwne, mniej uprawek, pas buforowy,
   - **z formalnościami:** oczko, zastawka – „może wymagać zgłoszenia wodnoprawnego”; nawadnianie – „pozwolenie wodnoprawne, Wody Polskie”.
7. **Raport PDF:** werdykt na str. 1, ranking na str. 2, potem stan wody, 10 lat, przyczyny, rekomendacje, źródła z datami, pewność, ograniczenia.

## 4. Źródła danych
| Dane | Źródło | Do czego |
|---|---|---|
| Granice działki | ULDK GUGiK | obrys, powierzchnia |
| Gleba | IUNG (kategorie podatności na suszę), mapa glebowo-rolnicza GUGiK (kompleks, gatunek), SoilGrids, EGiB/KIEG | pojemność wodna, przydatność dla uprawy |
| Teren | NMT GUGiK | spadki, górki, obniżenia, spływ |
| Pogoda 10 lat | NASA POWER (dziś); **IMGW – stacje** (wdrażane, A7) | bilans wody, ET0 |
| Prognoza | Open-Meteo | ryzyko na 7 dni |
| Plony | GUS BDL (16 województw × 10 lat) | plon potencjalny w rankingu |
| Wody (rowy, cieki) | BDOT10k | **w przygotowaniu** |

## 5. Metody
- **Bilans wody w glebie:** FAO-56. Model dzień po dniu, ET0 Penman-Monteith (Hargreaves, gdy brakuje danych), KBW = opad − ET0, profil 1 m, pojemność wodna z kategorii IUNG.
- **Plon:** FAO-33, 1 − Ya/Ym = Ky·(1 − ETa/ETc).
- **Symulacja 10 lat:** każda z 17 upraw na pogodzie z 10 pełnych sezonów, plon potencjalny z GUS województwa × przydatność gleby (D61).
- **Kalibracja z GUS:** model porównany ze średnimi plonami GUS (D61). Wrażliwość upraw na suszę sprawdzona na latach suchych 2015, 2018 i 2019 (`research/data/drought_report.md`).
- **Teren:** wypełnianie zagłębień (priority-flood), spływ D8 i D-infinity, wskaźnik TWI – własny kod w numpy, bez bibliotek GPL (`research/terrain/`).
- **Rekomendacje i werdykt:** reguły YAML (warunek → zalecenie → dane, które je uruchomiły). LLM nic nie liczy.

## 6. Wiarygodność – co sprawdziliśmy
- **Opady.**
  - NASA POWER zawyża opad o **16–23 % rocznie względem stacji IMGW na nizinach** (podlaskie, lubelskie, kujawsko-pomorskie), w każdym z 10 lat. W górach (małopolskie) jest −3 % (`research/precip/REPORT.md`).
  - Przykład lokalnej burzy: **15.07.2021, Podlasie – IMGW 58 mm, NASA 3,5 mm** (`research/precip/out/big_differences.csv`).
  - Dlatego głównym źródłem opadu będą stacje IMGW (A7).
- **Plony.** Model kontra średnie plony GUS: **od −13 % do +11 % (±7–13 %) dla upraw polowych** w podlaskim, lubelskim i wielkopolskim (`.ai/decisions.md`, D61).
- **Test słabej ziemi:** Puszcza Notecka (piasek słabogliniasty, kompleks 6, kat. IUNG I). Wynik: **❌ pszenica, rzepak (i jęczmienie, kukurydza); ✅ żyto, łubin** (D70; punkt w `research/demo/out/candidates.json`).
- **Test dobrej działki:** Podlasie, działka 201305_2.0038.6/1 (kat. III, kompleks 2). Wynik: **polecane rzepak 3,5 t/ha i pszenica ozima 4,5 t/ha** (słaby rok 2018: 3,8 t/ha, ryzyko 1 na 10) (`.ai/log/a-backend.md`).
- **Uczciwie o kalibracji:** GUS miesza efekt gatunku z efektem gleby, bo żyto rośnie na najsłabszych piaskach. Kalibracja jest więc tylko kierunkowa, a glebę model liczy osobno (`research/data/drought_report.md`).

## 7. Zasady
- **Zbóż w Polsce się nie nawadnia** – liczy się zatrzymanie wody w glebie. Plan dawek tylko dla upraw, które w Polsce się nawadnia (warzywa, sady, truskawki) (D48, D64; `research/data/crops.csv`, kolumna `irrigation_practice`).
- **Tylko potwierdzone ekoschematy ARiMR**, bez kwot dopłat (D51).
- **Bez danych osobowych:** bez kont i logowania.
- **Licencje:** tylko MIT/BSD/Apache (czcionka Inter – OFL), bez GPL/AGPL.
- **Przy każdym wyniku** źródło, data danych, pewność i ograniczenia. Braki mówimy wprost.

## 8. Ograniczenia
- **Rozdzielczość:** teren w siatce 3–15 m, mapy glebowe sprzed lat, NASA POWER ~50 km (lokalne burze niewidoczne).
- **Szacunki agrotechniczne do weryfikacji:** Ky części upraw, przerwy w płodozmianie, przedplony, przydatność gleb – oznaczone „szac.” w `research/data/crops.csv`, pytania do mentora w `research/data/do_mentora.md`.
- **Brak publicznych deklaracji upraw:** rolnik sam podaje, co rośnie i co rosło wcześniej.
- **Model nie zna** drenażu, rowów ani przepustów.
- **Jeszcze nie ma:** danych satelitarnych (Sentinel-2) i hydrologicznych (BDOT10k) – patrz `research/submission/wymagania.md`.
- **Usługi publiczne bywają przeciążone:** ULDK i NMT odsyłają 302. Dlatego mamy cache, tryb offline i nigdy nie podążamy za przekierowaniami.

## 9. Plan rozwoju
1. Opady ze stacji IMGW jako źródło główne, ERA5-Land do porównania (A7, `research/precip/`).
2. Sentinel-2 (NDVI/NDMI) – zgodność modelu z satelitą jako miara pewności.
3. BDOT10k – najbliższy rów, ciek albo zbiornik i propozycje zastawek.
4. Weryfikacja agrotechniki z agronomem (mentor KOWR), potem korekta `crops.csv`.
5. Wiele działek gospodarstwa, tryb doradcy, symulator „co jeśli” (międzyplony → mniej dni stresu).
