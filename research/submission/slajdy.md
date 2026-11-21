# Wodoskop – slajdy (szkic, 8 slajdów; Dominik zatwierdza)

**1. Wodoskop – prześwietl swoją działkę pod kątem suszy**
- Zadanie KOWR „Zatrzymaj wodę”, zespół: … (do wpisania)
- Dla rolnika bez GIS – przeglądarka lub telefon
- *Na ekranie:* mapa z obrysem działki i werdyktem w panelu

**2. Problem**
- Dane o wodzie są publiczne, ale rozproszone
- Rolnik nie wie, czy susza to wyjątek, czy norma jego pola
- Nie wie, co siać i co zrobić z wodą bez pozwoleń
- *Na ekranie:* zdjęcie suchego pola i logotypy źródeł (IMGW, GUGiK, IUNG, GUS)

**3. Jak to działa**
- Numer działki albo klik → stan wody na tle 10 lat
- Werdykt w prostych zdaniach, „Co tu posiać?”, teren, co zrobić z wodą
- Raport PDF ze źródłami i ograniczeniami
- *Na ekranie:* zrzut ekranu panelu działki

**4. Dobra działka vs słaba działka**
- Podlasie (kompleks 2): polecane rzepak 3,5 t/ha i pszenica 4,5 t/ha, ryzyko suszy 1 na 10 lat
- Puszcza Notecka (piasek, kat. IUNG I): ❌ pszenica, rzepak; ✅ żyto, łubin
- Ranking z symulacji 10 sezonów pogody dla tej działki
- *Na ekranie:* dwie strony 1 raportu obok siebie (`reports/examples/dobra-*-p1.png`, `slaba-*-p1.png`)

**5. Teren w skali pola**
- Górki, stoki, obniżenia, kierunki spływu
- Miejsce, gdzie woda ucieka z pola
- Propozycje: oczko w zagłębieniu, pas buforowy w poprzek spływu
- *Na ekranie:* widok 3D i warstwa „Spływ wody”

**6. Sprawdziliśmy dane, zanim im zaufaliśmy**
- NASA zawyża opad o 16–23 % względem stacji IMGW na nizinach
- 15.07.2021, Podlasie: IMGW 58 mm, NASA 3,5 mm – lokalna burza
- Plony z modelu vs GUS: w granicach ±7–13 % dla upraw polowych
- *Na ekranie:* wykres słupkowy rok × źródło (`research/precip/out/201305_2.0038.6-1_opady.png`)

**7. Rekomendacje, które rolnik może wykonać**
- Najpierw bez pozwoleń: międzyplony, resztki pożniwne, mniej uprawek
- Zbóż się nie nawadnia – liczy się zatrzymanie wody
- Formalności wprost (Wody Polskie), tylko potwierdzone ekoschematy ARiMR
- *Na ekranie:* karty rekomendacji z oznaczeniem formalności

**8. Co dalej**
- Stacje IMGW jako główne źródło opadu, Sentinel-2, rowy i cieki z BDOT10k
- Weryfikacja agrotechniki z agronomem
- Wiele działek gospodarstwa, tryb doradcy
- *Na ekranie:* mapa Polski z działkami demo (`research/demo_candidates.md`)
