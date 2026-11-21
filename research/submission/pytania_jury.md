# Wodoskop – 12 trudnych pytań jury (szkic; Dominik zatwierdza)

**1. Skąd bierzecie dane?**
Tylko z bezpłatnych, publicznych źródeł:
- **działki i teren:** ULDK, NMT GUGiK,
- **gleba:** IUNG, mapa glebowo-rolnicza GUGiK, SoilGrids,
- **pogoda:** NASA POWER, a do porównania stacje IMGW i ERA5-Land,
- **prognoza i plony:** Open-Meteo, GUS.

Listę z adresami i opisem mamy w `CLAUDE.md` i `research/precip/SOURCES.md`.

**2. Na ile dokładne są opady?**
- **Satelitarny model NASA POWER** (siatka ~50 km) zawyża opad o 16–23 % względem stacji IMGW na nizinach, w każdym z 10 lat.
- **Lokalnych burz model nie widzi.** 15.07.2021 na Podlasiu stacja zmierzyła 58 mm, a NASA 3,5 mm (`research/precip/REPORT.md`).
- **Dlatego** głównym źródłem będą stacje IMGW (do 30 km, ważone odległością), a różnicę między źródłami pokazujemy rolnikowi jednym zdaniem.

**3. Dlaczego nie liczycie nawadniania zbóż?**
- Bo w Polsce zbóż się praktycznie nie nawadnia: brak instalacji, a pobór wody wymaga pozwolenia wodnoprawnego.
- Dla zbóż, rzepaku i strączkowych pokazujemy, ile wody brakuje i jak ją zatrzymać w glebie.
- Dawki liczymy tylko tam, gdzie nawadnianie jest praktyką (warzywa, sady, truskawki) (D48, `research/data/crops.csv`).

**4. Skąd wiecie, co rośnie na polu?**
- Nie wiemy – i mówimy to wprost. Publicznych deklaracji upraw nie ma, więc uprawę i przedplon podaje rolnik.
- Bez wyboru uprawy aplikacja pokazuje stan działki.
- Sentinel-2 (zieleń i wilgotność roślin) mamy w planie jako sprawdzian modelu, nie jako rozpoznawanie upraw.

**5. Co, gdy GUGiK nie działa?**
- **Cache wszystkich źródeł** (działki, gleba, teren, pogoda) i tryb offline.
- **Awaria jednego źródła** obniża pewność, ale nie wywraca analizy.
- **Bez granic działki** liczymy obszar przybliżony 1 ha wokół punktu, z ostrzeżeniem.
- **Nigdy nie podążamy za przekierowaniami** – przeciążony GUGiK odsyła wtedy plik ~126 MB (D53–D56, D69).

**6. RODO?**
- Nie zbieramy danych osobowych: bez kont, logowania i zapisu, kto pytał.
- Numer działki ewidencyjnej to dana publiczna z ULDK.
- Zapisane działki trzymamy tylko w przeglądarce użytkownika.

**7. Ile kosztuje utrzymanie?**
- **Dziś zero za dane:** wszystkie źródła są bezpłatne.
- **Infrastruktura:** jeden mały serwer z cache SQLite.
- **Przy dużym ruchu:** komercyjny plan Open-Meteo albo własna kopia danych pogodowych, większy cache.
- Szacunek kosztów opiszemy w README (wymóg KOWR 5.4–5.5).

**8. Czy da się to skalować na całą Polskę?**
- **Kod działa dla dowolnej działki**, a dane mają zasięg krajowy.
- **Wąskie gardło** to limity usług publicznych: ULDK i NMT blokują przy dużym ruchu, Open-Meteo ma 10 000 zapytań na dobę.
- **Rozwiązanie:**
  - cache bez wygasania dla danych, które się nie zmieniają (gleba, teren, historia pogody),
  - pobieranie archiwów IMGW raz w miesiącu,
  - indeks stacji (`research/precip/data/`).

**9. Na ile wiarygodne są plony w rankingu?**
- Model porównaliśmy ze średnimi plonami GUS z 10 lat: od −13 % do +11 % (±7–13 %) dla upraw polowych w trzech województwach (D61).
- Pewność rankingu nigdy nie jest „wysoka”, a gdzie plon GUS to zastępnik (łubin, jęczmienie), piszemy „ograniczona”.

**10. Kto zweryfikował agrotechnikę?**
- **Metody:** FAO-56 (Kc, korzenie) i FAO-33 (Ky) to standardy naukowe.
- **Szacunki:** przerwy w płodozmianie, przedplony, przydatność gleb i część Ky to nasza ocena wg zaleceń IUNG/COBORU, oznaczona „szac.”.
- **Weryfikacja:** pytania zadaliśmy mentorowi (`research/data/do_mentora.md`), odpowiedzi zapisujemy w `research/data/mentor_odpowiedzi.md`.
- **Test słabej ziemi** (Puszcza Notecka) dał zgodny z praktyką wynik: żyto i łubin tak, pszenica i rzepak nie.

**11. Czym różnicie się od IUNG SMSR?**
- **SMSR** to oficjalny monitoring suszy rolniczej: klimatyczny bilans wody dla 15 upraw i kategorii gleb, w skali kraju i gmin.
- **My korzystamy z tej samej listy upraw i kategorii gleb, ale schodzimy do jednej działki:**
  - gleba z mapy glebowo-rolniczej, teren z NMT,
  - stan wody dziś na tle 10 lat,
  - ranking upraw z plonem,
  - konkretne działania z formalnościami,
  - raport.

**12. Co dalej po hackathonie?**
- **Najpierw:**
  - opady ze stacji IMGW,
  - Sentinel-2 jako sprawdzian modelu,
  - rowy i cieki z BDOT10k,
  - weryfikacja agrotechniki z agronomem.
- **Potem:** wiele działek gospodarstwa i tryb doradcy.
- Chętnie przekażemy KOWR wnioski z porównania źródeł opadów i kalibracji z GUS.
