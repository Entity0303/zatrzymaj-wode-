# Wdrożenie – publiczny link do Wodoskopu

Frontend (React) idzie na **Vercel**, backend (FastAPI w Dockerze) na **Render**. Konfiguracja jest już w repo:
`render.yaml` (katalog główny) i `frontend/vercel.json`. Konta zakłada i klika właściciel repo – poniżej kolejność.

```
przeglądarka ──► Vercel (frontend, pliki statyczne)
      │
      └──► Render (backend /api/…) ──► źródła publiczne: GUGiK, IUNG, IMGW, NASA POWER, Open-Meteo, Earth Search…
```

Kolejność ma znaczenie: **najpierw Render** (potrzebny adres backendu), **potem Vercel**, **na końcu wracamy do Render**
i wpisujemy adres Vercela (CORS i kod QR w PDF).

---

## 1. Backend na Render

1. Wejdź na <https://dashboard.render.com> → zaloguj się przez GitHub (konto z dostępem do repo).
2. **New** → **Blueprint**.
3. Wybierz repozytorium `zatrzymaj-wode-` (gałąź `main`). Render znajdzie `render.yaml` i pokaże usługę `wodoskop-api`
   (Docker, region Frankfurt, plan Free).
4. Render poprosi o dwie wartości (`sync: false`):
   - `CORS_ORIGINS` – na razie wpisz `["http://localhost:5173"]` (poprawimy w kroku 3),
   - `PUBLIC_URL` – na razie zostaw puste.
5. **Apply**. Pierwsze budowanie obrazu trwa ok. 5–10 minut (WeasyPrint, rasterio, numpy).
6. Gdy status jest **Live**, skopiuj adres usługi, np. `https://wodoskop-api.onrender.com`.
7. Sprawdź: `https://wodoskop-api.onrender.com/api/health` → `{"status":"ok"}`.

Zmienne ustawione przez `render.yaml` (nie trzeba ich wpisywać):

| Zmienna | Wartość | Po co |
|---|---|---|
| `PORT` | `8000` | Dockerfile uruchamia serwer na 8000 – Render kieruje tam ruch |
| `DEMO_OFFLINE` | `false` | dane na żywo (nie tylko z cache) |
| `OFFLINE_SOURCES` | *(puste)* | w chmurze GUGiK nie jest zablokowany – wszystkie źródła włączone |
| `CACHE_DB` | `/data/cache.sqlite` | cache SQLite (na planie Free – do restartu, patrz niżej) |
| `DEMO_WARMUP` | `true` | po starcie w tle liczą się przykłady z ekranu startowego |

Health check to `/api/health` (lekki). **Nie** ustawiaj `/api/status` jako health check – ten adres przy każdym wywołaniu
wysyła zapytania testowe do wszystkich źródeł (GUGiK, NASA, IMGW…), a Render sprawdza zdrowie co kilka sekund.

## 2. Frontend na Vercel

1. Wejdź na <https://vercel.com> → zaloguj się przez GitHub.
2. **Add New…** → **Project** → **Import** przy repozytorium `zatrzymaj-wode-`.
3. **Root Directory** → **Edit** → wybierz `frontend`. Framework: Vite (wykryje się sam; ustawienia są w `frontend/vercel.json`).
4. **Environment Variables** → dodaj:
   - Name: `VITE_API_URL`
   - Value: adres z Render **bez** ukośnika na końcu, np. `https://wodoskop-api.onrender.com`
5. **Deploy**. Po ok. 1–2 minutach dostaniesz adres, np. `https://wodoskop.vercel.app` (nazwę można zmienić w
   Settings → Domains).

`VITE_API_URL` jest wpisywany do plików w chwili budowania – po jego zmianie trzeba zrobić **Redeploy**
(Deployments → ⋯ → Redeploy).

## 3. Powrót do Render: CORS i kod QR

1. Render → `wodoskop-api` → **Environment**.
2. `CORS_ORIGINS` = `["https://wodoskop.vercel.app"]` – dokładnie adres z Vercela, `https://`, bez ukośnika na końcu,
   w nawiasach i cudzysłowach (to lista JSON). Kilka adresów: `["https://wodoskop.vercel.app","http://localhost:5173"]`.
3. `PUBLIC_URL` = `https://wodoskop.vercel.app` (kod QR w raporcie PDF prowadzi do aplikacji).
4. **Save Changes** – Render sam przebuduje i uruchomi usługę ponownie (ok. 1–3 min).

## 4. Test po wdrożeniu (3 linki)

1. `https://wodoskop-api.onrender.com/api/demo/examples` – lista 6 przykładów (JSON). Działa = backend żyje.
2. `https://wodoskop.vercel.app/` – ekran startowy z kartami „Zobacz przykład” (karty przychodzą z backendu – jeśli są,
   frontend rozmawia z backendem i CORS jest dobrze ustawiony).
3. `https://wodoskop.vercel.app/?dzialka=201305_2.0038.6/1` – działka 6/1 Wnory-Wandy: werdykt, „Co tu posiać?”, potem
   „Pobierz raport PDF” → plik się pobiera.

## 5. Przed oceną: obudzenie backendu

Plan Free usypia usługę po ok. **15 minutach bez ruchu**. Pierwsze zapytanie po uśpieniu czeka na start kontenera
(zwykle **1–2 minuty**), a cache jest pusty (patrz niżej).

Ok. **10 minut przed oceną**:
1. Otwórz `https://wodoskop-api.onrender.com/api/status` – obudzi usługę i sprawdzi źródła (pierwsze otwarcie może
   trwać 1–2 min; odśwież, aż pokaże listę źródeł).
2. Otwórz `https://wodoskop.vercel.app/` i kliknij 2–3 przykłady – policzą się i trafią do cache.
3. Nie zostawiaj usługi bez ruchu na dłużej niż 15 minut przed pokazem (np. odśwież `/api/health` co kilka minut).

Opcjonalnie: darmowy zewnętrzny „pinger” (np. cron-job.org) otwierający `/api/health` co 10 minut trzyma usługę
w pogotowiu. Jedna usługa działająca całą dobę mieści się w darmowym limicie godzin Render.

## 6. Konsekwencje planu Free

- **Brak trwałego dysku.** Cache SQLite (`/data/cache.sqlite`) znika przy każdym restarcie, wdrożeniu i uśpieniu.
  Po wybudzeniu pierwsze analizy pobierają wszystko od nowa (pogoda 10 lat, gleba, teren, zdjęcie satelitarne) –
  zwykle 10–30 s na działkę; przykłady demo rozgrzewają się same w tle po starcie (`DEMO_WARMUP=true`).
  Rozwiązania: (a) plan **Starter** + dysk 1 GB – odkomentuj sekcję `disk` w `render.yaml`;
  (b) gotowy cache w obrazie (seed) – opis w punkcie 8.
- **512 MB pamięci.** Liczenie zdjęcia satelitarnego (rasterio) i PDF (WeasyPrint) naraz może przekroczyć limit –
  w logach Render będzie „Out of memory” i restart. Wtedy: w Environment dodaj `SENTINEL_ENABLED=false`
  (bez nowych zdjęć satelitarnych, reszta działa) albo przejdź na plan Starter.
- **Wolniejszy procesor** – analiza może trwać dłużej niż lokalnie.

## 7. Gdy coś nie działa

| Objaw | Co sprawdzić |
|---|---|
| Na stronie „Brak połączenia z serwerem aplikacji” | backend śpi (poczekaj 1–2 min i odśwież) albo zły `VITE_API_URL` (Vercel → Settings → Environment Variables → popraw → Redeploy) |
| W konsoli przeglądarki (F12) błąd „CORS” / „blocked by CORS policy” | `CORS_ORIGINS` na Render: dokładny adres Vercela, `https://`, bez `/` na końcu, format `["…"]` |
| Karty „Zobacz przykład” piszą „chwilowo niedostępne” | to samo co wyżej (CORS / backend śpi) |
| Odświeżenie podstrony na Vercelu daje 404 | Root Directory = `frontend` (wtedy działa `vercel.json` z przekierowaniem na `index.html`) |
| Render: „Health check failed” / usługa nie startuje | `PORT=8000` w Environment; logi: Render → wodoskop-api → **Logs** |
| Render: build się nie udaje | Logs → szukaj błędu `pip install`; Dockerfile jest w `backend/` (`dockerContext: ./backend`) |
| Analiza bardzo wolna / błędy GUGiK | `/api/status` pokaże, które źródło nie odpowiada; awaryjnie `OFFLINE_SOURCES=uldk,nmt` (tylko cache dla tych źródeł) |
| Raport PDF się nie pobiera | Logs na Render (WeasyPrint); sprawdź też CORS (PDF idzie tym samym adresem) |

Wariant awaryjny bez CORS: zamiast `VITE_API_URL` można dodać w `frontend/vercel.json` przekierowanie
`{"source": "/api/(.*)", "destination": "https://wodoskop-api.onrender.com/api/$1"}` (przed regułą na `index.html`)
– przeglądarka widzi jeden adres. Minus: Vercel przerywa takie zapytania po kilkudziesięciu sekundach, a pierwsza
analiza po wybudzeniu backendu może trwać dłużej.

## 8. Do zrobienia w backendzie (druga sesja) – opcjonalnie

- **CORS** – jest konfigurowalny (`cors_origins` w `backend/app/core/config.py`, zmienna `CORS_ORIGINS` jako lista JSON).
  Podglądy Vercela mają zmienne adresy (`wodoskop-git-…-konto.vercel.app`); jeśli mają działać, dodać
  `cors_origin_regex: str = ""` w `Settings` i `allow_origin_regex=settings.cors_origin_regex or None`
  w `CORSMiddleware` (`backend/app/main.py`), na Render: `CORS_ORIGIN_REGEX=https://wodoskop(-[a-z0-9-]+)?\.vercel\.app`.
- **Gotowy cache w obrazie (seed)** – w repo są już: działki demo (`backend/app/data/demo_parcels.json`), zapisany teren
  NMT (`backend/app/data/terrain/*.geojson|facts.json`), magazyn opadów IMGW (`backend/app/data/imgw/opady.npz`),
  plony GUS (`backend/app/data/crops/*.csv`). **Tylko w wolumenie** (`cache-data:/data/cache.sqlite`, ok. 15 MB) jest
  reszta: NASA POWER (ok. 12 MB), ortofotomapa, NMT, Sentinel-2, mapa glebowo-rolnicza, IUNG, SoilGrids, ULDK, PRNG.
  Propozycja:
  1. skrypt `backend/scripts/export_seed.py`: z `/data/cache.sqlite` kopiuje wiersze tabeli `cache` z przestrzeni
     o długim / nieskończonym TTL (bez prognozy Open-Meteo i bez wyników „na dziś”) do
     `backend/app/data/seed/cache_seed.sqlite.gz` (gzip, szac. 4–6 MB; `*.sqlite` jest w `.gitignore`, `.gz` nie);
  2. przy starcie (`lifespan` w `main.py`, przed `store()`): jeśli plik `CACHE_DB` nie istnieje albo tabela `cache`
     jest pusta – rozpakować seed i wczytać `INSERT OR IGNORE` (świeży wpis z wolumenu zawsze wygrywa);
  3. `stored_at` zostaje z seeda (TTL działa jak dotąd); w `/api/status` widać liczbę wpisów po starcie.
  Efekt: po każdym wybudzeniu na planie Free przykłady i działki testowe liczą się od razu, bez zapytań do GUGiK.
