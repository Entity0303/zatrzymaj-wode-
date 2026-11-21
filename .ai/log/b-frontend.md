# Dziennik – osoba B (Mefju), frontend

Nowe wpisy na górze. Wpis: data i godzina · gałąź · co zrobiono · zmienione pliki · czy zmieniono kontrakt API.

---

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
