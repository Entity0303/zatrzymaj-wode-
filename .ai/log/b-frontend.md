# Dziennik – osoba B (Mefju), frontend

Nowe wpisy na górze. Wpis: data i godzina · gałąź · co zrobiono · zmienione pliki · czy zmieniono kontrakt API.

---

## 2026-11-21 · `b/frontend` · B15: ekran powitalny – tylko mapa i logo, reszta po wyborze działki
**Co:** przed wyborem działki (komputer i telefon) widać tylko mapę pól z bliska (okolice działki z „Susza 2018”, zoom 14→15, powolny przelot 14 s – wyłączony przy `prefers-reduced-motion`) z miękką winietą i kartę powitalną (wjazd z dołu): logo, „Wodoskop”, hasło, wyszukiwarka (krótsza podpowiedź), „Moja lokalizacja”, „albo kliknij swoje pole na mapie”, pigułki „Zobacz przykład” (demo dla jury, 1 klik) i dyskretne linki Moje działki · Raporty · Ustawienia. Schowane do czasu wyboru działki: lewy pasek / dolne zakładki, górny pasek, pigułki warstw, kontrolki mapy, legenda, panel, karty. Po wyborze (wyszukanie, klik w mapę, lokalizacja, przykład) interfejs pojawia się łagodnie (`ui-appear`, sama przezroczystość). Bez poziomego przewijania (1440 / 390 px).
**Pliki:** `frontend/src/features/intro/IntroHero.tsx`, `frontend/src/features/map/ParcelMap.tsx` (`IntroView`), `frontend/src/features/search/SearchBar.tsx` (`placeholder`), `frontend/src/pages/Start.tsx`, `frontend/src/theme/index.css`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B14: poprawka – długa nazwa uprawy wychodziła poza pole
**Co:** w wąskim polu wyboru uprawy (tablet 298 px, zwinięta karta) długie nazwy („Kukurydza na kiszonkę”, „Rzepak i rzepik (jesień)”) wypychały strzałkę poza pole. Teraz: pole jako kontener – „Uprawa:” widoczne dopiero od 340 px szerokości pola (ikona zostaje), nazwa skracana „…” jeśli nadal za długa, pełna nazwa w dymku, strzałka zawsze widoczna. Sprawdzone pomiarem i zrzutami (1440, 1024, 390 px).
**Pliki:** `frontend/src/features/parcel-panel/CropField.tsx`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B13: zwinięty panel działki (komputer)
**Co:** przy wybranej działce prawy panel domyślnie jako mała karta (wysokość wg treści): nazwa działki, gmina/obręb/ha, wybór uprawy, w trakcie analizy pasek postępu, potem okrąg stanu + odznaka + nagłówek oceny, przyciski „Pełny panel” i „Paszport wodny”. Pełny panel ma „Zwiń panel”. Wybór zapamiętany (`zw.ui.v1.panel`). Pusty stan (przykłady), paszport, kreator zgłoszeń i telefon bez zmian.
**Pliki:** `frontend/src/features/parcel-panel/ParcelSummary.tsx`, `frontend/src/pages/Start.tsx`, `frontend/src/lib/{storage,i18n.en}.ts`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B12: mniej rzeczy naraz na ekranie komputera
**Co:** na wierzchu: mapa, wyszukiwarka, pigułki warstw, panel działki (nagłówek, uprawa, karta stanu, 4 wskaźniki, „Co zrobić?”, przyciski). Schowane z przyciskiem: dolny pasek 5 kart (pigułka „Pogoda, gospodarstwo, oś czasu” w lewym dolnym rogu; „Ukryj” nad paskiem), legenda (zwinięta do pigułki z nazwą warstwy i paskiem kolorów), w panelu „Pokaż szczegóły” (faza uprawy, woda w glebie, plan nawadniania, gleba, postęp analizy; w trybie doradcy zawsze rozwinięte). Usunięte z widoku: nieaktywny przełącznik 2D|3D (wróci z 3D), karta z hasłem w lewym pasku; język jako mały przycisk w pigułce pogody. Stan rozwinięcia zapamiętany w przeglądarce (`zw.ui.v1`). Telefon bez zmian. Sprawdzone zrzutami 1440 px.
**Pliki:** `frontend/src/pages/Start.tsx`, `frontend/src/features/parcel-panel/ParcelPanel.tsx`, `frontend/src/features/map/LegendCard.tsx`, `frontend/src/layout/{TopBar,Sidebar}.tsx`, `frontend/src/lib/{storage,i18n.en}.ts`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B11: wybrana działka w polu wyszukiwania
**Co:** po wybraniu działki (link, „Zobacz przykład”, klik na mapie, lista kandydatów) pole wyszukiwania pokazuje „obręb numer”, np. „Szczytno 112/11” – ten sam tekst wyszukuje tę działkę ponownie (sprawdzone: 200). Wpisywanie innej działki działa jak wcześniej.
**Pliki:** `frontend/src/features/search/SearchBar.tsx`, `frontend/src/pages/Start.tsx`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B10: „Zobacz przykład” – 4 analizy jednym klikiem
**Co:** pusty stan panelu (komputer, tablet, szuflada telefonu – na telefonie bez linku szuflada startuje do połowy): 4 karty – Susza 2018 (6/1 Wnory-Wandy, zboża ozime, 15.07.2018), Wilgotniejszy 2021 (ta sama działka, 15.07.2021 – bilans +40 mm vs średnia), Kukurydza dziś (ta sama działka, dziś), To nie jest pole (Szczytno 112/11 – las 51%). Klik = działka + uprawa + data → pełna analiza; adres w pasku od razu jest linkiem. Karty opisują scenariusz, wyniki liczy serwer. Wszystkie 4 sprawdzone na prawdziwym `/api/analysis` 21.11.2026. Lista w `features/parcel-panel/examples.ts` – do podmiany na `GET /api/demo/examples` z kontraktu. Tablet (1024×768) sprawdzony zrzutem – bez przewijania w poziomie.
**Uwaga dla A:** `/api/parcel` zwraca dziś 404 („nie znaleziono działki”, ULDK) dla 4 działek z `.ai/test-parcels.md`: `040703_5.0020.76`, `160703_5.0011.945`, `302114_5.0018.445`, `061704_2.0011.383/2` (powtarzalnie); `201305_2.0038.6/1` i `143203_2.0027.112/11` działają.
**Pliki:** `frontend/src/features/parcel-panel/{examples.ts,PanelEmpty.tsx,ParcelPanel.tsx}`, `frontend/src/pages/Start.tsx`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B9: zgłoszenia rowów i zbiorników (formularz + mapa)
**Co:** kreator 4 kroków z paskiem postępu (SPEC 11): 1. rodzaj obiektu (rów / rzeka lub strumień / staw lub zbiornik) + miejsce (domyślnie środek działki, „Wskaż miejsce na mapie” – tryb wskazywania z banerem i „Anuluj”, bursztynowy znacznik); 2. stan (7 kafelków z kolorem) i poziom wody; 3. zdjęcie (zostaje na urządzeniu – kontrakt nie ma pola na zdjęcie) i opis; 4. podsumowanie, adresat wg rodzaju obiektu, „Pobierz gotowe pismo” (tekst generowany w przeglądarce, pola osobowe do uzupełnienia ręcznie), „Pokaż zgłoszenie innym rolnikom na mapie” → POST `/api/infra-reports` (501 → „w budowie, pismo możesz pobrać już teraz”), „Nic nie wysyłamy automatycznie.”. Wejście: przycisk na dole panelu działki (mniej widoczny niż główna ścieżka). Komputer: zamiast panelu; telefon: pełna szuflada. Pinezki zgłoszeń wokół działki (GET `/api/infra-reports`, ~1,5 km) w kolorze stanu, dymek z potwierdzeniami i „Potwierdzam” (POST `/confirm`).
**Pliki:** `frontend/src/features/infra-reports/{InfraReportWizard,InfraPins}.tsx`, `frontend/src/features/infra-reports/{infra,letter}.ts`, `frontend/src/api/client.ts` (`post`, `infraReports`, `createInfraReport`, `confirmInfraReport`), `frontend/src/features/map/ParcelMap.tsx`, `frontend/src/features/parcel-panel/ParcelPanel.tsx`, `frontend/src/pages/Start.tsx`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie (`InfraReportIn`, `InfraReport` bez zmian).

## 2026-11-21 · `b/frontend` · B8: warstwy mapy podpięte do /api/layers
**Co:** `useLayerData` – GET `/api/layers/{layer}?parcel_id=&date=` dla wybranej działki (zmiana warstwy/działki/daty przerywa poprzednie); 404/501 = „warstwa w budowie” (nie błąd). `LayerData` – wspólne rysowanie: raster PNG w bbox (`ImageOverlay`) + GeoJSON z dymkiem `label`/`name`; każda warstwa w swoim pliku z własnym stylem (Teren: strefy, Spływ: rowy/odpływ/zgłoszenia, Gleba: kolory kodów IUNG jak w legendzie). Warstwa pod białym obrysem działki. Legenda pokazuje stan: wybierz działkę / wczytuję / w budowie / błąd / „Dane z {data}”. Klik w działce → GET `/api/layers/{layer}/point` (tekst z serwera; 501 → „brak danych w tym punkcie – warstwa w budowie”). Sprawdzone przechwyceniem odpowiedzi w przeglądarce testowej (dziś backend: 501).
**Propozycja dla A (format obiektów, `schemas/layers.py` ma TODO):** `features[].properties` = `{ kind?, color?, label? }`; `kind`: Teren `gorka|stok|plasko|dolek`, Spływ `arrow|spot|outflow|line|pin`, Gleba kod IUNG jako tekst (`'1'…'14'`). Bez tych pól frontend użyje kolorów domyślnych.
**Pliki:** `frontend/src/features/map/layers/{useLayerData.ts,LayerData.tsx,types.ts,CropHealth,PlantMoisture,Terrain,WaterFlow,Soil}.tsx`, `frontend/src/features/map/ParcelMap.tsx`, `frontend/src/api/client.ts`, `frontend/src/pages/Start.tsx`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie (używa istniejących `LayerResponse`, `PointValue`).

## 2026-11-21 · `b/frontend` · B7: dolne karty i oś czasu z danych analizy
**Co:** Gospodarstwo – liczba zapisanych działek + odznaki stanu z historii analiz, „Wymaga uwagi: N”, klik → Moje działki. Bilans wody – własny mini-wykres SVG: sezon (niebieska linia) na tle pasma 10 lat i średniej, „X mm względem średniej” + etykieta pochodzenia. Alerty – maks. 2 z wyniku: ryzyko na 7 dni (status uwaga/ryzyko/susza) i zalecone nawadnianie; bez zagrożeń ✓ „Brak alertów”; bez analizy „Brak danych”. Oś czasu – lata z `stress_days_by_year` w kolorze stanu (dni stresu względem średniej tych lat: ≤0,75× dobrze, ≤1,25× uwaga, ≤2× ryzyko, więcej susza), wybrany rok obwiedziony, klik w rok = ta sama data w tamtym roku, ◀ ▶ = miesiąc (zakres 10 lat). Wspólne propsy `layout/cards/types.ts` dla paska (komputer) i szuflady (telefon).
**Pliki:** `frontend/src/layout/cards/{types.ts,FarmCard,BalanceCard,AlertsCard}.tsx`, `frontend/src/features/timeline/TimelineCard.tsx`, `frontend/src/layout/{BottomCards,BottomCardsStack}.tsx`, `frontend/src/pages/Start.tsx`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B6: Moje działki, Raporty, Ustawienia (pamięć przeglądarki)
**Co:** nawigacja aktywna (lewy pasek i dolne zakładki): `#dzialki`, `#raporty`, `#ustawienia` (`lib/router.ts`); Start bez #, stan działki w adresie, więc powrót na mapę odtwarza analizę. `lib/storage.ts` – localStorage z try/catch i odświeżaniem między komponentami; historia analiz (`zw.analyses.v1`, maks. 50, tylko prawdziwe wyniki – nie mock). Moje działki: karty zapisanych działek z ostatnim stanem z historii, „Pokaż na mapie” (link z ostatnią uprawą i datą), usuwanie z potwierdzeniem w stronie. Raporty: karty z okręgiem stanu, „Otwórz paszport” (`?widok=paszport` – po analizie od razu paszport), PDF, „Kopiuj link”, usuwanie, „Wyczyść historię”. Ustawienia: podkład mapy (domyślny na Starcie), tryb rolnik/doradca (doradca: „Dlaczego?” i postęp analizy rozwinięte), język, usuwanie zapisanych danych. Paszport dla gruntu nierolnego: komunikat + gleba + wiarygodność (bez A–D). Sprawdzone na prawdziwym `/api/analysis` (działka 112/11 = las wg IUNG).
**Pliki:** `frontend/src/{App.tsx, lib/{router,storage,deepLink,hooks}.ts, layout/{PageShell,Sidebar,BottomTabs,sections}.ts*, pages/{MyParcels,Reports,Settings,Start}.tsx, features/reports/ReportCard.tsx, features/passport/Passport.tsx, components/RecommendationCard.tsx, features/parcel-panel/ParcelPanel.tsx, lib/i18n.en.ts}`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B5: paszport wodny A–E
**Co:** paszport podpięty: przycisk „Zobacz pełny paszport wodny” i strzałka › w karcie stanu; komputer – panel 640 px zamiast panelu działki (Esc / ← zamyka), telefon – pełna szuflada. Nagłówek przyklejony: działka, uprawa, data, „analiza historyczna”, „Pobierz PDF”, „Drukuj” (osobna wersja do wydruku przez portal, wykresy o stałej szerokości), „Kopiuj link”, skróty A–E. A: okrąg 0–100 w kolorze stanu + 5 kart (woda % i mm, ryzyko 7 dni, kondycja, wilgotność roślin, pojemność gleby). B: wykresy Recharts – bilans narastająco na tle pasma min–max i średniej 10 lat, dni stresu w latach (bieżący wyróżniony), opady miesięczne vs średnia; odznaki: odchylenie od średniej, ranking, najdłuższy okres bez deszczu. C: czynniki z ikoną, paskiem i źródłem. D: maks. 5 rekomendacji w 3 grupach + plan nawadniania, „Pokaż na mapie” (bursztynowe podświetlenie `location`, lot mapy). E: pewność + powód, pasek kompletności, tabela źródeł, ograniczenia. „Dlaczego?” wspólne dla panelu i paszportu (`RecommendationWhy`). Mock to zapis prawdziwej odpowiedzi dla innej działki (6/1) – w trybie przykładowym paszport pokazuje jej dane. Sprawdzone zrzutami (1440 px, 390 px).
**Pliki:** `frontend/src/features/passport/{Passport,PassportSection,SectionA..E}.tsx`, `frontend/src/features/passport/charts/{BalanceChart,StressChart,PrecipChart}.tsx`, `frontend/src/features/parcel-panel/{RecommendationWhy,WhatToDo,ParcelPanel,StatusCard}.tsx`, `frontend/src/features/map/ParcelMap.tsx`, `frontend/src/pages/Start.tsx`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · B4: wygląd „otwarte pole”, prosty język, poprawki telefonu
**Co:** paleta: szałwia, leśna zieleń, kremowe tło, bursztyn (akcenty), grafit zamiast czerni – przez tokeny `theme/index.css` (nazwy tokenów bez zmian, nowe: `sage`, `amber`, `font-display`). Nagłówki szeryfem Fraunces (osobny commit z `package.json`), dane i liczby dalej Inter. `WaveDivider` – falista linia między sekcjami panelu. Nowa ilustracja pola w słońcu (bez zdjęć – brak licencjonowanych). Prosty język: „Rodzaj gleby”, „1 mm wody = 1 litr na m²”, gleba „jak gąbka”, woda w glebie „jak bak”, klasy „w ewidencji”, odznaki faz („teraz najbardziej potrzebuje wody”, „zbliża się zbiór”…). Poprawki: legenda na telefonie tylko przy zwiniętej szufladzie (zasłaniała działkę), etykiety pochodzenia zawijają się zamiast „Szacunek model...”, lewy pasek 104 px, napis DANE PRZYKŁADOWE pod pigułkami. Sprawdzone zrzutami (telefon 390 px, komputer 1440 px).
**Pliki:** `frontend/src/theme/{index.css,status.ts}`, `frontend/src/components/{WaveDivider,FieldIllustration,LogoMark,SourceTag,DateField,MetricCard}.tsx`, `frontend/src/features/parcel-panel/*`, `frontend/src/features/map/{LayerPills,ParcelMap,layers/CropHealth}.tsx`, `frontend/src/layout/Sidebar.tsx`, `frontend/src/pages/Start.tsx`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend` · merge `origin/a/backend` (A4: pełne /api/analysis)
**Co:** scalone A4 (ocena, pewność, przyczyny, silnik reguł, pełne `/api/analysis`; mock = prawdziwa odpowiedź). Konflikt w `.ai/decisions.md` – A zajęła D35–D39, przełącznik języka przenumerowany na **D40** (wcześniej D30 → D35). Kontrakt: `Recommendation.priority`, `in_panel` – panel pokazuje rekomendacje z `in_panel` (po jednej z kategorii), w kolejności retencja → agrotechnika → nawadnianie, w kategorii wg `priority`. Weryfikacja: `npm run build`, `pytest` 150 passed.
**Pliki:** `.ai/decisions.md`, `frontend/src/features/parcel-panel/WhatToDo.tsx`, odwołania D40 (`i18n.ts`, `i18n.en.ts`, `LanguageProvider`, `LanguageToggle`, status B) + pliki A z merge.
**Kontrakt API:** TAK (zmiana A, przyjęta) → `.ai/contract-changes.md`.

## 2026-11-21 · `b/frontend` · B3: linki do analizy i raport PDF (uwagi mentora, część 1)
**Co:** stan w adresie `?dzialka=&uprawa=&data=` (`lib/deepLink.ts`): otwarcie linku od razu wyszukuje działkę (przy kilku wynikach – lista, uprawa przypisana po wyborze) i liczy analizę; adres w pasku aktualizowany na bieżąco (`replaceState`, inne parametry np. `?dane=przykladowe` zostają); zła uprawa / data spoza 10 lat w linku są ignorowane. Przycisk „Kopiuj link do tej analizy” w panelu (gdy brak schowka – podpowiedź, by skopiować adres z paska). „Pobierz raport PDF” → `GET /api/report.pdf?parcel_id=&crop=&date=` (te same parametry co analiza; aktywny po gotowej analizie, także „Raport” w szufladzie telefonu); błędy po polsku z tym, co działa dalej (404/501 → „Raport PDF jest jeszcze w budowie”). `przedplon` – czekam na nazwę pola w kontrakcie, nie zgadujemy.
**Pliki:** `frontend/src/lib/deepLink.ts`, `frontend/src/features/reports/useReportDownload.ts`, `frontend/src/api/client.ts` (`reportPdf`), `frontend/src/pages/Start.tsx`, `frontend/src/features/parcel-panel/{ParcelPanel,MobileSheetHeader}.tsx`, `frontend/src/lib/i18n.en.ts`.
**Kontrakt API:** nie (`/api/report.pdf` zwraca plik; endpoint po stronie A – dziś 404).

## 2026-11-21 · `b/frontend` · B2: nowe pola kontraktu w panelu
**Co:** panel działki pokazuje pola A3b i sekcję gleby: `CropSeasonCard` (faza, dzień sezonu, pasek start → zbiór, korzenie, wrażliwość), `SoilWaterCard` (zakres strefa korzeni / profil, opis, „tego dnia mniej wody było w N z 10 lat” z paskiem lat, podsumowanie zakończonego sezonu), `IrrigationCard` (status, dawka, pierwsza dawka, co ile dni, suma 7 dni – na końcu „Co zrobić?”), `SoilCard` (kategoria IUNG, WOD mm, udziały kategorii, klasy bonitacyjne / powód braku), `NonAgriculturalCard` („To nie jest grunt rolny” zamiast karty stanu; wtedy bez wskaźników i zaleceń). Kolory kodów IUNG w `theme/soil.ts` (wspólne z legendą). ~48 tekstów EN. Weryfikacja: `npm run build`, `oxlint`; w przeglądarce nie sprawdzane.
**Pliki:** `frontend/src/features/parcel-panel/{CropSeasonCard,SoilWaterCard,IrrigationCard,SoilCard,NonAgriculturalCard,ParcelPanel}.tsx`, `frontend/src/theme/soil.ts`, `frontend/src/features/map/layers/Soil.tsx`, `frontend/src/lib/{format,i18n.en}.ts`.
**Kontrakt API:** nie (tylko odczyt pól z `types.ts`).

## 2026-11-21 · `b/frontend` · merge `origin/a/backend` (A3b)
**Co:** scalone zmiany A: kontrakt A3b (`crop_season`, `soil_water`, `irrigation` w `AnalysisResponse` + mock), ciągły bilans, fazy upraw, nawadnianie. Konflikt tylko w `.ai/decisions.md` – oba D30; D30–D34 zostają po stronie A (D30 cytowane w kodzie backendu), przełącznik języka przenumerowany na **D35** (odwołania w `i18n.ts`, `i18n.en.ts`, `LanguageProvider`, `LanguageToggle`, status B). Weryfikacja: `npm run build` OK, `pytest` 125 passed. Nowe pola kontraktu jeszcze nie pokazywane w UI.
**Pliki:** `.ai/decisions.md`, `.ai/log/b-frontend.md`, `.ai/status/b-frontend.md`, `frontend/src/{lib/i18n.ts,lib/i18n.en.ts,components/LanguageProvider.tsx,components/LanguageToggle.tsx}` + pliki A z merge.
**Kontrakt API:** TAK (zmiana A, przyjęta bez zmian po stronie B) → `.ai/contract-changes.md`.

## 2026-11-21 · `b/wyglad-grafiki` · B1
**Co:** wygląd dopasowany do grafik wzorcowych. Dodane `design/ref-desktop.png`, `ref-mobile.png`; `ref-style.png` nie było – wykonana od zera wg SPEC 2/14 i obu grafik (źródło HTML `design/ref-style.src.html`, render headless Edge). Zmiany: elementy na mapie białe bez linii z cieniem float (wyszukiwarka, lokalizacja, pigułki, 2D|3D, kontrolki, panel); pogoda · data analizy · język w jednej pigułce z podziałami; dolny pasek 5 kart = jedna biała karta z liniami podziału (tablet: przewijana); MetricCard/RecommendationCard płaskie (linia, bez cienia), ikona w kółku, pasek 6 px, strzałka ↓/↑ przy bilansie; ScoreRing z torem -soft, w paszporcie 120 px w kolorze stanu + „na 100”; karta stanu bez linii, ikona 44 px, nagłówek 18/24, strzałka ›; legendy: r 12, pasek 6 px, osobna próbka „Chmury”, kropki klas; lewy pasek: podpisy 14 px, karta hasła (kropla, hasło, ilustracja); powierzchnia w nagłówku panelu spokojniejsza. Logika, kontrakt i backend bez zmian; bez nowych liczb. Weryfikacja: `npm run build` OK, `oxlint` bez nowych ostrzeżeń; w przeglądarce nie sprawdzane.
**Pliki:** `design/ref-{desktop,mobile,style}.png`, `design/ref-style.src.html`, `frontend/src/{components/{DashboardCard,DateField,LanguageToggle,MetricCard,RecommendationCard,ScoreRing}.tsx, features/map/{LayerPills,LegendCard,MapControls,ViewToggle}.tsx, features/map/layers/{CropHealth.tsx,types.ts}, features/parcel-panel/{KeyMetrics,ParcelHeader,StatusCard}.tsx, features/passport/SectionA.tsx, features/search/{LocateButton,SearchBar}.tsx, features/weather/WeatherWidget.tsx, layout/{BottomCards,Sidebar,TopBar}.tsx, lib/i18n.en.ts, pages/Start.tsx, theme/status.ts}`.
**Kontrakt API:** nie.

## 2026-11-21 · `b/frontend`
**Co:** przełącznik języka PL | EN (D30). `lib/i18n.ts` (`t()`, `useLang`, `locale()`), `lib/i18n.en.ts` (~300 tekstów: cały UI, uprawy, warstwy, błędy, opisy pogody, teksty mocka), `components/LanguageProvider.tsx`, `components/LanguageToggle.tsx` (górny pasek; na telefonie okrągły przycisk). Tłumaczenie w miejscach wyświetlania (karty, odznaki, błędy, kroki), więc etykiety w danych zostają po polsku. `ErrorInfo.vars` dla {zmiennych} w błędach. Liczby/daty wg języka. Fokus wyszukiwarki przez `data-parcel-search` zamiast polskiego aria-label. Gałąź: od teraz jedna długa `b/frontend` (nowe zasady od A), z `mathew`.
**Pliki:** `frontend/src/lib/{i18n,i18n.en}.ts`, `frontend/src/components/{LanguageProvider,LanguageToggle}.tsx`, `frontend/src/main.tsx` + ~50 plików komponentów/funkcji (tylko teksty → `t()`).
**Kontrakt API:** nie.

## 2026-11-21 · `b/wybor-uprawy-ladowanie`
**Co:** uruchamianie analizy po wyborze uprawy; zmiana uprawy lub daty analizy przelicza od nowa (poprzednie zapytanie przerywane). Ekran ładowania w panelu (SPEC 13 krok 4, 15.1): karta „Liczę ocenę wody dla działki…” z uprawą, datą, licznikiem sekund i paskiem postępu, `LoadingSteps` ✓/⏳/✕, szkielety wskaźników i rekomendacji. Na mocku (`?dane=przykladowe`) kroki z `analysis.sample.json` przechodzą kolejno w tempie `duration_ms` (maks. 2,5 s/krok), potem wynik. Bez mocka: `GET /api/analysis`; backend nie przesyła postępu, więc wszystkie kroki „w toku” do odpowiedzi (nie udajemy postępu); 501 → komunikat „Ocena sytuacji wodnej jest jeszcze w budowie”, 502/504 → „Spróbuj ponownie”.
**Pliki:** `frontend/src/features/parcel-panel/{useAnalysis.ts,AnalysisLoading.tsx,ParcelPanel.tsx,types.ts}`, `frontend/src/mocks/useMockAnalysis.ts`, `frontend/src/api/client.ts` (`describeAnalysisError`), `frontend/src/pages/Start.tsx`.
**Kontrakt API:** nie.

## 2026-11-21 15:20 · `main` · commit f31e94c
**Co:** podział na `api/ mocks/ theme/ layout/ components/ features/ pages/` (1 komponent / warstwa / sekcja = 1 plik), bez zmiany wyglądu; `api/types.ts` identyczny z Pydantic; mock `analysis.sample.json` (tylko dev + `?dane=przykladowe`, napis „DANE PRZYKŁADOWE”); panel działki czyta wynik analizy; szkielety paszportu A–E, raportów, zgłoszeń i stron.
**Pliki:** `frontend/src/**` (86), `frontend/tsconfig.app.json`, `frontend/components.json`.
**Kontrakt API:** TAK – `frontend/src/api/types.ts` (razem z backendem) → `.ai/contract-changes.md`.

## 2026-11-21 15:03 · `main` · commit 0bff78f
**Co:** wygląd wg SPEC_UI (kroki 1–2 sekcji 17): tokeny, ekran Start, panel działki, komponenty SPEC 14, tablet, telefon z szufladą; pogoda i prognoza 7 dni; wybór uprawy; zapis działek w przeglądarce.
**Pliki:** `frontend/src/**` (32), `frontend/package.json`, `design/SPEC_UI.md`.
**Kontrakt API:** nie.

## 2026-11-21 14:21 · `main` · commit 265b6a7
**Co:** wyszukiwanie działki i mapa: shadcn/ui, ortofotomapa Geoportalu (WMTS EPSG:3857) + OSM, klik w mapę, lista kandydatów, panel działki, wersja mobilna.
**Pliki:** `frontend/src/**` (13), `frontend/package.json`, `frontend/vite.config.ts`, `frontend/components.json`, `frontend/tsconfig*.json`.
**Kontrakt API:** nie.

## 2026-11-21 13:44 · `main` · commit 0dc3fe4
**Co:** szkielet frontendu React + Vite + Tailwind z mapą Leaflet.
**Pliki:** `frontend/**`.
**Kontrakt API:** nie.
