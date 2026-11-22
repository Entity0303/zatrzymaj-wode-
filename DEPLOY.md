# Wdrożenie – publiczny link do Wodoskopu

Frontend (React) działa na **Vercel**, backend (FastAPI w Dockerze) na **Render**. Konfiguracja jest w repo:
[`render.yaml`](render.yaml) i [`frontend/vercel.json`](frontend/vercel.json). Konta zakłada i klika właściciel repo.

```
przeglądarka ──► Vercel (frontend, pliki statyczne)
      │
      └──► Render (backend /api/…) ──► źródła publiczne: GUGiK, IUNG, IMGW, NASA POWER, Open-Meteo, Earth Search…
                 │
                 └── trwały dysk /data (cache SQLite)
```

Kolejność: **najpierw Render** (potrzebny adres backendu), **potem Vercel**, **na końcu wracamy do Render** i wpisujemy
adres Vercela (CORS, kod QR i adres w stopce PDF).

---

## 1. Backend na Render

1. <https://dashboard.render.com> → zaloguj się przez GitHub (konto z dostępem do repo).
2. **New** → **Blueprint** → repozytorium `zatrzymaj-wode-`, gałąź `main`. Render znajdzie `render.yaml` i pokaże
   usługę `wodoskop-api`: Docker, region Frankfurt, **plan Starter (płatny)** z **trwałym dyskiem 1 GB** pod `/data`.
3. Render poprosi o dwie wartości (`sync: false`):
   - `CORS_ORIGINS` – na razie `http://localhost:5173` (poprawimy w kroku 3),
   - `PUBLIC_URL` – na razie puste.
4. **Apply**. Pierwsze budowanie obrazu trwa ok. 5–10 minut.
5. Gdy status jest **Live**, skopiuj adres usługi, np. `https://wodoskop-api.onrender.com`.
6. Sprawdź: `https://wodoskop-api.onrender.com/api/health` → `{"status":"ok"}`.

### Co ustawia `render.yaml`

| Ustawienie | Wartość | Po co |
|---|---|---|
| `plan` | `starter` | bez usypiania; trwały dysk wymaga planu płatnego |
| `disk` | `cache`, `/data`, 1 GB | cache SQLite przeżywa restarty i wdrożenia |
| `healthCheckPath` | `/api/health` | lekki (bez zapytań do źródeł). **Nie** ustawiaj `/api/status` – ten adres odpytuje wszystkie źródła, a Render sprawdza zdrowie co kilka sekund |
| `autoDeploy` | `true` | każde wypchnięcie na `main` wdraża backend – **na czas oceny wyłącz** (patrz punkt 5) |
| `buildFilter` | `paths: backend/**, render.yaml`; `ignoredPaths: backend/tests/**, **/*.md` | budowanie tylko przy zmianach backendu (zmiany frontendu, testów i dokumentacji nie przebudowują obrazu) |

### Zmienne środowiskowe

| Zmienna | Wartość | Po co |
|---|---|---|
| `PORT` | `8000` | Dockerfile uruchamia serwer na 8000 (jeden proces uvicorn) |
| `DEMO_OFFLINE` | `false` | dane na żywo |
| `OFFLINE_SOURCES` | `bdot` | wszystkie źródła na żywo poza nieużywanym BDOT10k; awaryjnie np. `uldk,nmt,bdot` (te źródła tylko z cache) |
| `CACHE_DB` | `/data/cache.sqlite` | plik cache na trwałym dysku |
| `CACHE_SEED` | domyślnie `true` (nie trzeba ustawiać) | gdy `/data/cache.sqlite` jest pusty (pierwszy start), wczytuje dane działek przykładowych z obrazu (`backend/app/data/seed/cache_seed.sqlite.gz`) |
| `DEMO_WARMUP` | `true` | w tle liczą się przykłady z ekranu startowego (po kolei; przykłady z danymi na dziś w cache są pomijane) |
| `DEMO_WARMUP_DELAY_S` | domyślnie `120` (nie trzeba ustawiać) | rozgrzewka startuje 2 minuty po uruchomieniu, żeby nie spowalniać pierwszych zapytań po wdrożeniu |
| `CORS_ORIGINS` | wpisywane ręcznie | adresy frontendu – **lista JSON** `["https://wodoskop.vercel.app"]` albo **tekst z przecinkami** `https://wodoskop.vercel.app,http://localhost:5173`; bez ukośnika na końcu |
| `CORS_ORIGIN_REGEX` | `^https://.*\.vercel\.app$` | podglądy Vercela o zmiennych adresach; pusty napis = wyłączone; błędne wyrażenie jest pomijane z ostrzeżeniem w logu |
| `PUBLIC_URL` | wpisywane ręcznie | publiczny adres aplikacji – kod QR i stopka w raporcie PDF |
| `FRONTEND_URL` | opcjonalnie | ma pierwszeństwo przed `PUBLIC_URL` w raporcie PDF; gdy obie puste – `https://wodoskop.vercel.app` |
| `SENTINEL_ENABLED` | opcjonalnie `false` | awaryjnie: bez nowych zdjęć satelitarnych (tylko cache), gdy brakuje pamięci |

## 2. Frontend na Vercel

1. <https://vercel.com> → zaloguj się przez GitHub → **Add New…** → **Project** → **Import** repozytorium.
2. **Root Directory** → `frontend`. Framework: Vite (ustawienia w `frontend/vercel.json`).
3. **Environment Variables**: `VITE_API_URL` = adres z Render **bez** ukośnika na końcu, np.
   `https://wodoskop-api.onrender.com`.
4. **Deploy**. Po 1–2 minutach dostaniesz adres, np. `https://wodoskop.vercel.app` (nazwa: Settings → Domains).

`VITE_API_URL` jest wpisywany do plików w chwili budowania – po jego zmianie zrób **Redeploy**.

**Ignored Build Step** (żeby zmiany backendu nie budowały frontendu) – Settings → Git → Ignored Build Step → Custom:

```bash
git diff --quiet $VERCEL_GIT_PREVIOUS_SHA $VERCEL_GIT_COMMIT_SHA -- .
```

Polecenie działa w katalogu `frontend/` (Root Directory). Kod wyjścia 0 (brak zmian w `frontend/`) = pomiń budowanie,
1 = buduj. To ustawienie jest w panelu Vercela, nie w repo.

## 3. Powrót do Render: CORS i adres w PDF

1. Render → `wodoskop-api` → **Environment**.
2. `CORS_ORIGINS` = `https://wodoskop.vercel.app` (albo lista JSON; dokładny adres, `https://`, bez `/` na końcu).
3. `PUBLIC_URL` = `https://wodoskop.vercel.app`.
4. **Save Changes** – Render uruchomi usługę ponownie.

## 4. Test po wdrożeniu

1. `https://wodoskop-api.onrender.com/api/demo/examples` – lista 6 przykładów (JSON). Działa = backend żyje.
2. `https://wodoskop.vercel.app/` – ekran startowy z przykładami (przychodzą z backendu – jeśli są, CORS jest dobrze
   ustawiony).
3. `https://wodoskop.vercel.app/?dzialka=201305_2.0038.6/1` – werdykt, „Co tu posiać?”, potem „Pobierz raport PDF”.
4. `https://wodoskop.vercel.app/?dzialka=201305_2.0038.6/1&data=2018-06-30` – data historyczna.

## 5. Na czas oceny

- **Wyłącz automatyczne wdrożenia backendu:** Render → `wodoskop-api` → Settings → Auto-Deploy → **Off** (albo
  `autoDeploy: false` w `render.yaml`). Wdrożenie restartuje usługę i czyści pamięć wyników – pierwsze zapytania po
  nim są wolniejsze.
- Po ostatnim wdrożeniu otwórz aplikację i kliknij 2–3 przykłady oraz działki z README – trafią do cache.
- `/api/status` pokazuje, które źródła odpowiadają (wysyła zapytania testowe – nie odświeżaj go w pętli).

## 6. Uwagi o planach

- **Plan Starter** (obecny): usługa nie usypia, cache jest na trwałym dysku. Pamięć 512 MB – liczenie zdjęcia
  satelitarnego i PDF naraz może ją przekroczyć (w logach „Out of memory” i restart); wtedy `SENTINEL_ENABLED=false`
  albo większa instancja.
- **Plan Free** (nie używamy): usypia po ok. 15 minutach bez ruchu (pierwsze zapytanie czeka 1–2 minuty) i nie ma
  trwałego dysku – cache znika przy każdym restarcie; aplikacja startuje wtedy z seeda (tylko działki przykładowe).
  Żeby go użyć, usuń z `render.yaml` sekcję `disk` i zmień `plan` na `free`.

## 7. Gdy coś nie działa

| Objaw | Co sprawdzić |
|---|---|
| Na stronie „Brak połączenia z serwerem aplikacji” | trwa wdrożenie backendu (poczekaj 1–2 min) albo zły `VITE_API_URL` (Vercel → Settings → Environment Variables → popraw → Redeploy) |
| W konsoli przeglądarki (F12) błąd „CORS” | `CORS_ORIGINS` na Render: dokładny adres Vercela, `https://`, bez `/` na końcu |
| Przykłady na starcie „chwilowo niedostępne” | to samo co wyżej (CORS / backend niedostępny) |
| Odświeżenie podstrony na Vercelu daje 404 | Root Directory = `frontend` (działa wtedy przekierowanie z `vercel.json`) |
| Render: „Health check failed” | `PORT=8000`; logi: Render → wodoskop-api → **Logs** |
| Render: build się nie udaje | Logs → błąd `pip install`; Dockerfile jest w `backend/` (`dockerContext: ./backend`) |
| Zmiana w kodzie backendu nie wdrożyła się | `buildFilter` – zmiana musi być w `backend/**` (poza `backend/tests/**` i plikami `.md`) albo w `render.yaml`; sprawdź też, czy Auto-Deploy jest włączony |
| Działka się nie wczytuje (502) | w logach linia `BŁĄD ŹRÓDŁA …` podaje źródło, typ błędu i stan bezpiecznika; `/api/status` pokaże, które źródło nie odpowiada; awaryjnie `OFFLINE_SOURCES=uldk,nmt,bdot` |
| Raport PDF się nie pobiera | Logs na Render (WeasyPrint, pamięć); sprawdź też CORS |

## 8. Seed cache

`backend/scripts/export_seed.py` kopiuje z `/data/cache.sqlite` wpisy poza prognozą i bieżącymi stanami wód do
`backend/app/data/seed/cache_seed.sqlite.gz`. Przy starcie (`load_seed()`), gdy tabela cache jest pusta, seed jest
wczytywany do `/data/cache.sqlite` (wpis z dysku zawsze wygrywa). Na Renderze z trwałym dyskiem seed wczyta się więc
tylko przy pierwszym uruchomieniu. Odświeżenie seeda: `docker compose exec backend python scripts/warm_demo.py
--no-pdf` → `docker compose exec backend python scripts/export_seed.py` → commit pliku `.gz`. Uwaga: eksport obejmuje
cały lokalny cache – przed eksportem warto zacząć od pustego wolumenu, żeby plik nie urósł. Zgłoszenia rolników do
seeda nie trafiają.
