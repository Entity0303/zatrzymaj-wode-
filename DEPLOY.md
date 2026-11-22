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
| `CACHE_SEED` | *(domyślnie `true`, nie trzeba ustawiać)* | pusty cache po starcie / uśpieniu → wczytanie gotowych danych działek demo z obrazu (`backend/app/data/seed/cache_seed.sqlite.gz`) |
| `CORS_ORIGIN_REGEX` | *(opcjonalnie, ręcznie)* | podglądy Vercela o zmiennych adresach, np. `https://wodoskop(-[a-z0-9-]+)?\.vercel\.app` |

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
(zwykle **1–2 minuty**). Cache startuje z gotowego seeda (dane działek demo: działka, gleba, pogoda 10 lat, teren,
zdjęcie satelitarne, woda w okolicy, ortofotomapa) – przykłady liczą się od razu, bez zapytań do źródeł.

Ok. **10 minut przed oceną**:
1. Otwórz `https://wodoskop-api.onrender.com/api/status` – obudzi usługę i sprawdzi źródła (pierwsze otwarcie może
   trwać 1–2 min; odśwież, aż pokaże listę źródeł).
2. Otwórz `https://wodoskop.vercel.app/` i kliknij 2–3 przykłady – policzą się i trafią do cache.
3. Nie zostawiaj usługi bez ruchu na dłużej niż 15 minut przed pokazem (np. odśwież `/api/health` co kilka minut).

Opcjonalnie: darmowy zewnętrzny „pinger” (np. cron-job.org) otwierający `/api/health` co 10 minut trzyma usługę
w pogotowiu. Jedna usługa działająca całą dobę mieści się w darmowym limicie godzin Render.

## 6. Konsekwencje planu Free

- **Brak trwałego dysku.** Cache SQLite (`/data/cache.sqlite`) znika przy każdym restarcie, wdrożeniu i uśpieniu –
  dlatego obraz ma **gotowy seed** (`backend/app/data/seed/cache_seed.sqlite.gz`, wczytywany przy starcie, gdy cache
  jest pusty): działki demo i przykłady liczą się od razu. Nowe działki (spoza seeda) pobierają dane od zera –
  zwykle 10–30 s; teren, woda w okolicy i zdjęcie satelitarne liczą się w tle (analiza nie czeka).
  Prognozy i bieżących stanów wód w seedzie nie ma (wygasają w godzinę) – pobierają się przy pierwszej analizie.
  Trwały cache: plan **Starter** + dysk 1 GB – odkomentuj sekcję `disk` w `render.yaml`.
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

## 8. Backend pod hosting – zrobione (A13)

- **CORS** – `CORS_ORIGINS` (lista JSON) i opcjonalnie `CORS_ORIGIN_REGEX` dla podglądów Vercela
  (`allow_origin_regex` w `backend/app/main.py`).
- **Seed cache w obrazie** – `backend/scripts/export_seed.py` kopiuje z `/data/cache.sqlite` wszystkie wpisy poza
  prognozą Open-Meteo i bieżącymi stanami wód IMGW do `backend/app/data/seed/cache_seed.sqlite.gz`; przy starcie
  (`lifespan` → `load_seed()`), gdy tabela `cache` jest pusta, seed jest wczytywany przez `INSERT OR IGNORE`
  (wpis z wolumenu zawsze wygrywa). Odświeżenie seeda przed wdrożeniem (na dobrej sieci):
  `docker compose exec backend python scripts/warm_demo.py --no-pdf` → `docker compose exec backend python
  scripts/export_seed.py` → commit pliku `.gz`. Zgłoszenia rolników (`infra.sqlite`) do seeda nie trafiają.
- **`/api/health`** – lekki (`{"status":"ok"}`, bez zapytań zewnętrznych).
