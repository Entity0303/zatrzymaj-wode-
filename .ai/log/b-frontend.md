# Dziennik – osoba B (Mefju), frontend

Nowe wpisy na górze. Wpis: data i godzina · gałąź · co zrobiono · zmienione pliki · czy zmieniono kontrakt API.

---

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
