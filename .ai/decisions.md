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

### D28 · 2026-11-21 · Zapas wody na start sezonu
**Uzasadnienie:** po suchej zimie profil nie jest pełny. Bez danych o wilgotności gleby przyjmujemy pojemność polową, zmniejszoną o deficyt bilansu P − ET0 w oknie przed sezonem: Dr0 = min(TAW, |bilans|), gdy bilans ujemny (mm za mm – proporcjonalnie do TAW).
**Konsekwencje:** okno od 1 XI roku poprzedniego do startu (siew/wegetacja wiosenna); dla siewu letnio-jesiennego (rzepak jesień) od 1 VII – okno od listopada objęłoby całe lato poprzedniej uprawy. Zakres pobieranej pogody rozszerzony do 1 XI (rok sezonu − 11) – okno najstarszego sezonu porównawczego. Brak danych w oknie (> 20%) → start z pełnym profilem + ograniczenie.

### D29 · 2026-11-21 · Nawadnianie i stan poza sezonem
**Uzasadnienie:** zalecenie tylko wtedy, gdy model pokazuje stres teraz lub w ciągu 7 dni; dawka liczona, nie zgadywana.
**Konsekwencje:** dawka = ubytek do pojemności polowej w dniu przekroczenia RAW, zaokrąglona do 5 mm (min. 5 mm); powyżej 40 mm dopisek „w praktyce w N dawkach po ok. 30–35 mm”. Rekomendacja w formacie kontraktu (`category = nawadnianie`, dane wejściowe, pewność: średnia przy prognozie, ograniczona przy scenariuszu). Przed sezonem uprawy – brak wskaźników „na dziś” i brak dni stresu; po sezonie – tylko podsumowanie dni stresu zakończonego sezonu na tle 10 lat.
