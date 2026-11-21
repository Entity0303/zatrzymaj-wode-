# Specyfikacja UI/UX – „Zatrzymaj wodę” (HackNation 2026, KOWR)

Dokument wykonawczy dla Claude Code. Opisuje **pełny wygląd i zachowanie** aplikacji. Funkcje i źródła danych opisuje CLAUDE.md – tu jest wszystko o tym, JAK to ma wyglądać i działać na ekranie.

Grafiki wzorcowe: `design/ref-desktop.png` (układ komputera), `design/ref-mobile.png` (telefon, legendy warstw), `design/ref-style.png` (styl kart i wskaźników).

---

## 0. Wizja i zasada nadrzędna

Rolnik wpisuje numer działki, wybiera uprawę i datę analizy. Aplikacja pobiera publiczne dane (działka, pogoda, gleba, teren, satelita, wody) i pokazuje **zrozumiały cyfrowy obraz jego pola**.

**Ścieżka:** Szukaj działki → Zobacz pole → Zrozum jego stan → Dostań rekomendacje → Pobierz raport.

**Zasada 30 sekund:** rolnik w 30 sekund rozumie stan pola i widzi najważniejsze działanie do wykonania.

**Mapa jest produktem. Dane czynią mapę mądrą. Rekomendacje czynią ją użyteczną.**

Aplikacja ma przypominać połączenie: Map Google (znajoma nawigacja) + nowoczesnej platformy rolniczej (sensowne dane o glebie i roślinach) + prostej aplikacji konsumenckiej. Nie może wyglądać jak skomplikowany program GIS ani korporacyjny dashboard.

---

## 1. Użytkownik

Zwykły rolnik w Polsce: ograniczona wiedza techniczna, nie zna terminów GIS ani wskaźników satelitarnych, woli obraz niż wykresy, chce konkretnych zaleceń, a nie surowych danych. Korzysta z komputera, tabletu i telefonu (także na polu, w słońcu).

**Interfejs wyłącznie po polsku.** Terminy techniczne tylko w rozwijanych sekcjach „Szczegóły”.

### Słownik interfejsu (zawsze używaj lewej strony w głównym UI)

| W interfejsie | Termin techniczny (tylko w „Szczegółach”) |
|---|---|
| Kondycja upraw | NDVI (Sentinel-2) |
| Wilgotność roślin | NDMI (Sentinel-2) |
| Bilans wody | KBW = opad − ET0 |
| Woda tracona przez parowanie | ET0 (FAO-56 Penman-Monteith) |
| Ile wody zmieści gleba | WOD (woda ogólnie dostępna), kategoria IUNG |
| Woda w glebie | model bilansu wody w glebie FAO-56 |
| Teren | NMT (numeryczny model terenu GUGiK) |
| Spływ wody | kierunki spływu D8, akumulacja, TWI |
| Działka 112/11 | identyfikator ULDK 143203_2.0027.112/11 |

---

## 2. Tożsamość wizualna

### 2.1 Charakter
Czysty, nowoczesny, inspirowany naturą. Spokojny, godny zaufania, przystępny. Bez neonów, bez ciężkich gradientów, bez glassmorphismu, bez futurystyki.

### 2.2 Paleta (tokeny – zdefiniuj jako zmienne CSS / theme Tailwind)

| Token | Hex | Użycie |
|---|---|---|
| `brand` (leśna zieleń) | `#2F6B47` | logo, główne przyciski, aktywna nawigacja, nagłówki akcentowe |
| `brand-dark` | `#1F4D33` | hover przycisków, przycisk „Pobierz raport” |
| `ok` (jasna zieleń) | `#5BB37F` | dobry stan, zdrowe uprawy |
| `ok-soft` | `#E6F4EA` | tło odznak/kart „dobrze” |
| `bg` (ciepła złamana biel) | `#F8F6F1` | tło aplikacji |
| `surface` | `#FFFFFF` | karty, panele |
| `surface-2` (jasny beż) | `#EFEBE3` | drugorzędne powierzchnie, pola formularzy |
| `earth` (brąz) | `#8B6B4A` | gleba, teren |
| `water` (niebieski) | `#2F80C9` | woda, wilgotność, rowy |
| `water-soft` | `#E3F0FB` | tło kart wody |
| `warn` (żółty) | `#E8B931` | uwaga, umiarkowane ryzyko |
| `warn-soft` | `#FDF4D8` | tło odznak „uwaga” |
| `risk` (pomarańcz) | `#E07B39` | wysokie ryzyko |
| `danger` (czerwony) | `#C8453B` | susza, stan krytyczny |
| `danger-soft` | `#FBE7E5` | tło odznak „problem” |
| `text` | `#1E2A23` | tekst główny |
| `text-muted` | `#5F6B64` | tekst drugorzędny |
| `border` | `#E3DED4` | obramowania kart |

Statusy (spójne w całej aplikacji – mapa, odznaki, raport):
🟢 **Dobrze** (`ok`) · 🟡 **Uwaga** (`warn`) · 🟠 **Ryzyko** (`risk`) · 🔴 **Susza** (`danger`) · ⚪ **Brak danych** (szary `#B8BDB9`, kreskowanie).

### 2.3 Typografia
- Krój: **Inter** (fallback: system-ui). Cyfry tabelaryczne dla liczb (`tabular-nums`).
- Skala: H1 28/34 semibold · H2 22/28 semibold · H3 18/24 semibold · tekst 16/24 · drobny 14/20 (minimum – nic mniejszego poza przypisami źródeł 12/16) · duże liczby wskaźników 32–40 semibold.
- Krótkie zdania. Liczby zawsze z jednostką (mm, ha, %, dni).

### 2.4 Kształty, cienie, odstępy, ikony
- Zaokrąglenia: karty 16 px, przyciski i pola 12 px, pigułki/odznaki pełne (9999 px).
- Cień kart: `0 1px 2px rgba(30,42,35,.06), 0 4px 16px rgba(30,42,35,.06)`. Pływające elementy na mapie: nieco mocniejszy cień.
- Siatka odstępów 4 px; wewnątrz kart 16–20 px; między kartami 12–16 px.
- Ikony: **lucide-react** (MIT), obrys 1,75 px, rozmiar 20 px (24 px w nawigacji).
- Animacje: subtelne, 150–250 ms (wysuwanie paneli, przejście mapy `flyTo` ~1 s). Szanuj `prefers-reduced-motion`.

---

## 3. Nawigacja i architektura informacji

Cztery sekcje (lewy pasek na komputerze, dolny pasek zakładek na telefonie):

1. **Start** – mapa + przegląd gospodarstwa + paszport wodny wybranej działki.
2. **Moje działki** – lista zapisanych działek (pamięć przeglądarki), status każdej, szybkie przejście do mapy.
3. **Raporty** – poprzednie paszporty wodne (pamięć przeglądarki), pobieranie PDF, drukowanie, link do udostępnienia.
4. **Ustawienia** – podkład mapy domyślny, jednostki, tryb „rolnik / doradca” (doradca = więcej liczb i wykresów widocznych od razu), wyczyszczenie zapisanych danych.

Bez kont i logowania. Żadnych dodatkowych pozycji menu.

---

## 4. Ekran Start – komputer (≥ 1280 px)

Wzorzec: `design/ref-desktop.png`.

```
┌────┬──────────────────────────────────────────────────────────────────────┐
│    │ [🔍 Wpisz numer działki…        ] [📍 Moja lokalizacja]   ☀ 18°C  📅 Data analizy │
│ L  │ [Kondycja upraw][Wilgotność roślin][Teren][Spływ wody][Gleba]  [2D|3D] │
│ E  │                                                   ┌───────────────┐   │
│ W  │                 M A P A  (pełny ekran pod spodem) │ PANEL DZIAŁKI │   │
│ Y  │      obrys działki + kolorowa warstwa w obrysie   │  (380 px)     │   │
│    │                                                   │               │   │
│ P  │  [+][−][⌖ wróć do działki]        [legenda]       │               │   │
│ A  │                                                   └───────────────┘   │
│ S  │ ┌──────────┬────────────┬──────────┬────────────┬─────────────┐      │
│ E  │ │Gospodar- │ Bilans wody│ Alerty   │ Prognoza   │ Oś czasu    │      │
│ K  │ │stwo      │ (trend)    │          │ 7 dni      │             │      │
└────┴─┴──────────┴────────────┴──────────┴────────────┴─────────────┴──────┘
```

### 4.1 Lewy pasek (szer. 96 px na komputerze, ikona + podpis pod spodem)
- Na górze logo: kropla w liściu + napis „Zatrzymaj wodę” (na wąskim pasku tylko znak).
- Pozycje: Start, Moje działki, Raporty, Ustawienia. Aktywna: tło `ok-soft`, ikona i tekst `brand`, pasek 3 px po lewej.
- Na dole mała karta z hasłem „Oszczędzaj wodę. Chroń plony.” z ilustracją pola (jak na ref-desktop).

### 4.2 Górny pływający pasek (nad mapą, karty z cieniem)
- **Wyszukiwarka** (szer. ~420 px, wys. 48 px, zaokrąglona pigułka): ikona lupy, placeholder „Wpisz numer działki, np. 143203_2.0027.112/11 lub Szczytno 112/11”. Enter = szukaj. Pod spodem lista podpowiedzi przy wielu wynikach.
- **„📍 Moja lokalizacja”** – przycisk-pigułka.
- Po prawej: **pogoda teraz** (ikona, temperatura, opis – Open-Meteo dla środka działki lub środka mapy) i **„📅 Data analizy”** (kalendarz; zakres: dziś − 10 lat … dziś; zmiana daty przelicza analizę).
- Druga linia: **pigułki warstw** (sekcja 5.3) i przełącznik **2D | 3D** (segmentowany, 3D nieaktywne do czasu implementacji – z dymkiem „Wkrótce”).

### 4.3 Mapa
Patrz sekcja 5. Zajmuje całe tło obszaru treści.

### 4.4 Prawy panel działki (szer. 380 px, pływająca karta, przewijana)
Patrz sekcja 6. Gdy nie wybrano działki – pusty stan z instrukcją.

### 4.5 Dolny pasek kart (wys. ~150 px, 5 kart w rzędzie)
1. **Gospodarstwo** – liczba zapisanych działek (duża cyfra), ogólny stan w okręgu (np. „Dobrze 2 · Uwaga 1”), liczba działek wymagających uwagi.
2. **Bilans wody** – mała linia: bilans wody od początku sezonu na tle pasma z 10 lat (min–max) i średniej. Podpis np. „−84 mm względem średniej”.
3. **Alerty** – maks. 2 najważniejsze (ikona, tekst, czas), np. „Działka 112/11 – stres wodny za ok. 6 dni”, „Rów przy działce 6/1 zgłoszony jako zarośnięty”. Brak alertów: zielony ✓ „Brak alertów”.
4. **Prognoza 7 dni** – dzień, ikona, temp. maks/min, **suma opadu w mm** (niebieski) i parowanie (mm). Na dole: „Bilans tygodnia: −12 mm”.
5. **Oś czasu** – skrót sekcji 9 (mini-pasek miesięcy z kolorami stanu) + „Ostatnia aktualizacja danych: …”.

---

## 5. Interaktywna mapa 2D (domyślna)

### 5.1 Podkład i obrysy
- Podkład: **ortofotomapa Geoportalu**; zapasowo OpenStreetMap (przełącznik w Ustawieniach i w małym przycisku warstw podkładu w rogu mapy).
- Wybrana działka: **biały obrys 3 px**, delikatna poświata (cień), etykieta-pigułka w środku: „Działka 112/11” + ikona stanu (jak „Good Health” na ref-desktop).
- Sąsiednie działki (po przybliżeniu ≥ 16): cienkie białe linie 1 px, przezroczystość 50% (warstwa działek z KIEG/ULDK), klikalne.
- Kolorowe warstwy danych **przycinane do obrysu działki** (poza obrysem nie malujemy danych pola).

### 5.2 Kontrolki mapy (lewy dolny róg, pionowa grupa białych kwadratowych przycisków 44 px)
`+` przybliż · `−` oddal · `⌖` wróć do mojej działki · `◎` moja lokalizacja. Skala w lewym dolnym rogu. Atrybucje źródeł w prawym dolnym rogu (małe, ale czytelne).

### 5.3 Warstwy (pigułki – jedna główna warstwa naraz)
Pigułka: ikona + krótka nazwa; aktywna = tło `ok-soft`, obramowanie `brand`. Każda warstwa ma **legendę** jako mała ciemna karta (styl z ref-mobile.png: ciemne tło `#1E2A23` 90%, biały tekst, pasek gradientu, opisy krańców). Legenda w prawym dolnym rogu mapy (nad atrybucją).

| Pigułka | Ikona | Co pokazuje w obrysie | Kolory / legenda |
|---|---|---|---|
| **Kondycja upraw** | liść | NDVI z najbliższego bezchmurnego zdjęcia przed datą analizy, piksele 10 m | czerwony → żółty → zielony; „Słaba roślinność … Bujna”; białe = chmury/brak |
| **Wilgotność roślin** | kropla | NDMI, piksele 10 m | brąz → beż → niebieski; „Sucho … Wilgotno” |
| **Teren** | góra | strefy: sucha górka / stok / płasko / mokry dołek + cieniowanie rzeźby; spadki | brąz (górka), jasny beż (stok), szarozielony (płasko), niebieski (dołek); w legendzie różnica wysokości „od 134,7 do 148,0 m n.p.m.” |
| **Spływ wody** | fale | strzałki kierunku spływu, miejsca zbierania się wody (niebieskie plamy), miejsce odpływu z działki (czerwona strzałka z podpisem „tu woda ucieka”), rowy/cieki/zbiorniki w okolicy (niebieskie linie i powierzchnie z BDOT10k), zgłoszenia rolników (pinezki) | niebieski = woda; legenda z symbolami |
| **Gleba** | warstwy | kategorie podatności na suszę IUNG (I–IV, organiczne, nie-rolne) | I żółty, II pomarańcz, III ciemny pomarańcz, IV brąz-czerwony, organiczne szary; podpisy „Bardzo podatna … Mało podatna” |

Opcjonalne nakładki (przełączniki w małym menu „Dodatkowo”): granice sąsiednich działek, rowy i zbiorniki (gdy główna warstwa ≠ Spływ wody), zgłoszenia rolników.

### 5.4 Interakcje
- Klik poza wybraną działką → wyszukanie działki w tym punkcie → mapa `flyTo` do niej, panel się aktualizuje.
- Klik **wewnątrz** działki przy aktywnej warstwie → dymek z wartością w punkcie, np. Kondycja: „Kondycja: słaba (0,31) · zdjęcie 12.06.2026”; Teren: „Wysokość 141,6 m · spadek 6% · woda spływa na SW”; Gleba: „Kat. II – podatna na suszę · ok. 149 mm wody”.
- Najechanie (komputer) na rów/zbiornik → podświetlenie i dymek „Rów melioracyjny · 40 m od działki”; klik → karta obiektu z przyciskiem „Zgłoś stan” (sekcja 11).
- Przy wielu wynikach wyszukiwania: numerowane znaczniki na mapie zgodne z listą w panelu.
- Zmiana daty analizy → ponowne przeliczenie; warstwy satelitarne pokazują zdjęcie najbliższe dacie (z podpisem daty zdjęcia).

---

## 6. Panel działki (prawa karta / dolna szuflada na telefonie)

Kolejność od góry (wzorzec ref-desktop.png – karta „Field A1”, ale po polsku i z naszymi danymi):

1. **Nagłówek:** ikona liścia, „Działka 112/11”, po prawej „5,01 ha”. Pod spodem: „gm. Kampinos, obręb Szczytno · pow. warszawski zachodni”. Ikony: ☆ zapisz działkę, ⋯ (kopiuj identyfikator, otwórz w Geoportalu).
2. **Uprawa:** pole wyboru (15 upraw z IUNG) – „Uprawa: Zboża ozime ▾”. Bez wybranej uprawy analiza nie startuje (komunikat: „Wybierz, co rośnie na tej działce”).
3. **Karta stanu** (duża, tło w kolorze statusu „-soft”): ikona, „Uwaga – rośnie ryzyko suszy”, jedno zdanie: „Gleba zmieści mało wody, a od marca spadło o 84 mm mniej niż zwykle.” Strzałka › przewija do Paszportu wodnego.
4. **Kluczowe wskaźniki** (siatka 2×2 kart):
   - **Woda w glebie** – 38% + pasek (niebieski) · etykieta „szacunek modelu”.
   - **Ryzyko na 7 dni** – odznaka „Średnie” · „stres za ok. 6 dni” · etykieta „prognoza”.
   - **Kondycja upraw** – okrąg 0–100 lub opis „Dobra” · etykieta „z satelity · 12.06.2026”.
   - **Bilans wody (sezon)** – „−84 mm” · strzałka ↓ czerwona · etykieta „obliczenia z danych pogodowych”.
   Każda karta: ikona, nazwa, duża liczba, mała etykieta pochodzenia (sekcja 15.2).
5. **„Co zrobić?”** – maks. 3 rekomendacje (sekcja 7, D) jako karty z ikoną kategorii (💧 zatrzymanie wody / 🌱 uprawa / 🚿 nawadnianie), tytułem i jednym zdaniem. Klik „Dlaczego?” rozwija: przesłanki z danymi, źródła, daty, pewność.
6. **Przycisk główny** (pełna szerokość, `brand-dark`): „📄 Pobierz raport”. Pod nim link „Zobacz pełny paszport wodny”.
7. Drobna stopka: „Dane: GUGiK, IUNG, NASA POWER, Sentinel-2 · stan na 21.11.2026”.

Panel bez wybranej działki: ilustracja pola + „Znajdź swoją działkę” + 3 sposoby (wpisz numer / kliknij na mapie / Moja lokalizacja).

---

## 7. Paszport wodny (główny wynik analizy)

Otwiera się jako szeroki panel (komputer: wysuwa się zamiast prawego panelu do szer. 640 px z zakładkami A–E lub przewijana strona; telefon: pełny ekran). Nagłówek: „Paszport wodny · Działka 112/11 · Zboża ozime · stan na 15.06.2026” + przyciski „Pobierz PDF”, „Drukuj”, „Udostępnij link”.

### A. Stan obecny
- Duży wskaźnik w okręgu (styl ref-style.png): ogólny stan wodny 0–100 z opisem („Uwaga”).
- Karty: woda w glebie (% i mm), kondycja upraw, wilgotność roślin, ryzyko niedoboru na 7 dni, ile wody zmieści gleba.
- Zdanie podsumowania: „Na tej działce rośnie ryzyko suszy. Rośliny zaczną odczuwać brak wody za ok. 6 dni, jeśli nie spadnie deszcz.”

### B. Na tle 10 lat
- Wykres bilansu wody narastająco od początku sezonu: linia tego roku na tle pasma min–max i średniej z 10 lat.
- Słupki: liczba dni stresu wodnego w każdym roku (2016–2026), bieżący rok wyróżniony.
- Opady miesięczne: ten rok vs średnia.
- Zdanie: „W 6 z 10 ostatnich lat w maju–lipcu brakowało wody. Najgorszy był 2018 (41 dni stresu).”
- (P3) Kontekst: „W roku suszy 2018 plony pszenicy w województwie były o ok. 28% niższe” (GUS).

### C. Dlaczego?
Lista czynników z paskami udziału (od największego), każdy z liczbą:
- Mało opadów – „od marca 212 mm, zwykle 296 mm”.
- Gleba – „kat. II, zmieści ok. 149 mm wody – mało”.
- Teren – „spadek do 6%, woda szybko spływa na SW”.
- Wymagania uprawy – „zboża ozime w fazie kłoszenia potrzebują najwięcej wody”.

### D. Co mogę zrobić?
Zawsze w trzech grupach, w tej kolejności:
1. **Zatrzymaj wodę** (retencja) – np. „Oczko wodne w zagłębieniu przy południowej granicy (ok. 600 m²) – zbiera się tam woda z 1,2 ha.” · „Zastawka na rowie 35 m od miejsca, gdzie woda ucieka z działki.” · „Pas trwałej zieleni w poprzek stoku w części NE.”
2. **Zmiany w uprawie** – np. „Międzyplon po żniwach i pozostawienie resztek pożniwnych – więcej próchnicy, gleba zmieści więcej wody.” · „Uprawa uproszczona zamiast orki.”
3. **Nawadnianie** (opcjonalne) – np. „Nawadnianie ma sens w ciągu 5–7 dni: dawka ok. 20 mm. Najbliższe źródło wody: staw 300 m.”
Każda rekomendacja: tytuł, jedno zdanie, rozwijane „Dlaczego?” (przesłanki z liczbami, źródło, data, pewność). Na mapie przycisk „Pokaż na mapie” podświetla miejsce.

### E. Wiarygodność danych
- Odznaka pewności: **Wysoka** / **Średnia** / **Ograniczone dane** + jedno zdanie dlaczego („Model i zdjęcie satelitarne zgadzają się”).
- Tabela źródeł: źródło, co z niego wzięto, data danych, rozdzielczość, status (✓ / ⚠ częściowo / ✕ brak).
- Kompletność: pasek „5 z 6 źródeł”.
- Znane ograniczenia (generowane z danych): „Pogoda uśredniona dla obszaru ok. 50 km”, „Ostatnie bezchmurne zdjęcie: 12 dni przed datą analizy”, „Klasy bonitacyjne niedostępne w tym powiecie”.
- Nigdy nie sugeruj pewności, której dane nie dają.

---

## 8. Widok 2D / 3D

- **2D jest domyślny** i pełni wszystkie funkcje.
- **3D (P3)** – przełącznik „3D” w pasku warstw. Pokazuje teren działki i otoczenia z NMT (siatka wysokości przeskalowana pionowo ×3–5 dla czytelności), obrys działki, zagłębienia i spadki, rowy/zbiorniki, z nałożoną aktywną warstwą (kondycja/gleba/strefy terenu) jako teksturą. Bez modeli roślin, maszyn i budynków. Obracanie, przybliżanie, przycisk „Widok z góry”.
- Przełączanie zachowuje wybraną działkę, położenie i aktywną warstwę.
- Technologia: react-three-fiber/three.js (MIT) z siatką z NMT albo MapLibre GL z teren-DEM – wybrać to, co szybciej działa z naszymi danymi.

---

## 9. Oś czasu (historia)

- Pasek u dołu mapy (rozwijany z karty „Oś czasu”): miesiące z ostatnich 10 lat jako segmenty w kolorach stanu (bilans wody), zaznaczony wybrany dzień, przyciski ◀ ▶ (miesiąc), szybki wybór roku.
- Zmiana daty aktualizuje mapę (najbliższe zdjęcie satelitarne), panel i paszport.
- Tryb porównania (P3): „Porównaj z…” – podział mapy na dwie połowy (suwak) dla dwóch dat.
- Brak danych dla daty: segment kreskowany szary + komunikat „Brak bezchmurnego zdjęcia satelitarnego w tym okresie – pokazujemy najbliższe z 28.05.2026”.

---

## 10. Raporty

### 10.1 Ekran „Raporty”
Lista kart (najnowsze na górze): miniatura mapy działki, „Działka 112/11 · Zboża ozime”, data analizy, odznaka stanu, przyciski: Otwórz · PDF · Drukuj · Kopiuj link. Pusty stan: „Nie masz jeszcze raportów – wykonaj analizę działki”.

### 10.2 Układ raportu PDF / wydruku (A4 pionowo, 2–3 strony)
1. Nagłówek: logo, „Paszport wodny działki”, data wygenerowania, kod QR do analizy online.
2. Dane działki: identyfikator, gmina/obręb/powiat/województwo, powierzchnia, uprawa, data analizy, mapa działki (ortofotomapa + obrys).
3. Stan obecny (sekcja A) – wskaźnik i karty.
4. Na tle 10 lat (B) – wykresy.
5. Dlaczego? (C).
6. Co mogę zrobić? (D) – z mapką miejsc rekomendacji.
7. Gleba i teren – kategoria gleby, mapa stref terenu.
8. Źródła danych i daty, wiarygodność, ograniczenia (E).
9. Stopka: „Raport ma charakter pomocniczy. Wyniki oparte na danych publicznych – patrz ograniczenia.”
Styl jak aplikacja, ale druk przyjazny (białe tło, kolory statusów, bez ciemnych kart).

---

## 11. Zgłoszenia stanu rowów i zbiorników (funkcja dodatkowa)

Mniej widoczna niż główna ścieżka: wejście przez klik w rów/zbiornik na mapie albo przycisk „Zgłoś stan wody w okolicy” na dole panelu działki.

Kroki (szuflada / modal, 4 kroki z paskiem postępu):
1. **Wybierz obiekt** na mapie (podświetlony; nazwa typu: „Rów melioracyjny”, „Rzeka/strumień”, „Staw/zbiornik”).
2. **Jaki problem?** – duże kafelki z ikonami: Drożny ✓, Zarośnięty, Zamulony, Zatkany przepust, Uszkodzona zastawka, Uszkodzona skarpa, Zanieczyszczony; poziom wody: Brak / Niski / Normalny / Wysoki.
3. **Zdjęcie** (opcjonalnie) i krótki opis.
4. **Podsumowanie** – adresat ustalony z typu obiektu („Ciek → Wody Polskie, Nadzór Wodny” / „Rów → właściciel gruntu lub spółka wodna”) + przycisk „Pobierz gotowe pismo”. Komunikat: „Nic nie wysyłamy automatycznie.”

Na mapie: pinezki w kolorze stanu (🟢 drożny, 🟡 uwaga, 🔴 problem), liczba potwierdzeń, data ostatniego zgłoszenia; przycisk „Potwierdzam” / „Już naprawione”.

---

## 12. Telefon i tablet

### Telefon (< 768 px) – wzorzec ref-mobile.png
- Mapa na pełnym ekranie.
- U góry: pole wyszukiwania (pigułka) + przycisk lokalizacji; pod nim przewijane poziomo pigułki warstw.
- Kontrolki mapy po prawej (pionowo): +, −, lokalizacja, warstwy.
- Legenda aktywnej warstwy: mała ciemna karta nad szufladą.
- **Szuflada od dołu** (bottom sheet) z trzema położeniami: zwinięta (nazwa działki + status + przycisk „Raport”), połowa (wskaźniki + „Co zrobić?”), pełna (paszport wodny).
- Dolny pasek zakładek: Start, Działki, Raporty, Ustawienia.
- Przyciski min. 44×44 px, tekst min. 16 px.

### Tablet (768–1279 px)
- Lewy pasek zwinięty do ikon (64 px), prawy panel 340 px, dolny pasek kart przewijany poziomo (karty po 260 px).

---

## 13. Ścieżki użytkownika

**Główna (pierwsza wizyta):**
1. Start: pusty stan, mapa Polski, kursor w wyszukiwarce.
2. Wpisuje „Szczytno 112/11” → Enter → (wiele wyników: lista + numerowane znaczniki → wybór).
3. Mapa leci do działki, obrys, panel: dane działki + „Wybierz uprawę”.
4. Wybiera „Zboża ozime” (data domyślnie dziś) → ekran ładowania z krokami (≤ 30 s).
5. Panel: karta stanu, 4 wskaźniki, 3 rekomendacje; mapa: warstwa „Kondycja upraw”.
6. Przełącza „Spływ wody” → widzi, gdzie woda ucieka i rów obok.
7. Klik „Zobacz pełny paszport wodny” → sekcje A–E.
8. „Pobierz raport” → PDF. Działka zapisana w „Moje działki”.

**Na polu (telefon):** Moja lokalizacja → działka pod stopami → status w szufladzie → „Co zrobić?”.

**Historia:** zmiana daty na 15.07.2018 → mapa i paszport dla tamtego dnia, podpis „analiza historyczna”.

**Zgłoszenie rowu:** warstwa Spływ wody → klik w rów → „Zgłoś stan” → Zarośnięty + zdjęcie → pobierz pismo.

---

## 14. Komponenty wielokrotnego użytku (shadcn/ui + własne)

| Komponent | Opis |
|---|---|
| `SearchBar` | pigułka z lupą, podpowiedzi, stan ładowania, błąd pod spodem |
| `LayerPills` | grupa pigułek z ikonami, jedna aktywna, przewijana na telefonie |
| `MapControls` | pionowa grupa przycisków 44 px |
| `LegendCard` | ciemna karta z paskiem gradientu i opisami krańców (styl ref-mobile) |
| `ParcelLabel` | pigułka na mapie: numer działki + ikona stanu |
| `StatusBadge` | Dobrze / Uwaga / Ryzyko / Susza / Brak danych – kolor + ikona + tekst (nigdy sam kolor) |
| `MetricCard` | ikona, nazwa, duża liczba z jednostką, pasek/okrąg, `SourceTag` |
| `SourceTag` | mała etykieta pochodzenia: Pomiar / Z satelity (data) / Szacunek modelu / Prognoza / Brak danych |
| `ScoreRing` | okrąg 0–100 z liczbą w środku (styl ref-style) |
| `RecommendationCard` | ikona kategorii, tytuł, zdanie, rozwijane „Dlaczego?”, „Pokaż na mapie” |
| `TrendChart` | Recharts: linia roku na tle pasma 10 lat |
| `ConfidenceBadge` | Wysoka / Średnia / Ograniczone dane + tooltip z uzasadnieniem |
| `DetailsAccordion` | „Szczegóły” z terminami technicznymi i surowymi liczbami |
| `BottomSheet` | szuflada mobilna z 3 położeniami |
| `LoadingSteps` | lista kroków z ✓ / ⏳ / ✕ |
| `EmptyState` | ilustracja + tytuł + instrukcja + akcja |
| `ErrorNotice` | po polsku: co nie zadziałało, co działa dalej, „Spróbuj ponownie” |
| `WeatherWidget` | ikona, temperatura, opis; prognoza 7 dni z opadem w mm |
| `Timeline` | segmenty miesięcy z kolorami stanu, ◀ ▶, wybór roku |
| `ReportCard` | miniatura, dane, akcje |

---

## 15. Stany ekranu i rzetelność danych

### 15.1 Stany
- **Ładowanie analizy:** `LoadingSteps` w panelu: „Szukam działki ✓ · Pobieram pogodę z 10 lat ✓ · Sprawdzam glebę ✓ · Analizuję teren ⏳ · Zdjęcia satelitarne ⏳ · Liczę bilans wody…”. Szkielety (skeleton) kart wskaźników. Mapa już pokazuje działkę.
- **Pusty:** „Znajdź swoją działkę” + 3 sposoby.
- **Błąd źródła:** np. „Nie udało się pobrać zdjęć satelitarnych. Pozostała analiza jest kompletna – pewność wyniku: średnia.” + „Spróbuj ponownie”.
- **Brak danych:** szare kreskowanie na mapie, karta z „Brak danych dla tej daty” – nigdy zero ani wymyślona wartość.
- **To nie jest grunt rolny:** „Według mapy gleb IUNG ta działka to las / woda / zabudowa – ocena suszy rolniczej nie ma tu zastosowania.”
- **Brak sieci:** baner u góry „Brak połączenia – pokazujemy ostatnio zapisane dane”.

### 15.2 Etykiety pochodzenia (obowiązkowe przy każdej liczbie)
| Etykieta | Kiedy |
|---|---|
| **Pomiar** | wartości z ewidencji/rejestrów (powierzchnia, wysokość terenu) |
| **Z satelity · data** | NDVI, NDMI |
| **Obliczenia z danych** | bilans wody, parowanie |
| **Szacunek modelu** | woda w glebie, dni stresu |
| **Prognoza** | ryzyko na 7 dni, termin nawadniania |
| **Brak danych** | gdy źródło nie dało wyniku |

### 15.3 Czego nie pokazujemy
pH, składników pokarmowych, temperatury gleby i żadnych innych wartości, których nie mamy z danych. Sekcja „Gleba” pokazuje: kategorię podatności na suszę, ile wody zmieści gleba, klasę bonitacyjną (gdy dostępna).

---

## 16. Dostępność

- Kontrast tekstu min. 4,5:1 (WCAG AA); duże liczby min. 3:1.
- Status nigdy tylko kolorem – zawsze ikona + tekst.
- Pełna obsługa klawiaturą (Tab, Enter, Esc zamyka panele), widoczny focus (obrys `brand` 2 px).
- Etykiety ARIA dla przycisków ikonowych i mapy; legenda dostępna jako tekst.
- Palety warstw czytelne przy daltonizmie (zielony–czerwony uzupełniony jasnością i opisem).
- Responsywność od 360 px; skalowanie tekstu do 200% bez utraty treści.
- `prefers-reduced-motion` wyłącza animacje lotu mapy i wysuwania.

---

## 17. Kolejność wdrażania wyglądu

1. Tokeny (paleta, typografia, cienie) + układ Start (lewy pasek, górny pasek, mapa, prawy panel, dolny pasek kart) + wersja telefonu z szufladą.
2. Panel działki + `MetricCard`, `SourceTag`, `StatusBadge`, `RecommendationCard`, `LoadingSteps`, stany puste/błędu.
3. Warstwy mapy + legendy (Kondycja, Wilgotność, Teren, Spływ wody, Gleba).
4. Paszport wodny A–E + wykresy.
5. Raport PDF/wydruk + ekran Raporty + Moje działki.
6. Oś czasu.
7. Zgłoszenia rowów i zbiorników.
8. Widok 3D, tryb porównania dat, tryb doradcy.
