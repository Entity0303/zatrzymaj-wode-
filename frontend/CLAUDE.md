# Frontend – zasady (osoba B: Mefju)

Uzupełnia główny `CLAUDE.md` (wymagania KOWR, praca zespołowa, pamięć projektu w `.ai/`).
React + Vite + TypeScript + Tailwind v4 + shadcn/ui + react-leaflet + Recharts. Uruchamianie: `docker compose up` (port 5173, proxy `/api`).

## Wygląd

- Wyłącznie wg **`design/SPEC_UI.md`** i grafik w `design/` (`ref-desktop.png`, `ref-mobile.png`, `ref-style.png`). Niczego nie upraszczaj ani nie pomijaj; jeśli czegoś nie da się zrobić – napisz to wprost.
- Tokeny (paleta, cienie, zaokrąglenia, Inter) tylko z `theme/index.css` – bez „luźnych” kolorów hex w komponentach, poza wyjątkami już tam opisanymi.
- UI po polsku, słownik z SPEC 1 (np. „Kondycja upraw”, nie „NDVI” – terminy techniczne tylko w „Szczegółach”). Tekst min. 14 px (przypisy źródeł 12 px), przyciski min. 44×44 px.

## Struktura `src/`

| Katalog | Co tu jest |
|---|---|
| `api/` | `client.ts` (zapytania, błędy po polsku), `types.ts` (**KONTRAKT** – identyczny z `backend/app/schemas/`) |
| `mocks/` | `analysis.sample.json` + `useMockAnalysis.ts` |
| `theme/` | `index.css` (tokeny SPEC 2), `status.ts`, `recommendations.ts` |
| `layout/` | `Sidebar`, `BottomTabs`, `TopBar`, `BottomCards` (+ `cards/`), `BottomCardsStack`, `MobileSheet` |
| `components/` | komponenty wielokrotnego użytku z SPEC 14 – **1 komponent = 1 plik**; `components/ui/` = shadcn |
| `features/` | `search`, `map` (+ `map/layers/` – **1 warstwa = 1 plik**: CropHealth, PlantMoisture, Terrain, WaterFlow, Soil), `parcel-panel`, `passport` (**SectionA … SectionE** – 1 sekcja = 1 plik), `timeline`, `reports`, `infra-reports`, `weather` |
| `pages/` | `Start`, `MyParcels`, `Reports`, `Settings` |
| `lib/` | `utils` (cn), `dates`, `format`, `hooks`, `crops` |

`App.tsx` i `package.json` to pliki wspólne – zmieniane w osobnym małym commicie.

## Dane

- Typy **tylko z `api/types.ts`**. Nie definiuj własnych kształtów odpowiedzi API w komponentach. Zmiana typów = zmiana kontraktu → uzgodnienie z osobą A, obie strony naraz, wpis w `.ai/contract-changes.md`.
- Do czasu gotowego `/api/analysis` (dziś 501) pracuj na **`mocks/analysis.sample.json`**: `npm run dev` / `docker compose up` i adres `http://localhost:5173/?dane=przykladowe`. Mock działa tylko w trybie deweloperskim i tylko z tym parametrem, ekran pokazuje napis „DANE PRZYKŁADOWE”; z buildu produkcyjnego jest usuwany. Nowe pola w mocku muszą przejść `backend/tests/test_contract.py`.
- **Zakaz wymyślonych liczb.** Brak danych = „Brak danych” (szare kreskowanie, `SourceTag kind="brak_danych"`), nigdy 0 ani przykładowa wartość poza mockiem. Każda liczba ma etykietę pochodzenia (SPEC 15.2).

## Weryfikacja

- `npm run build` (TypeScript + Vite) musi przechodzić; `npx oxlint` bez nowych ostrzeżeń.
- Przeglądarki Claude Code używa tylko na wyraźną prośbę.
