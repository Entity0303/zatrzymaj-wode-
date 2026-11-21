# Wodoskop – slajdy (8 + zapas)

1. **Wodoskop – prześwietl swoją działkę pod kątem suszy.** Zadanie KOWR „Zatrzymaj wodę”. Zrzut: mapa z obrysem działki i werdyktem.
2. **Problem.** Dane o wodzie są publiczne, ale rozproszone. Rolnik nie wie, czy susza to wyjątek, ani co może zrobić bez pozwoleń.
3. **Jak to działa.** Działka + uprawa + data → kilka sekund → werdykt, stan wody na tle 10 lat, „Co tu posiać?”, rekomendacje retencja → agrotechnika → nawadnianie, raport PDF.
4. **Werdykt i „Co tu posiać?”.** Puszcza Notecka (piasek, kat. IUNG I): ❌ pszenica, rzepak; ✅ żyto, łubin. Obok czarnoziem z Grzędy Horodelskiej: ✅ pszenica. Ranking z symulacji 10 sezonów: typowy plon, słaby rok, ryzyko suszy, płodozmian.
5. **Teren w skali pola.** Mapa stref: sucha górka, stok, mokry dołek. Strzałki spływu, miejsce, gdzie woda ucieka z pola, propozycja oczka i pasa buforowego (stok w Małopolsce: spadek 15 %).
6. **Opady – sprawdzamy źródła.**
   - **Wykres:** słupki rok × źródło (IMGW vs NASA, `research/precip/out/*_opady.png`).
   - **Liczby:** NASA zawyża opad o +16–23 % na nizinach. 15.07.2021, Podlasie: **58 mm (IMGW) vs 3,5 mm (NASA)**.
   - **Wniosek:** stacje IMGW źródłem głównym.
7. **Wiarygodność.**
   - Kalibracja z GUS: model vs plony z 10 lat w granicach ±7–13 %.
   - Wrażliwość na suszę sprawdzona na latach 2015, 2018 i 2019.
   - Przy każdym wyniku źródło, data, pewność i ograniczenia. Szacunki oznaczone.
8. **Dlaczego to działa w praktyce.** Działania najpierw bez pozwoleń (międzyplony, pasy buforowe), formalności wprost (Wody Polskie, ekoschematy ARiMR). PDF do zabrania do doradcy.

**Zapas (pytania):**
- źródła danych i licencje,
- ograniczenia (drenaż, rozdzielczość, szacunki Ky),
- odporność: cache, tryb offline, brak przekierowań.
