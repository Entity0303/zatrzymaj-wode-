# Wodoskop – przewidywane pytania jury i odpowiedzi

**1. Skąd wiecie, ile padało na mojej działce?**
- **Źródła:** stacje IMGW (posterunki opadowe, klimatologiczne, synoptyczne) z maks. 30 km, ważone odległością, oraz modele NASA POWER i ERA5-Land do porównania.
- **Co sprawdziliśmy:** NASA na nizinach zawyża opad o 16–23 % rocznie, w każdym z 10 lat, a w górach jest blisko stacji (−3 %).
- **Przykład:** 15.07.2021 na Podlasiu stacja zmierzyła 58 mm, a NASA podaje 3,5 mm.
- **Wniosek:** IMGW źródłem głównym (wdrażane w backendzie jako A7). Gdy źródła się różnią, mówimy to rolnikowi jednym zdaniem.

**2. A jeśli w pobliżu nie ma stacji?**
- Proponujemy stacje do 50 km z niższą pewnością, potem model. Na Lubelszczyźnie najbliższa stacja z pełną serią jest 37 km dalej – i to mówimy wprost.

**3. Czy wyniki są zgodne z rzeczywistością?**
- **Plony:** model porównany ze średnimi plonami GUS z 10 lat. Różnica od −13 % do +11 % (±7–13 %) dla upraw polowych w trzech województwach.
- **Wrażliwość na suszę:** sprawdzona na spadkach plonów GUS w latach suchych 2015, 2018 i 2019. Kolejność upraw wg Ky zgadza się z kolejnością spadków plonów w GUS (korelacja Spearmana 0,77).
- **Uczciwie:** GUS miesza efekt gatunku z glebą, więc tej kalibracji używamy tylko kierunkowo.

**4. Skąd wiecie, co siać na słabej ziemi?**
- **Test:** Puszcza Notecka (piasek słabogliniasty, kompleks żytni słaby, kat. IUNG I).
- **Wynik:** ❌ pszenica, rzepak, jęczmień, kukurydza; ✅ żyto, łubin.
- **Skąd:** z symulacji 10 sezonów i przydatności gleby (kompleks z mapy glebowo-rolniczej GUGiK). Zgodne z zaleceniami agrotechnicznymi.

**5. Dlaczego żyto, skoro w suszy 2018 traciło procentowo tyle co pszenica?**
- Bo żyto rośnie na najsłabszych piaskach – traciło przez glebę, nie przez gatunek. Model liczy glebę osobno (pojemność wodna z IUNG), więc nie karzemy żyta za piasek dwa razy. Pytanie zadaliśmy też mentorowi.

**6. Czy to nie są gotowe teksty z AI?**
- Nie. Każde zdanie powstaje z reguły (YAML) i policzonych liczb: bilans wody FAO-56, plon FAO-33, teren z NMT. LLM niczego nie liczy. Przy każdej rekomendacji są dane, które ją uruchomiły.

**7. Co z drenażem, rowami, przepustami?**
- Model ich nie zna – piszemy to wprost w ograniczeniach raportu. Rolnik zna swoje pole: wynik terenu to wskazówka, gdzie sprawdzić, a nie projekt melioracji.

**8. Teren – skąd wiecie, gdzie woda ucieka?**
- **Dane i obliczenia:** model terenu GUGiK (siatka 3–15 m), wypełnianie zagłębień, kierunki spływu D8 i D-infinity, akumulacja spływu.
- **Wynik:** wyjście wody to miejsce na granicy pola, przez które odpływa największa część jego powierzchni.
- **Testy:** płaszczyzna, misa, dwa wzgórza.

**9. Co, jeśli usługa publiczna nie działa?**
- Cache wszystkich źródeł i tryb offline. Awaria jednego źródła obniża pewność, ale nie wywraca analizy. Nigdy nie podążamy za przekierowaniami – przeciążony serwer GUGiK potrafi wtedy wysłać plik ~126 MB.

**10. Licencje i dane osobowe?**
- Tylko licencje permisywne (MIT/BSD/Apache, Inter – OFL), bez bibliotek GPL (teren liczymy sami w numpy). Żadnych danych osobowych, bez kont i logowania.

**11. Co jest szacunkiem?**
- Ky części upraw (FAO-33 obejmuje tylko kilka), część zaleceń agrotechnicznych (przerwy, przedplony, gleby), wrażliwość na suszę. Wszystko oznaczone w danych („szac.”), pewność rankingu nigdy „wysoka”.
