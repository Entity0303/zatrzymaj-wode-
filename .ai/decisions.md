# Decyzje projektowe

Wpis: data · decyzja · uzasadnienie · konsekwencje. Zmieniany w osobnym małym commicie. Nowe decyzje na dole.

---

### D1 · 2026-11-21 · NASA POWER jako główne źródło pogody z 10 lat
**Uzasadnienie:** dzienne dane od dziesięcioleci dla dowolnego punktu, bez klucza, ~1,6 s na 10 lat (wszystkie parametry do ET0 w jednym zapytaniu). Archiwum Open-Meteo (ERA5-Land ~10 km) ma dzienny limit na IP – w sieci hackathonu zwraca 429.
**Konsekwencje:** rozdzielczość ~50 km → ograniczenie „Pogoda uśredniona dla obszaru ok. 50 km” w wiarygodności. Archiwum Open-Meteo tylko jako źródło opcjonalne z fallbackiem na NASA POWER. Open-Meteo forecast – prognoza 16 dni.

### D2 · 2026-11-21 · ET0 liczone samodzielnie wg FAO-56 (Penman-Monteith), fallback Hargreaves
**Uzasadnienie:** kontrola nad metodą i jednolitość dla 10 lat; zgodność z metodyką (KBW = opad − ET0). Hargreaves wymaga tylko temperatury – gdy brakuje promieniowania, wilgotności lub wiatru.
**Konsekwencje:** metoda oznaczana dla każdego dnia (`PM`/`HG`); udział dni Hargreavesa obniża pewność. Test na przykładzie 18 z FAO-56.

### D3 · 2026-11-21 · Kategorie gleb IUNG (WOD) jako podstawa pojemności wodnej
**Uzasadnienie:** ogólnopolska mapa podatności na suszę używana w oficjalnym SMSR, z zakresami wody ogólnie dostępnej (WOD) dla kategorii I–IV; dostępna przez WMS GetFeatureInfo.
**Konsekwencje:** działkę próbkujemy kilkoma punktami → udziały kategorii; kody 11–14 = „to nie jest grunt rolny”.

### D4 · 2026-11-21 · Klasy bonitacyjne EGiB (KIEG) tylko informacyjnie
**Uzasadnienie:** usługa obejmuje tylko część powiatów, format HTML – nie da się na niej oprzeć obliczeń dla dowolnej działki w Polsce.
**Konsekwencje:** pokazywane w szczegółach, gdy dostępne; brak = ograniczenie, nie błąd.

### D5 · 2026-11-21 · NMT przez GetHByPointList zamiast WCS
**Uzasadnienie:** WCS za wolny dla wymogu < 30 s; GetHByPointList zwraca wysokości ±0,1 m dla listy punktów (POST do 1000 punktów ~2,5 s).
**Konsekwencje:** siatka punktów w obrysie + bufor; kolejność osi x = PÓŁNOC, y = WSCHÓD (odwrotnie niż ULDK). Spadki, dołki, spływ, TWI liczone w numpy (bez bibliotek GPL).

### D6 · 2026-11-21 · BDOT10k zamiast OSM/Overpass dla rowów i wód
**Uzasadnienie:** urzędowa baza z rozróżnieniem rów melioracyjny / ciek / kanał / zbiornik i datą aktualizacji; Overpass – niepełne rowy, limity publicznych serwerów.
**Konsekwencje:** WMS GetMap (odległość) + GetFeatureInfo (`x_kod`, data); typ obiektu decyduje o adresacie pisma (ciek → Wody Polskie, rów → właściciel/spółka wodna).

### D7 · 2026-11-21 · Sentinel-2 z Earth Search (2017+) + Copernicus Data Space (2016)
**Uzasadnienie:** Earth Search STAC – darmowe COG L2A, odczyt fragmentu przez rasterio bez pobierania sceny; brak 2016 → Copernicus Data Space STAC, żeby objąć pełne 10 lat.
**Konsekwencje:** zdjęcie najbliższe *przed* datą analizy, maska chmur SCL, data zdjęcia w `source_tag`.

### D8 · 2026-11-21 · Nie pokazujemy pH, składników pokarmowych ani temperatury gleby
**Uzasadnienie:** brak takich danych w publicznych źródłach dla dowolnej działki; zasada „wszystko liczone z danych”.
**Konsekwencje:** sekcja Gleba = kategoria podatności, ile wody zmieści gleba, klasa bonitacyjna (gdy dostępna) – SPEC 15.3.

### D9 · 2026-11-21 · Interfejs wyłącznie po polsku, prostym językiem
**Uzasadnienie:** użytkownik – rolnik bez wiedzy GIS (KOWR, SPEC 1).
**Konsekwencje:** słownik SPEC 1 (np. „Kondycja upraw” zamiast NDVI); terminy techniczne tylko w „Szczegółach”.

### D10 · 2026-11-21 · Czcionka Inter (SIL OFL 1.1), dołączona lokalnie
**Uzasadnienie:** wymagana przez SPEC 2.3; OFL 1.1 to licencja permisywna dla czcionek (dopisana do zasady licencji w CLAUDE.md). Pakiet `@fontsource-variable/inter` – bez zapytań do Google Fonts.

### D11 · 2026-11-21 · Brak kont, logowania i stron prawnych
**Uzasadnienie:** działający prototyp na hackathon, bez danych osobowych; liczy się ścieżka Szukaj działki → Zobacz pole → Zrozum stan → Rekomendacje → Raport.
**Konsekwencje:** zapis działek i raportów tylko w pamięci przeglądarki; bez polityki prywatności, cookies, RODO, admina, „O nas”.

### D12 · 2026-11-21 · Mock analizy tylko z parametrem `?dane=przykladowe`
**Uzasadnienie:** `docker compose up` uruchamia serwer deweloperski, więc warunek „tylko w trybie dev” włączałby mock zawsze i udawał prawdziwe dane.
**Konsekwencje:** mock = tryb dev **i** parametr w adresie; widoczny napis „DANE PRZYKŁADOWE”; plik JSON usuwany z buildu produkcyjnego.

### D13 · 2026-11-21 · Ortofotomapa przez WMTS (EPSG:3857) zamiast WMS
**Uzasadnienie:** WMS Geoportalu obsługuje EPSG:3857, ale kafel ~4,5 s; WMTS tej samej usługi (te same zdjęcia, kafle z cache) ~2,3 s.
**Konsekwencje:** `features/map/ParcelMap.tsx` – szablon KVP GetTile; OSM jako zapas.

### D14 · 2026-11-21 · Sezon bilansu domyślnie od 1 marca
**Uzasadnienie:** początek okresu wegetacyjnego i okres oceny w metodyce suszy rolniczej (KBW liczony od wiosny). Reguła liczona względem **ostatniego dnia z danymi** (data analizy − 1): jeśli jest przed 1 marca, sezon zaczyna się 1 marca roku poprzedniego. Dla daty analizy 1 marca daje to sezon poprzedni (bieżący miałby 0 dni).
**Konsekwencje:** `analysis/water_balance.default_season_start`; parametr `season_start` pozwala to zmienić (np. per uprawa w A3).

### D15 · 2026-11-21 · Dane pogodowe tylko do dnia przed datą analizy; zakres od 1 stycznia (rok początku sezonu − 10)
**Uzasadnienie:** zasada „tylko dane sprzed daty analizy”. Dla dat przed 1 marca sezon zaczyna się rok wcześniej, więc 10 poprzednich sezonów wymaga danych od roku daty − 11 (o rok więcej niż „rok daty − 10”).
**Konsekwencje:** `history_range()`; opóźnienie publikacji (NASA POWER ~2–4 dni) nie jest maskowane – „Dane pogodowe do dnia X” w ograniczeniach.

### D16 · 2026-11-21 · ET0 przy źródle zapasowym: wartość z archiwum Open-Meteo przed Hargreavesem
**Uzasadnienie:** archiwum nie podaje promieniowania, wilgotności ani wiatru (PM niemożliwe), ale podaje ET0 FAO-56 liczone z ERA5 – dokładniejsze niż Hargreaves z samej temperatury. Uzupełnia D2.
**Konsekwencje:** kolejność metod na dzień: PM → OM → HG → brak; liczba dni wg metody w metadanych i ograniczeniach.

### D17 · 2026-11-21 · Obsługa braków w bilansie
**Uzasadnienie:** brak danych nie może udawać pełności ani zaniżać wyniku bez informacji.
**Konsekwencje:** rok porównawczy z > 10% braków w okresie – pomijany (lista w ograniczeniach); pojedyncze dni bez danych w bieżącym sezonie – 0 mm w bilansie + ograniczenie „N dni bez danych”; miesiąc z > 20% braków – brak sumy (`null`); percentyl = % lat porównawczych z niższym bilansem (0 = najgorszy z 10 lat).

### D18 · 2026-11-21 · Budżet czasu pobierania pogody
**Uzasadnienie:** limit 30 s na całą analizę. NASA POWER zwykle ~1,6–1,9 s za 10 lat.
**Konsekwencje:** NASA POWER: 9 s na próbę + 1 ponowna próba (sieć/timeout/5xx; 429 bez ponawiania); archiwum Open-Meteo: 10 s, bez ponawiania. Cache 6 h, klucz – współrzędne zaokrąglone do 0,1° (rozdzielczość źródła ~50 km) + zakres dat.

### D19 · 2026-11-21 · Gleba IUNG: WCS GetCoverage `text/plain` jako metoda główna, GetFeatureInfo jako zapas
**Uzasadnienie:** rozważono GetMap PNG + zliczanie pikseli wg kolorów legendy. Odrzucone: wymaga dekodowania PNG (nowa zależność – Pillow), legenda jest typu „ramp” (przy przeskalowaniu możliwe kolory pośrednie), kody 19 i 99 mają ten sam kolor. GeoServer IUNG udostępnia WCS 2.0.1 z formatem `text/plain` – **surowe kody** wszystkich komórek 5 m w bbox działki w ~0,3 s, bez kolorów i bez nowych bibliotek. GetFeatureInfo (≤ 16 punktów) to tylko próbkowanie, więc zostaje zapasem.
**Konsekwencje:** osie WCS w konwencji PL-1992: `SUBSET=x(północ)`, `SUBSET=y(wschód)`, wiersz 0 = północ (sprawdzone 6/6 z GetFeatureInfo). Liczymy komórki ze środkiem w obrysie; powyżej 250 tys. komórek – `SCALEFACTOR`. Metoda zapasowa obniża pewność i jest opisana w ograniczeniach.

### D20 · 2026-11-21 · Reprezentatywna WOD kategorii IUNG
**Uzasadnienie:** IUNG podaje przedziały WOD; do średniej ważonej potrzebna jedna wartość na kategorię. II i III – środek przedziału (148,7 i 186,2 mm); I i IV mają przedział otwarty – granica ∓ połowa szerokości sąsiedniej kategorii (I: 127,5 − 21,2 = 106,3 mm; IV: 202,5 + 16,25 = 218,8 mm).
**Konsekwencje:** ograniczenie „WOD to wartość typowa dla kategorii gleby, nie pomiar na tej działce”. Kategoria → status karty: I = ryzyko, II = uwaga, III–IV = dobrze.

### D21 · 2026-11-21 · „To nie jest grunt rolny”: kody 5, 11–14 łącznie > 50% działki
**Uzasadnienie:** SPEC 15.1. Lasy, wody, zabudowa, drogi/nieużytki nie są użytkami rolnymi; gleby organiczne (5) nie mają kategorii podatności IUNG, więc WOD nie da się ocenić.
**Konsekwencje:** `soil_capacity` = „Nie dotyczy” (value null) z komunikatem; dokładnie 50% – jeszcze grunt rolny. Przykłady: 160703 (las 100%), 143203 (las 51% + zabudowa 14%), 302114 (woda 100%).

### D22 · 2026-11-21 · Klasy EGiB z KIEG: tylko nasza działka, brak = normalny stan
**Uzasadnienie:** odpowiedź KIEG dotyczy działki w punkcie – punkt przy granicy może trafić w sąsiada. Wiele powiatów nie publikuje klas.
**Konsekwencje:** zapytanie w środku działki + 3 punktach, bierzemy tylko wiersze z „Identyfikator działki” = nasza działka; klasy z „Oznaczenie konturu”. Brak klas → notka „Powiat nie udostępnia klas…”, bez obniżania pewności (D4). Nie odczytujemy „Grupy rejestrowej” ani pól o właścicielach.

### D23 · 2026-11-21 · Parametry upraw: FAO-56 tab. 11/12/22 + kalendarz PL; założenia tam, gdzie FAO-56 milczy
**Uzasadnienie:** jedno spójne, cytowalne źródło dla Kc, faz, Zr i p. Tab. 11 opisuje kalendarze innych klimatów, więc długości faz dopasowano do terminów w Polsce (zadanie A3): ozime i rzepak ozimy – wegetacja od 1 III; zboża jare – siew 8 IV (środek 1–15 IV); kukurydza – 1 V; ziemniak – 20 IV; burak – 1 IV; wieloletnie – 1 IV–31 X; rzepak jesień – od 20 VIII.
**Założenia (brak w tabelach FAO-56 lub w zadaniu):** kukurydza na kiszonkę – Kc_end 0,50 i faza dojrzewania 30 dni; rzepak jesień – Kc_mid 0,80, bez fazy dojrzewania (do ok. 28 XI); tytoń – wszystkie parametry przez analogię (brak w tab. 12/22); strączkowe – siew 15 IV; warzywa – start 20 IV, fazy 20/30/50/20, Zr 0,5 m, p 0,4; krzewy owocowe, truskawki – fazy dopasowane do 1 IV–31 X; chmiel – faza dojrzewania wydłużona do 31 X.
**Konsekwencje:** `analysis/crops.py`, źródło każdej wartości w komentarzu; korzenie od startu sezonu mają głębokość maksymalną (bez modelu wzrostu korzeni – uproszczenie, zawyża TAW na początku sezonu upraw jarych).

### D24 · 2026-11-21 · Kc_mid i Kc_end bez korekty klimatycznej (FAO-56 równ. 62)
**Uzasadnienie:** wartości tab. 12 są dla RHmin ≈ 45% i u2 ≈ 2 m/s – warunki zbliżone do Polski latem; korekta wymaga wysokości roślin i dziennego RHmin, a zmienia Kc zwykle o < 0,05.
**Konsekwencje:** prostszy model; możliwa korekta przy kalibracji do IUNG SMSR.

### D25 · 2026-11-21 · TAW z WOD IUNG skalowanej do głębokości korzeni; RAW = p · TAW
**Uzasadnienie:** WOD z IUNG traktujemy jako wodę dostępną w profilu ok. 1 m. Korzenie płytsze – proporcjonalnie mniej (ziemniak 0,5 m → 50% WOD), głębsze – bez zwiększania (pod 1 m brak danych o glebie).
**Konsekwencje:** `taw_from_wod()`; p z tab. 22 bez korekty na ETc (FAO-56 dopuszcza p + 0,04·(5 − ETc)) – do rozważenia przy kalibracji.

### D26 · 2026-11-21 · Opad efektywny: spływ 20% części opadu powyżej 20 mm/dzień
**Uzasadnienie:** prosty, zachowawczy wzór bez danych o terenie (A3). Parametry `runoff_threshold` i `runoff_fraction` są argumentami modelu – nadpisze je analiza terenu z NMT (spadki).
**Konsekwencje:** nadmiar wody ponad pojemność polową = przesiąkanie (Dr ≥ 0), raportowane jako `percolation_mm`.

### D27 · 2026-11-21 · Ryzyko 7 dni i „stres za X dni”
**Uzasadnienie:** rolnik potrzebuje odpowiedzi „kiedy rośliny zaczną cierpieć”. Horyzont 16 dni = zasięg prognozy Open-Meteo.
**Konsekwencje:** data analizy = dziś → prognoza Open-Meteo (opad, ET0), `source_tag = prognoza`; data historyczna (lub brak prognozy) → scenariusz typowej pogody: mediana opadu i ET0 z tych samych dni w 10 poprzednich latach, `source_tag = szacunek_modelu`. Luka opóźnienia NASA POWER (2–4 dni przed datą analizy) uzupełniana danymi Open-Meteo `past_days=7`, a gdy ich brak – scenariuszem (ograniczenie w odpowiedzi). Klasy: **wysokie** – RAW przekroczone już lub w ≤ 3 dni; **średnie** – 4–7 dni; **niskie** – później albo wcale w horyzoncie. Status „danger” (Susza), gdy stres trwa i Ks < 0,5.

### D28 · 2026-11-21 · Zapas wody na start sezonu *(reset na start sezonu – zastąpiony ciągłym bilansem D30; okna 1 XI / 1 VII obowiązują)*
**Uzasadnienie:** po suchej zimie profil nie jest pełny. Bez danych o wilgotności gleby przyjmujemy pojemność polową, zmniejszoną o deficyt bilansu P − ET0 w oknie przed sezonem: Dr0 = min(TAW, |bilans|), gdy bilans ujemny (mm za mm – proporcjonalnie do TAW).
**Konsekwencje:** okno od 1 XI roku poprzedniego do startu (siew/wegetacja wiosenna); dla siewu letnio-jesiennego (rzepak jesień) od 1 VII – okno od listopada objęłoby całe lato poprzedniej uprawy. Zakres pobieranej pogody rozszerzony do 1 XI (rok sezonu − 11) – okno najstarszego sezonu porównawczego. Brak danych w oknie (> 20%) → start z pełnym profilem + ograniczenie.

### D29 · 2026-11-21 · Nawadnianie i stan poza sezonem *(dawka i stan poza sezonem – zastąpione przez D33, D34)*
**Uzasadnienie:** zalecenie tylko wtedy, gdy model pokazuje stres teraz lub w ciągu 7 dni; dawka liczona, nie zgadywana.
**Konsekwencje:** dawka = ubytek do pojemności polowej w dniu przekroczenia RAW, zaokrąglona do 5 mm (min. 5 mm); powyżej 40 mm dopisek „w praktyce w N dawkach po ok. 30–35 mm”. Rekomendacja w formacie kontraktu (`category = nawadnianie`, dane wejściowe, pewność: średnia przy prognozie, ograniczona przy scenariuszu). Przed sezonem uprawy – brak wskaźników „na dziś” i brak dni stresu; po sezonie – tylko podsumowanie dni stresu zakończonego sezonu na tle 10 lat.

### D30 · 2026-11-21 · Ciągły bilans wody przez cały rok, dwie warstwy w profilu 1 m (zastępuje w D28 „reset” na start sezonu)
**Uzasadnienie:** reset zapasu przy siewie ukrywał suche wiosny i nie pozwalał podać stanu wody poza sezonem. Siew zmienia tylko Kc i głębokość korzeni.
**Metoda:** profil 1 m (WOD z IUNG, D25) = strefa czynna 0..Zr(t) + warstwa dolna Zr(t)..1 m. Zr(t): goła gleba Ze = 0,12 m (FAO-56 rozdz. 7: 0,10–0,15 m); uprawy – liniowo od siewu (Ze; oziminy po zimie 0,3 m) do Zr max na końcu fazy rozwoju; wieloletnie – stale Zr max. Zmiana Zr przenosi plaster wody między warstwami przy równym względnym ubytku. Opad efektywny → strefa czynna → nadmiar do warstwy dolnej → dalej przesiąkanie (zimowa odbudowa). Ewapotranspiracja z strefy czynnej: uprawa Ks·Kc·ET0; **goła gleba (przed siewem, po zbiorze): Kc 0,35 × Kr**, Kr wg FAO-56 równ. 74 z TEW = WOD·Ze i REW = min(9 mm, TEW/2) (tab. 19: REW 8–10 mm) – parowanie ustaje, gdy wierzchnia warstwa przeschnie; spoczynek zimowy (oziminy, wieloletnie): Kc 0,4 (tab. 12, pszenica ozima z zamarzniętą glebą).
**Okno i stan początkowy:** od 1 XI roku poprzedzającego sezon (rzepak jesień: od 1 VII roku sezonu) do dnia przed analizą; dla daty przed startem sezonu – sezon poprzedni (stan liczony dalej bez przerwy). Na początku okna profil pomniejszony o deficyt bilansu P − ET0 z 92 dni przed oknem (stan po lecie), równy względny ubytek w obu warstwach. Zakres pobieranej pogody: od 1 VIII (rok − 12).

### D31 · 2026-11-21 · Terminy zbioru i kalendarz upraw w Polsce
**Terminy (zadanie A3b):** zboża ozime ok. 20 VII, jare ok. 5 VIII, rzepak ozimy ok. 15 VII, kukurydza na ziarno ok. 10 X, na kiszonkę ok. 15 IX, ziemniak ok. 15 IX, burak ok. 20 X. **Założenia:** strączkowe 10 VIII, warzywa gruntowe 31 VIII, tytoń 15 IX, rzepak jesień – koniec okresu jesiennego 30 XI, wieloletnie – 31 X; siew jesienny ozimin: pszenica 25 IX, rzepak 25 VIII (typowe terminy agrotechniczne).
**Konsekwencje:** proporcje faz z FAO-56 tab. 11 przeskalowane do okresu start–zbiór (`Crop.phases`). Oziminy: od siewu jesiennego do 31 X „wschody jesienne” (należą do następnego sezonu), od 1 XI do końca II „spoczynek zimowy”.

### D32 · 2026-11-21 · Dni stresu tylko w fazach wrażliwych; dojrzewanie nie liczone
**Uzasadnienie:** niedobór wody najsilniej obniża plon w fazie początkowej, rozwoju i pełni (kwitnienie, nalewanie); w dojrzewaniu wrażliwość plonu jest najmniejsza (współczynniki Ky, FAO-33 Doorenbos i Kassam). Waga 0 zamiast ułamkowej – prostszy i czytelniejszy komunikat dla rolnika, bez pozornej precyzji.
**Konsekwencje:** stres = faza wrażliwa i ubytek strefy korzeni > RAW. W dojrzewaniu, po zbiorze, przed siewem, we wschodach jesiennych i spoczynku: brak alarmu (`risk_7d` „Nie dotyczy”) i brak nawadniania – „Nawadnianie nieuzasadnione w tej fazie uprawy”.

### D33 · 2026-11-21 · Realistyczne nawadnianie (zastępuje dawkę „do pojemności polowej” z D29)
**Uzasadnienie:** jednorazowo gleba lekka przyjmie mniej wody niż ciężka; dawki 100+ mm są nierealne.
**Konsekwencje:** dawka jednorazowa = środek przedziału dla dominującej kategorii gleby IUNG: I 17,5 mm, II 22,5 mm, III 27,5 mm, IV 32,5 mm (brak kategorii → 22,5 mm); nigdy > 35 mm. Harmonogram z symulacji 7 dni (prognoza / scenariusz): dawka, gdy ubytek strefy korzeni > RAW, nie częściej niż co 2 dni; częstotliwość = odstęp między dawkami (albo dawka / średnie (ETc − opad efektywny), 2–14 dni); łączny niedobór = największa nadwyżka ubytku nad RAW w 7 dniach bez nawadniania (Ks = 1), zaokrąglona do 5 mm. Komunikat np. „27,5 mm teraz, powtórz za ok. 2 dni (w 7 dniach 3 dawki, niedobór ok. 70 mm)”.

### D34 · 2026-11-21 · Stan wody w glebie na każdą datę
**Uzasadnienie:** dane do rekomendacji jesienno-zimowych (retencja, międzyplony) i odpowiedź „jak teraz jest z wodą” także w listopadzie.
**Konsekwencje:** w fazach uprawy (początkowa…dojrzewanie) – strefa korzeni; poza nimi – cały profil ok. 1 m. Opis: < 50% → „niedobór wody po suchym lecie” (VIII–XII) / „po suchym okresie”; zapas rośnie (> 1 mm w 30 dni) → „gleba odbudowuje zapas wody”; ≥ 90% → „zapas wody w glebie odbudowany”; inaczej „zapas wody w normie”. Porównanie z tym samym dniem w 10 poprzednich latach (ciągły bilans każdego roku): w ilu latach było mniej wody. Podsumowanie zakończonego sezonu (dni stresu vs średnia 10 lat) jako informacja dodatkowa.

### D35 · 2026-11-21 · Ogólny stan wodny: wskaźnik 0–100, wagi i progi
**Składowe (0–100):** woda – % wody dostępnej (strefa korzeni w fazach uprawy, profil ~1 m poza nimi); ryzyko – dni do stresu: 0 → 0 pkt, ≤ 3 → 25, ≤ 7 → 50, ≤ 16 → 75, brak stresu w horyzoncie → 100 (tylko fazy wrażliwe); historia – średnia z „% lat z niższym bilansem wody od 1 III” i „% lat z mniejszym zapasem wody tego dnia”.
**Wagi:** fazy wrażliwe – woda 0,45, ryzyko 0,35, historia 0,20; pozostałe fazy – woda 0,65, historia 0,35. Brak składowej → wagi pozostałych przeskalowane; brak wody w glebie → `no_data`.
**Progi:** ≥ 70 ok, ≥ 50 warn, ≥ 30 risk, < 30 danger. Poza fazami wrażliwymi (dojrzewanie, po zbiorze, przed siewem, wschody jesienne, spoczynek) najwyżej **risk** i nagłówki o zapasie wody w glebie („Uwaga – mniejszy zapas wody w glebie niż zwykle”) – bez alarmu o stresie roślin. Grunt nierolny → `no_data` z komunikatem z sekcji `soil`.
**Uzasadnienie:** woda w glebie najlepiej oddaje stan na dziś; ryzyko – to, co stanie się za chwilę; historia – czy to normalne dla tego miejsca. Wagi do kalibracji z IUNG SMSR.

### D36 · 2026-11-21 · Pewność wyniku – punkty za przesłanki
**Metoda:** start 100 pkt, odejmowanie: brak satelity 15, brak terenu 10, pogoda NASA (~50 km) 10 albo źródło zapasowe 15, opóźnienie pogody > 3 dni 5, luka uzupełniona scenariuszem 10, > 10% dni Hargreavesa 10, brak prognozy (dziś) 10, data historyczna (ryzyko ze scenariusza) 5, brak gleby 35, gleba metodą punktową 10, część działki poza mapą IUNG 10, < 80% gleb rolnych mineralnych 5. Progi: ≥ 75 wysoka, ≥ 50 średnia, < 50 ograniczona. Bez zdjęć satelitarnych lub analizy terenu – najwyżej „średnia”.
**Konsekwencje:** `reason` = 3 najważniejsze przesłanki; źródła ze statusem ok / częściowo / brak (Sentinel-2, NMT, BDOT10k – „brak, w przygotowaniu”); kompletność bez EGiB (tylko informacyjnie); ograniczenia = z modułów + stałe (bez powtórzeń).

### D37 · 2026-11-21 · Przyczyny i ich udziały
**Wagi surowe:** opady – (średnia − opad)/średnia, gdy opad poniżej średniej z 10 lat; parowanie – (ET0 − średnia)/średnia, gdy powyżej; gleba – kat. I 0,50, II 0,35, III 0,20, IV 0,10; uprawa – 0,15 × Kc w fazach wrażliwych, 0,05 poza nimi (po pierwszym przeglądzie zmniejszone z 0,3, by uprawa nie przesłaniała niedoboru opadów); teren – brak danych, udział 0.
**Konsekwencje:** udziały = wagi / suma (zaokrąglone, suma dokładnie 100%), od największego; teren zawsze na końcu jako „brak danych (analiza terenu w przygotowaniu)”.

### D38 · 2026-11-21 · Silnik reguł rekomendacji (YAML)
**Uzasadnienie:** wymóg KOWR – żadnych gotowych tekstów bez danych; reguły czytelne i edytowalne bez zmiany kodu.
**Konsekwencje:** `analysis/rules/{retencja,agrotechnika,nawadnianie}.yaml`, 19 reguł; każda ma warunek (walidacja przy wczytaniu), fakt bez danych = warunek fałszywy, szablon z brakującym faktem = reguła pominięta; „Dlaczego?” i `inputs` z faktów, które uruchomiły regułę. Reguły wymagające terenu / wód w okolicy (oczko w zagłębieniu, zastawka, pas buforowy na stoku, mokradło) mają `requires` i są wyłączone do A6/A7. Kolejność: retencja → agrotechnika → nawadnianie, w grupie wg `priority`; `in_panel` – najważniejsza z każdej grupy (maks. 3). Kierunki działań wg listy z zadania A4 („Podstawy naukowe” KOWR) – treść dokumentu KOWR nie była czytana w tej sesji; do weryfikacji merytorycznej.

### D39 · 2026-11-21 · Pełne /api/analysis: czas, błędy, kroki
**Konsekwencje:** łączny budżet 27 s (zapas do 30 s): ULDK z własnym limitem, potem źródła równolegle z limitem = pozostały budżet. **502 tylko gdy brak działki (ULDK) albo pogody** (NASA POWER i archiwum Open-Meteo); awaria IUNG / KIEG / prognozy → brak danych w danej części, niższa pewność, krok `error`. 422: brak uprawy („Wybierz uprawę…”), nieznana uprawa, data z przyszłości lub starsza niż 10 lat. `steps` – każdy krok ze stanem i czasem (satelita i teren: `pending`, „w przygotowaniu”), ostatni krok `total` = czas całej analizy. Pomiar live: 1,2–2,5 s.

### D40 · 2026-11-21 · Konsultacja z mentorem 21.11 (prof. Gozdowski, SGGW, ekspert KOWR)
Wnioski (obowiązują przy regułach, raporcie i UI):
- **Rekomendacji mało i jasnych** – panel maks. 3, paszport/raport maks. 5.
- Rekomendacje niepewne oznaczamy wprost: **„obarczone dużym ryzykiem błędu”**; nigdy nie stoją na pierwszym miejscu.
- **Przy silnej suszy nawozy nie działają** – przy stresie wodnym zalecamy odłożenie nawożenia, żadna reguła nie zaleca wtedy nawożenia.
- **Dla rolnika najważniejsza jest gleba**: kategorie, frakcje (uziarnienie), przepuszczalność, zatrzymywanie wody przy ulewach, gruboziarnistość piasku, topografia.
- **Korzystać z gotowych modeli pogody** (u nas: NASA POWER, Open-Meteo/ERA5) – nie budujemy własnej interpolacji.
- Ważny **płodozmian** i **ekoschematy** (ARiMR) – pokazujemy powiązaną praktykę, bez kwot dopłat.
- Rekomendować przede wszystkim to, **co rolnik może zrobić bez pozwolenia**; przy każdej rekomendacji informacja o formalnościach.
- **Nawadnianie (pobór wody) wymaga pozwolenia wodnoprawnego – Wody Polskie.**
Źródła merytoryczne reguł: `docs/kowr/KOWR - Podstawy naukowe.pdf` (sekwencja: ocena → przyczyny → retencja → agrotechnika → nawadnianie; „retain water where it falls”; retencja glebowa: międzyplony, resztki pożniwne, ograniczenie intensywnej uprawy, materia organiczna; retencja krajobrazowa: oczka, mokradła, strefy buforowe, zadrzewienia).

### D41 · 2026-11-21 · Gleba dla rolnika: uziarnienie, przepuszczalność, woda z ulewy
**Źródło:** ISRIC SoilGrids 2.0 (REST, 250 m, licencja CC BY 4.0) – piasek/pył/ił i węgiel organiczny, średnia ważona 0–5, 5–15, 15–30 cm (5:10:15) w punkcie wewnątrz działki; limit 12 s, cache 7 dni. Brak danych w punkcie (woda, zabudowa) = poprawna odpowiedź „brak danych”, nie awaria.
**Klasa uziarnienia:** trójkąt USDA (algorytm NRCS) z nazwami po polsku (piasek, piasek gliniasty, glina piaszczysta, glina, glina pylasta, pył, glina piaszczysto-ilasta, glina ilasta, glina pylasto-ilasta, ił piaszczysty, ił pylasty, ił). Nie PTG 2008 – granice PTG dla piasków są drobniejsze i nie mam ich pewnie; gatunek z mapy glebowo-rolniczej (D43) ma pierwszeństwo w opisie dla rolnika.
**Przepuszczalność:** Ksat z równań Saxton i Rawls (2006), materia organiczna = 1,72 × węgiel org. (przycięta do 8%). Opisy: ≥ 50 mm/h bardzo duża, 25–50 duża, 12–25 średnia, 4–12 mała, < 4 bardzo mała.
**Woda z ulewy (progi):** Ksat ≥ 50 mm/h → „ucieka” (szybko wsiąka i przesiąka w głąb), 12–50 → „zatrzymuje”, < 12 → „splywa” (ryzyko spływu i zastoisk). Liczby ≥ 10 pokazujemy bez części dziesiętnej (bez pozornej precyzji).
**Ograniczenie:** Ksat silnie zależy od węgla organicznego (glina piaszczysta: OC 1% → ~51 mm/h, OC 3,7% → ~85 mm/h), a SoilGrids w warstwie 0–5 cm bywa zawyżony – opis w ograniczeniach raportu, reguła „spływ” ma pewność „ograniczona”.
**Gleba lekka (reguły):** kat. IUNG I–II albo gatunek z mapy pl, plp, ps, psp, ż, żp, pgl, pglp, pgm, pgmp (bardzo lekkie i lekkie) albo klasa USDA piasek / piasek gliniasty.

### D42 · 2026-11-21 · Rekomendacje po konsultacji (A5)
**Mało i jasno:** panel maks. 3 (`in_panel`, po jednej z grupy), paszport i raport maks. 5 – panel + najlepsze pozostałe wg wyniku = priorytet + pewność (wysoka +10, średnia 0, ograniczona −20) − 10 za każdy krok „później” − 5 za każdy stopień formalności.
**Kolejność w grupie:** pewne przed niepewnymi → bez formalności przed „maybe”/„required” → „teraz” przed „po zbiorze” i „przed następnym sezonem” → priorytet. Niska pewność = `warning` „Obarczone dużym ryzykiem błędu – traktuj jako wskazówkę i sprawdź na polu.”, nigdy pierwsza w grupie.
**Retencja zawsze:** 6 reguł zależnych tylko od fazy, rodzaju uprawy i bilansu wody (po zbiorze: międzyplon i słoma; nie zostawiaj ścierniska; zima bez orki – woda z roztopów; nie ugniataj mokrej gleby (oziminy); mniej uprawek przed siewem; okryta gleba w uprawach wieloletnich) – test sprawdza 15 upraw × 12 miesięcy. Do tego reguły zależne od gleby (próchnica, spływ przy ulewie) i 4 krajobrazowe czekające na teren (A6/A7).
**Formalności (`permit`):** agrotechnika, płodozmian, pasy buforowe, zadrzewienia – `none`; zastawki, oczka/stawy, mokradła – `maybe` (może wymagać zgłoszenia wodnoprawnego); nawadnianie – `required` (pozwolenie wodnoprawne). Link: https://www.gov.pl/web/wody-polskie.
**Nawożenie:** silny stres = faza wrażliwa i (Dr > RAW, tj. stres już jest, albo ryzyko 7 dni „wysokie”) → „Odłóż nawożenie – przy suszy nawóz nie zadziała”. Reguły oznaczone `fertilization: true` z terminem „teraz” są wtedy pomijane (test).
**Ekoschematy:** „Rolnictwo węglowe i zarządzanie składnikami odżywczymi” – praktyki: międzyplony ozime/wsiewki (E_MPW), uproszczone systemy uprawy (E_USU), wymieszanie słomy z glebą (E_WSG), zróżnicowana struktura upraw (E_ZSU), plan nawożenia (bez kodu – nie jestem pewien oznaczenia). „Retencjonowanie wody na TUZ” – w katalogu, ale żadna z 15 upraw nie jest TUZ, więc nieużywany. Bez kwot, z dopiskiem „Sprawdź aktualne warunki w ARiMR.” **Nazwy wg PS WPR 2023–2027 – nie weryfikowane z instrukcją ARiMR 2026 (brak dokumentu w repo).**
**Płodozmian:** parametr `previous_crop` (15 upraw lub `nie_wiem`). Reguła, gdy ta sama uprawa (rzepak = rzepak jesienny) albo zboże po zbożu (zboża ozime/jare); kukurydza nie liczy się jako „zboże” w tej regule. „Nie wiem” → brak reguły. Termin: przed następnym sezonem, ekoschemat E_ZSU.
**Nagłówek oceny (poprawka D35):** poza fazami wrażliwymi „Uwaga – mniejszy zapas wody… niż zwykle” tylko gdy bilans jest poniżej średniej z 10 lat; w przeciwnym razie „Uwaga – zapas wody w glebie niepełny”.

### D43 · 2026-11-21 · Mapa glebowo-rolnicza (WMS Geoportalu) – sprawdzone na żywo: DZIAŁA
**Usługa:** https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer, warstwa `0` (KONTURY_GLEBOWE), GetFeatureInfo WMS 1.3.0, EPSG:4326 (BBOX lat,lon), `INFO_FORMAT=text/xml` (format ESRI `<FIELDS …/>`). Zwraca: `KOMPLEKS` (kompleks przydatności rolniczej, np. 2, 6, 1z; poza rolnymi np. Tz, Tnk), `TYPPODTYP` (np. Bw, A, F), `PODLOZE1..5` (gatunek/uziarnienie kolejnych warstw: pl, ps, pgl, glp, l, li, płi…), `AKTUALNOSC` / `UWAGI` (rok mapy, np. 1966–1985).
**Test:** 7/7 punktów w 6 województwach z konturem (podlaskie, lubelskie, podkarpackie ×2, małopolskie, łódzkie, mazowieckie), 0,1–4 s; punkt poza zasięgiem (morze) → pusta odpowiedź.
**Konsekwencje:** `sources/soil_map.py` – kontur w punkcie wewnątrz działki, limit 7,5 s, cache 7 dni; w `soil.soil_map`: kompleks z nazwą, gatunek wierzchni z nazwą (gruboziarnistość piasku), głębsze warstwy, typ, rok mapy. Informacja dodatkowa (nie wchodzi do kompletności); rok mapy w ograniczeniach. Licencja: usługa przeglądania WMS GUGiK (bezpłatna); samych map do pobrania z PZGiK nie używamy.

### D44 · 2026-11-21 · Cache, dane z przeterminowanego cache, rozgrzewka przykładów
**TTL na wpis:** pogoda – dane sprzed tygodnia 7 dni, bieżące 6 h (NASA, archiwum Open-Meteo); działki ULDK, IUNG, KIEG, SoilGrids, mapa glebowo-rolnicza – 7 dni; prognoza 30 min.
**Odporność:** wpis po terminie zostaje do 30 dni. Gdy źródło nie odpowiada (błąd, przekroczenie limitu, bezpiecznik – D45), `cached_fetch` zwraca stary wynik; analiza zbiera takie użycia (`stale_scope`) → w `reliability`: źródło „częściowo” z notą „dane z cache z dnia DD.MM.RRRR GG:MM (źródło nie odpowiadało)”, ograniczenie o tym samym brzmieniu i **pewność o jeden poziom niżej**.
**Rozgrzewka:** przy starcie aplikacji w tle (`lifespan`, nie blokuje startu) 4 przykłady z `app/demo.py` liczone normalnym `run_analysis`, potem co 6 h; `DEMO_WARMUP=false` wyłącza (testy). Czas każdego przykładu w logu i w `/api/status`. Żadnych zapisanych wyników – po rozgrzewce analiza przykładu liczy się z danych w cache (~0,03 s).

### D45 · 2026-11-21 · Odporność źródeł: ULDK 302, limity na źródło, bezpiecznik
**ULDK:** przy dużym ruchu odpowiada `302 → integracja01.gugik.gov.pl/resp/uldk.php`, który zwraca pozorne „0” ze śmieciową geometrią (sprawdzone 21.11, przy keep-alive bywało 6/6 przekierowań). Wcześniej klient śledził przekierowanie i zgłaszał „nie znaleziono działki” (404). Teraz: bez śledzenia, do 6 prób z narastającą przerwą (0,25 s × n), ponowienia na nowym połączeniu (`Connection: close`); po wyczerpaniu – SourceError „usługa chwilowo ogranicza ruch” (502), z cache 7 dni i starym wpisem jako zapas. `/api/status` pokazuje przekierowanie jako błąd.
**Limity na źródło (łącznie, nie na operację httpx):** IUNG 14 s, KIEG 6 s, SoilGrids 12 s, mapa glebowo-rolnicza 7,5 s, prognoza 9,5 s (w `cached_fetch`, więc przekroczenie → stary wpis z cache); w routerze dodatkowa bariera o 0,5–1 s większa. KIEG potrafił wisieć 26 s.
**Bezpiecznik:** po awarii źródła pomocniczego nie pytamy go ponownie przez: KIEG, SoilGrids, mapa glebowo-rolnicza 5 min; prognoza, NASA POWER 2 min (NASA → od razu archiwum Open-Meteo); IUNG 1 min. Nie dotyczy ULDK. „Brak danych w tym miejscu” to nie awaria (nie wyzwala bezpiecznika).

### D46 · 2026-11-21 · Raport PDF
`GET /api/report.pdf?parcel_id=&crop=&date=&previous_crop=` = `run_analysis` + WeasyPrint (BSD) + Jinja2 (BSD) + segno (QR, BSD), czcionka Inter (OFL) z pakietu Debiana. Układ wg SPEC 10.2: nagłówek z datą wygenerowania i QR, działka z ortofotomapą Geoportalu (WMS `PZGIK/ORTO/WMS/StandardResolution`, warstwa `Raster`, EPSG:2180 – BBOX północ,wschód; kwadrat 1,5 × działka + 60 m; brak → napis „Ortofotomapa niedostępna”) i obrysem SVG, A–E, gleba i teren, źródła z datami, pewność, ograniczenia, stopka „raport pomocniczy” i numery stron. Wykresy SVG z Pythona (bilans narastająco z pasmem 10 lat, dni stresu w sezonach, opady miesięczne). Mapka miejsc rekomendacji – po analizie terenu (napisane wprost). **Link w QR:** `{PUBLIC_URL}/?dzialka=&uprawa=&data=&przedplon=` – frontend musi obsłużyć te parametry (prośba do B). Czas: 0,9–2,5 s przy danych w cache.

### D47 · 2026-11-21 · Przełącznik języka PL | EN (domyślnie polski) – zmienia D9
**Uzasadnienie:** prośba osoby B – interfejs ma być czytelny także dla osób nieznających polskiego (np. jury, goście). Polski zostaje językiem domyślnym, więc rolnik nic nie musi przełączać.
**Konsekwencje:** własny mały moduł `frontend/src/lib/i18n.ts` (bez nowej zależności): kluczem tłumaczenia jest tekst polski (`t('Szukam działki')`, zmienne `{n}`), słownik `lib/i18n.en.ts`, brak wpisu = tekst polski. Wybór zapamiętany w przeglądarce (`zw.lang.v1`), przełącznik w górnym pasku. Liczby i daty w formacie języka. Teksty z backendu (komunikaty błędów, rekomendacje, opisy) zostają po polsku, dopóki backend nie obsłuży języka – wyjątek: opisy pogody Open-Meteo i teksty mocka są w słowniku. Nowy tekst w UI = nowy wpis w `i18n.en.ts`.
*(pierwotnie D30, potem D35, potem D40 na gałęzi `b/frontend`; numer zmieniany przy scaleniach z `a/backend`, gdzie D30, D35 i D40 zajęła osoba A – ostatnio przy integracji INT1)*

### D48 · 2026-11-21 · Nawadnianie zgodne z praktyką w Polsce (`irrigation_practice`) – zmienia D33, D42
**Uzasadnienie:** zbóż, rzepaku i roślin strączkowych w Polsce się nie nawadnia (brak deszczowni, nieopłacalne, wymaga pozwolenia wodnoprawnego). Plan dawek dla pszenicy w suszy 2018 był merytorycznie błędny – rolnik nie ma czym tego zrobić.
**Konfiguracja (`analysis/crops.py`):** `not_practiced` – zboża ozime i jare, rzepak (oba), **rośliny strączkowe** (groch, bobik, łubin, soja na nasiona – bez nawadniania w PL); `optional` – kukurydza na ziarno i na kiszonkę, **burak cukrowy** (deszczownie tylko w części plantacji, gleby lekkie), **tytoń** (doraźnie przy wysadzaniu i w suszy); `common` – ziemniak, warzywa, drzewa i krzewy owocowe, truskawki, **chmiel** (plantacje zwykle z nawadnianiem kroplowym).
**Konsekwencje:** `not_practiced` – model nadal liczy stres i ryzyko 7 dni, ale `irrigation.status = nie_praktykowane`, bez dawek i planu; silnik reguł pomija całą kategorię „nawadnianie” (też bez uprawy). Przy stresie w fazie wrażliwej (≤ 7 dni do stresu) – 3 reguły zastępcze: zatrzymanie wody w glebie (retencja), ograniczenie strat wody: bez uprawek + odchwaszczanie (agrotechnika), zabiegi rano/wieczorem (agrotechnika); zdanie „Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie” (rzepak / strączkowe – odpowiednio). `optional` – plan dawek z dopiskiem „nawadnia się rzadko – ma sens tylko przy dostępnej wodzie i sprzęcie (pozwolenie wodnoprawne)”. Kontrola: „Susza 2018” (zboża ozime, 10.06.2018) – zero zaleceń nawadniania (test).

### D49 · 2026-11-21 · Zgodność źródeł gleby; kolejność: mapa glebowo-rolnicza > IUNG > SoilGrids
**Zbadane (201305, przykłady „Susza 2018” / „Mokry rok 2021”):** zgłoszony konflikt „IUNG kat. III, a mapa glebowo-rolnicza i SoilGrids – gleba lekka” był artefaktem JEDNEGO punktu. Mapa sprawdzona w 11 punktach działki: północna część – kompleks 6 (żytni słaby), piasek gliniasty lekki na piasku słabogliniastym i luźnym (3 punkty, ~25–35%), reszta – kompleks 2 (pszenny dobry), glina lekka pylasta na glinie średniej pylastej. IUNG: 75% kat. III, 25% kat. I – **zgodne z mapą**. SoilGrids (250 m): glina piaszczysta (lekka) – uśrednia oba kontury i jest najmniej dokładny. Pozostałych działek z przykładów (061704, 143203) nie dało się sprawdzić – ULDK ograniczał ruch (302) przez całą sesję.
**Wspólna skala:** kategorie agronomiczne gleb (PTG 1989), na których IUNG opiera kategorie podatności: I bardzo lekka (pl, ps, ż), II lekka (pgl, pgm, żg), III średnia (gl, glp, płz, l), IV ciężka (gs, gc, płi, i, li); SoilGrids (USDA): piasek / piasek gliniasty → I, glina piaszczysta → II, glina / glina pylasta / pył → III, gliny ilaste i iły → IV.
**Kolejność ważności:** mapa glebowo-rolnicza 1:5000 (badania terenowe; **9 punktów**: reprezentatywny + 8 rozłożonych, tylko kontury z kompleksem rolnym) > mapa IUNG (5 m, uogólniona) > SoilGrids (model globalny 250 m).
**Konflikt:** mapa vs IUNG – porównujemy **udział gleb lekkich (I–II) w działce**, konflikt przy różnicy > 40 p.p. (działka na dwóch konturach to nie konflikt – notka „na działce są dwie gleby…”); inne pary (np. bez mapy: IUNG vs SoilGrids) – różna grupa dominującej kategorii (lekka I–II vs średnia/ciężka III–IV).
**Konsekwencje:** `soil.consistency` {status ok/conflict, note, basis, category_used, by_source}. Zgodne – WOD z IUNG (udziały komórek w całej działce, spójne z SMSR). Konflikt rozstrzygnięty przez mapę – kategoria i WOD (wartość typowa IUNG dla kategorii, średnia ważona po punktach mapy), `soil.wod_mm` i `soil_capacity` z opisem źródła; sekcja IUNG (`dominant_code`, `shares`) bez zmian; pewność −10 pkt („gleba_konflikt”) i ograniczenie. Gdy IUNG nie odpowiada – kategoria z mapy, a bez niej z SoilGrids (model liczy się dalej, pewność nadal obniżona). Las, woda, zabudowa – zawsze wg IUNG (użytkowanie 2024; mapa glebowo-rolnicza z lat 60.–80.).

### D50 · 2026-11-21 · „Stan działki” bez uprawy: pokrycie referencyjne FAO-56
**Uzasadnienie:** deklaracje upraw ARiMR nie są publiczne – nie wiemy, co rośnie. Stan wody musi być znany od razu po wybraniu działki (punkt 1 przepływu panelu). Rozważone: ugór czarny (goła gleba, FAO-56 rozdz. 7) – woda paruje tylko z ~12 cm, więc latem profil zostaje mokry i „susza 2018” wyglądałaby dobrze; pokrycie referencyjne (trawa, dla której z definicji liczy się ET0) – ta sama powierzchnia, dla której IUNG liczy KBW = opad − ET0, więc wynik jest spójny z oficjalnym bilansem.
**Metoda (`analysis/field_state.py`):** Kc = 1 przez cały rok, korzenie w całym profilu ~1 m (WOD, D25), p = 0,5 (FAO-56 tab. 22: pastwiska 0,6, trawniki chłodnego klimatu 0,4), Ks równ. 84; ten sam dzienny bilans co dla upraw (`run`, opad efektywny D26, stan początkowy z 92 dni). Przebieg od 1 XI (rok hydrologiczny; gdy minęło < 30 dni – od 1 XI roku wcześniej) z pasmem min/max/średnia z 10 lat i porównaniem z tym samym dniem; luka opóźnienia NASA – jak w D27.
**Kontrakt:** `field_state` liczony zawsze (z uprawą i bez), null dla gruntu nierolnego; bez uprawy `crop`, `crop_season`, `irrigation` = null, `history.stress_days_by_year` = [], `risk_7d` „Nie dotyczy”, przyczyny bez czynnika „uprawa”, rekomendacje – tylko retencja (3 reguły wg pory roku + zależne od gleby). `suggestions` = null – miejsce na ranking „Co tu posiać?” (A5b-2). PDF bez uprawy: krótszy raport „Stan wodny działki”.

### D51 · 2026-11-21 · Ekoschematy – tylko potwierdzone kody ARiMR 2026 (zmienia D42)
Dozwolone: E_MPW (międzyplony ozime / wsiewki), E_USU (uproszczone systemy uprawy), E_WSG (wymieszanie słomy z glebą), E_PN (plan nawożenia), E_MIOD (rośliny miododajne), E_EKSTUZ (ekstensywne użytkowanie TUZ z obsadą). Usunięte: E_ZSU (płodozmian – bez ekoschematu), plan nawożenia bez kodu i „retencjonowanie wody na TUZ” bez kodu; „Odłóż nawożenie” – bez ekoschematu. Kod spoza listy = błąd przy wczytaniu reguł (test sprawdza też surowy YAML). Nadal bez kwot, z „Sprawdź aktualne warunki w ARiMR.”

### D52 · 2026-11-21 · Status poza sezonem uprawy i bez uprawy: zapas wody + bilans 30 dni (zmienia D35)
**Problem:** „Kukurydza dziś” (listopad, po zbiorze) dawała „Ryzyko 39” – historia (bilans od 1 III, najgorszy z 10 lat) karała za suche lato i stres kukurydzy, choć pola już nic nie potrzebuje.
**Metoda (`scoring.reserve_status`):** przed siewem, po zbiorze, we wschodach jesiennych i w spoczynku zimowym (oraz bez uprawy) wskaźnik = 0,6 × woda dostępna w profilu ~1 m + 0,4 × pozycja bilansu opad − ET0 z ostatnich 30 dni wśród 10 lat (0–100); progi jak D35. Poza sezonem najwyżej „risk” (bez „Suszy”), etykieta `status.scope_label = „poza sezonem”`; bez uprawy możliwa „Susza glebowa” (`scope = bez_uprawy`, „stan wody na działce”). Nagłówek „mniejszy zapas niż zwykle” tylko, gdy w mniej niż połowie z 10 lat tego dnia było mniej wody. Dojrzewanie – bez zmian (D35). `status.scope = sezon` w fazach uprawy.

### D53 · 2026-11-21 · Trwały cache SQLite dla wszystkich źródeł (zmienia D44)
**Uzasadnienie:** ULDK GUGiK blokuje IP sieci hackathonu (302 → resp/uldk.php); cache w pamięci znikał przy każdym restarcie i reloadzie, więc nawet raz pobrana działka wymagała ULDK ponownie. Na prezentacji jury nie może zobaczyć błędu.
**Metoda (`core/cache.py`):** jedna warstwa – `TTLCache` (pamięć) + jeden plik SQLite (`CACHE_DB`, tabela `ns, k → stored_at, ttl_s, value`, WAL, wartości przez pickle – plik pisze i czyta tylko aplikacja). Klucz = przestrzeń nazw źródła + `repr` znormalizowanych parametrów (współrzędne zaokrąglone do rozdzielczości: NASA 0,1°, archiwum Open-Meteo 0,1°, prognoza 0,01°, SoilGrids 1e-4°, mapa glebowo-rolnicza 1e-5°, IUNG – skrót WKT działki, KIEG – id działki, ortofotomapa – BBOX co 0,1 m). Czas zapisu ścienny (UTC) – wiek poprawny po restarcie. Plik niedostępny → ostrzeżenie w logu i praca na samej pamięci (nigdy błąd startu).
**TTL:** działki ULDK, IUNG, mapa glebowo-rolnicza, SoilGrids, KIEG, ortofotomapa – **bez wygasania**; pogoda NASA POWER i archiwum Open-Meteo – zakres kończący się ponad 7 dni temu **bez wygasania**, bliższy dziś 6 h (NASA uzupełnia ostatnie dni z opóźnieniem); **prognoza 1 h**. Wpis po TTL nadal 30 dni jako zapas przy awarii (D44). NMT, BDOT10k, GUS – klientów jeszcze nie ma (teren – osoba C); mają używać `cached_fetch` (proponowane: NMT i BDOT10k bez wygasania, GUS 30 dni).
**Docker:** wolumen `cache-data:/data` (Dockerfile: `/data` należy do `appuser`), `uvicorn --reload-dir app` – zapis cache ani skryptów nie przeładowuje serwera.

### D54 · 2026-11-21 · Działki bez zbędnych zapytań do ULDK, blokada i bezpiecznik
**Indeks znanych działek (`sources/uldk.py`):** każda pobrana działka zapisana także pod kluczem `("id", <id>)`, indeks z całego cache + `app/data/demo_parcels.json` przy starcie. Po pełnym id i po punkcie (shapely: punkt w obrysie) – najpierw indeks, ULDK tylko dla nieznanych. „Obręb numer” – ULDK (może być kilka działek w Polsce), a przy blokadzie – dopasowanie wśród znanych.
**Działki demo w repo:** `app/data/demo_parcels.json` – działki z `/api/demo/examples` + Wnory-Wandy 6/1, Szczytno 126/3 (gm. Kampinos), Lasotka 118. Pełne dane ma tylko 201305_2.0038.6/1 (zapisana odpowiedź ULDK); pozostałe z `needs_fetch: true` – uzupełni je `scripts/warm_demo.py`, gdy ULDK odpowie (zapisuje plik).
**Blokada ULDK:** 429, przekierowanie 3xx albo HTML zamiast odpowiedzi tekstowej → ponowienia po 1 s i 3 s (maks. 2), każde na nowym połączeniu, potem czytelny błąd 502 i **bezpiecznik 60 s** (zmienia D45: ULDK też ma bezpiecznik; wcześniej 6 prób co 0,25 s × n). Bezpiecznik wspólny dla wszystkich źródeł (`cached_fetch(breaker_s=)`, stan na źródło, czas ścienny). `/api/status`: źródło z otwartym bezpiecznikiem nie jest odpytywane – „ograniczony (do HH:MM, czas polski) – powód”; blokada wykryta zapytaniem testowym otwiera bezpiecznik ULDK. Rozgrzewka przykładów nie pyta ULDK o działki znane z cache / repo.

### D55 · 2026-11-21 · Tryb demo offline i przygotowanie prezentacji
**`DEMO_OFFLINE=true`:** żadnych zapytań zewnętrznych (`cached_fetch` zwraca tylko cache – także przeterminowany, bez obniżania pewności; `get_with_retry` odmawia), brak danych = 502 z komunikatem „brak tych danych w pamięci podręcznej (tryb demo offline…)”, nigdy 500. `/api/status` bez zapytań testowych. `/api/demo/examples` w trybie offline pokazuje tylko przykłady, które liczą się z samego cache (szybka próba analizy), a przy otwartym bezpieczniku ULDK – tylko te z działką znaną lokalnie (gdy nic – wszystkie). Kontrakt bez zmian.
**Przygotowanie:** `scripts/warm_demo.py` (na dobrej sieci: brakujące działki z ULDK, potem dla każdej działki demo analiza bez uprawy + przykłady + PDF-y; przerwy między zapytaniami, to co w cache – z cache), `scripts/demo_check.py` (ścieżka demo po HTTP z czasami i stanem źródeł). `scripts/smoke_cached_uldk.py` z A5b-1 usunięty – zastąpiony przez działki demo w repo.

### D56 · 2026-11-21 · Żadnych przekierowań i limity odpowiedzi dla wszystkich źródeł; uczciwy User-Agent
**Uzasadnienie:** GUGiK przy limicie przekierowuje na integracja01.gugik.gov.pl/resp/uldk.php, który serwuje plik ~126 MB; NMT potrafi zwrócić odpowiedź-śmieć (setki MB). Podążanie za przekierowaniem albo czytanie jego treści zawiesza analizę i zalewa serwer.
**Konsekwencje (`core/http.request`):** wspólny klient z `follow_redirects=False`; każde zapytanie czytane strumieniowo – odpowiedź 3xx → `RedirectBlocked` (podklasa SourceError, „ograniczenie ruchu”) **bez czytania treści** (połączenie zamykane od razu); treść > `max_bytes` (zadeklarowana albo w trakcie odczytu; domyślnie 30 MB, ULDK 5 MB, NMT 80 B × punkty) → przerwanie; odczyt > 2 × limit czasu → przerwanie; uszkodzona kompresja → SourceError (nie 500). Przez `request` idą `get_with_retry` (IUNG, KIEG, SoilGrids, mapa glebowo-rolnicza, NASA, archiwum Open-Meteo, ortofotomapa, sondy /api/status), ULDK, prognoza Open-Meteo i NMT. User-Agent: „Wodoskop/0.1 (HackNation 2026)”. Testy: 302 z treścią, której odczyt jest błędem (ULDK, NMT, dowolne źródło), cel przekierowania nigdy nie odpytany; gzip dekodowany raz.

### D57 · 2026-11-21 · Teren z NMT: port prototypu osoby C, cache, zapisany wynik jako zapas
**Źródło:** `research/terrain/` z gałęzi `c/research` (bez merge – pliki przez `git show`). Rdzeń `analyze_surface` i funkcje rastrowe przeniesione BEZ ZMIAN do `analysis/terrain.py` (czysty numpy; testy prototypu → `tests/test_terrain.py`); pobieranie urllib zastąpione `sources/nmt.py` (httpx async, POST po 1000 punktów, 6 równolegle, ponowienia, x = PÓŁNOC, y = WSCHÓD). Metoda i progi: research/terrain/NOTES.md (siatka ~5 m/ha^0,37 + bufor 100 m, σ = 6 m, stok ≥ 3%, górka TPI ≥ 0,3 m, dołek TPI ≤ −0,3 m / TWI ≥ 11 / zagłębienie ≥ 0,2 m i 50 m², odpływ ≥ 5% działki).
**Cache:** cała siatka wysokości działki pod kluczem siatki – bez wygasania, tylko komplet (błąd paczki = brak zapisu); bezpiecznik 120 s; wynik obliczeń w pamięci (32 działki) dla analizy, warstw i raportu. Obliczenia < 0,2 s w wątku (`asyncio.to_thread`).
**Zapisany wynik (`app/data/terrain/<id>.facts.json` + `.geojson`):** prawdziwe NMT policzone tym samym kodem przez osobę C 21.11.2026 dla działek demo 201305_2.0038.6/1 i 061704_2.0011.383/2. Używany tylko, gdy NMT nie odpowiada (dziś blokuje IP sieci hackathonu – 302) albo w DEMO_OFFLINE bez cache; oznaczony w ograniczeniach („z zapisanego wyniku analizy NMT z 21.11.2026”), źródło NMT „częściowo”. Ukształtowanie terenu się nie zmienia, więc to uczciwy zapas (jak `demo_parcels.json`). `TERRAIN_SAVED_RESULTS=false` wyłącza (testy).
**Brak NMT i zapisu:** `terrain = null` + `terrain_note` z powodem, analiza działa dalej, reguły terenowe wyłączone, pewność bez zmian względem A5 („brak analizy terenu”).
**Data analizy:** NMT jest jeden (aktualny) – dla dat historycznych używamy go także (teren praktycznie się nie zmienia); wyjątek od zasady „tylko dane sprzed daty”, zapisany tu.
**Wpływ na wynik:** teren nie zmienia modelu wody w glebie (spływ nadal 20% opadu > 20 mm, D26) – opisuje, gdzie na działce jest sucho / mokro; w przyczynach czynnik „teren” = 0,2 × udział stoków i górek.

### D58 · 2026-11-21 · Teren × gleba – ocena stref i zdania dla rolnika
**Reguły:** `analysis/rules/teren_gleba.yaml` (obok reguł rekomendacji, klucz `teren_gleba` – silnik rekomendacji go nie wczytuje). Gleba z kategorii użytej w modelu wody (`soil.consistency.category_used`): lekka = I–II, zwięzła = III–IV, nieznana. Oceny: górka – lekka **źle**, zwięzła uwaga; stok – uwaga; płasko – **dobrze**; dołek – lekka **dobrze** (najwilgotniej w suszy), zwięzła **źle** (woda stoi, uprawy wymakają), nieznana uwaga. Strefa < 1% działki – bez oceny i zdania. Nazwy dla rolnika: „górka – sucho”, „stok – woda ucieka”, „płasko – dobre warunki”, „dołek – woda stoi”; kolory: górka #8B6B4A, stok #E8B931, płasko #5BB37F, dołek #2F80C9.
**Podsumowanie (2–3 zdania, bez żargonu):** ukształtowanie (prawie płaska < 2%, lekko nachylona < 5%, nachylona < 10%, stroma) z różnicą wysokości i średnim spadkiem; którędy woda ucieka (i dopływ spoza działki, gdy ≥ jej powierzchni); zagłębienia bez odpływu albo ich brak. TWI, D8, priority-flood – tylko w `terrain.details` („dla dociekliwych”).
**Poprawka przy okazji:** reguła „Zwiększaj próchnicę” uruchamia się też przy dużej przepuszczalności – tytuł „lekka gleba trzyma mało wody” był sprzeczny z oceną terenu na glebie zwięzłej (201305) → „gleba zatrzyma więcej wody”.

### D59 · 2026-11-21 · Rekomendacje z terenu – progi i formalności (zmienia D42)
**Oczko / zbiornik (`terrain_interpret.py`):** **główna** rekomendacja tylko przy wyraźnym zagłębieniu bez odpływu – głębokość ≥ 0,3 m (3× precyzja NMT), zlewnia ≥ 0,5 ha (inaczej z ulewy 20 mm spłynie ledwie kilkanaście m³), działka ≥ 0,5 ha. **„Do rozważenia”** (priorytet 30, pewność ograniczona → ostrzeżenie, nigdy w panelu) – brak wyraźnego zagłębienia (oczko przy odpływie) albo płytkie zagłębienie / mała działka, przy zlewni ≥ 0,5 ha i działce ≥ 0,3 ha. Poniżej – nic. 201305 (0,58 ha, 2 m różnicy, brak zagłębień, zlewnia 1,9 ha) → „do rozważenia”; 061704 (zlewnia 0,3 ha) → brak.
**Pas buforowy / zadrzewienie:** propozycja prototypu (spadek > 5% na ≥ 10% działki) → „Pas zieleni lub zadrzewienie w poprzek stoku”, bez formalności, ekoschemat E_MIOD (pas roślin miododajnych – z listy D51).
**Zastawka:** odpływ główny ≥ 50% działki i dopływ z zewnątrz ≥ powierzchni działki → „Sprawdź rów przy miejscu odpływu” (pewność ograniczona – rowów z BDOT10k jeszcze nie mamy), zgoda właściciela rowu / spółki wodnej.
**Mokradło:** zagłębienie bez odpływu ≥ 500 m² w działce → „Zostaw podmokły fragment” – **bez formalności** (to zaniechanie prac; D42 dawało „maybe”).
**Formalności oczka:** progów Prawa wodnego / Prawa budowlanego (powierzchnia, głębokość, odległości) NIE zweryfikowałem – tekst ogólny: „może wymagać zgłoszenia lub pozwolenia (Prawo wodne, Prawo budowlane) – zależy od wielkości, głębokości i miejsca; zapytaj w Wodach Polskich i w starostwie” + link Wód Polskich (pole reguły `permit_note`).
