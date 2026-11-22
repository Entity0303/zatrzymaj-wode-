"""NMT GUGiK – wysokości terenu ±0,1 m (CLAUDE.md, źródło 7). Port z prototypu osoby C (research/terrain, A6).

https://services.gugik.gov.pl/nmt/  POST request=GetHByPointList&list="x y,x y,..."
UWAGA: EPSG:2180 z kolejnością x = PÓŁNOC, y = WSCHÓD (odwrotnie niż ULDK!). POST – maks. 1000 punktów.
Odpowiedź: "x y h,x y h,..." (te same współrzędne co w zapytaniu). Punkt bez danych → 0.0 (sprawdzone na żywo
przez C w małopolskim) – zero traktujemy jako brak, gdy teren leży wyraźnie wyżej.
NMT potrafi zwrócić odpowiedź-śmieć (setki MB) – twardy limit rozmiaru i czasu w `core.http.request` (D56).

Cache (D53): cała siatka wysokości działki pod jednym kluczem (siatka jest wyznaczona przez obrys) – bez wygasania.
Zapisujemy tylko komplet (wszystkie paczki pobrane); błąd paczki = ponowienie, potem SourceError (bez cache).
"""

import asyncio
import math

import httpx
import numpy as np

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, request

SOURCE = "NMT GUGiK"
SOURCE_URL = "https://services.gugik.gov.pl/nmt/"
RESOLUTION = "NMT 1 m (wysokości ±0,1 m)"
CHUNK_POINTS = 1000
RETRIES = 2

_cache: TTLCache[tuple[np.ndarray, dict]] = TTLCache(ttl_s=None, max_items=128, name=SOURCE)


def parse_heights(text: str) -> dict[tuple[float, float], float]:
    """'N E h,N E h,…' → {(E, N): h} (klucz zaokrąglony do 0,1 m). Śmieci i wartości spoza −100…3000 m pomijane."""
    out: dict[tuple[float, float], float] = {}
    for trip in text.strip().split(","):
        parts = trip.split()
        if len(parts) < 3:
            continue
        try:
            x, y, h = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        if not math.isfinite(h) or h < -100 or h > 3000:
            continue
        out[(round(y, 1), round(x, 1))] = h  # x = północ, y = wschód → klucz (E, N)
    return out


def match_heights(e: np.ndarray, n: np.ndarray, text: str) -> np.ndarray:
    """Wysokości dopasowane do wysłanych punktów (E, N). NMT odsyła współrzędne zaokrąglone po swojemu (wysłane
    448300.25 → zwrócone 448300.2), więc dopasowanie po kluczu z 0,1 m gubiło ok. połowę punktów (A8: „brak 51%
    wysokości”). Najpierw po kolejności (odpowiedź w tej samej kolejności, tolerancja 0,15 m), potem po sąsiednich
    kluczach 0,1 m."""
    trips = []
    for trip in text.strip().split(","):
        parts = trip.split()
        if len(parts) < 3:
            continue
        try:
            x, y, h = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        ok = math.isfinite(h) and -100 <= h <= 3000
        trips.append((y, x, h if ok else math.nan))  # x = północ, y = wschód → (E, N, h)
    out = np.full(e.size, np.nan)
    if len(trips) == e.size:
        arr = np.array(trips, dtype=float)
        if np.all(np.abs(arr[:, 0] - e) <= 0.15) and np.all(np.abs(arr[:, 1] - n) <= 0.15):
            return arr[:, 2]
    by_key = {(round(E * 10), round(N * 10)): h for E, N, h in trips}
    for k, (ee, nn) in enumerate(zip(e, n)):
        ke, kn = round(float(ee) * 10), round(float(nn) * 10)
        for de in (0, -1, 1):
            for dn in (0, -1, 1):
                h = by_key.get((ke + de, kn + dn))
                if h is not None:
                    out[k] = h
                    break
            else:
                continue
            break
    return out


async def _chunk(e: np.ndarray, n: np.ndarray) -> np.ndarray:
    lst = ",".join(f"{nn:.2f} {ee:.2f}" for ee, nn in zip(e, n))  # NMT: x = PÓŁNOC, y = WSCHÓD
    last = "brak odpowiedzi"
    for attempt in range(RETRIES + 1):
        if attempt:
            await asyncio.sleep(settings.nmt_retry_delay_s * attempt)
        try:
            resp = await request("POST", settings.nmt_url, source=SOURCE, timeout_s=settings.nmt_timeout_s,
                                 data={"request": "GetHByPointList", "list": lst}, max_bytes=80 * len(e) + 10_000)
        except RedirectBlocked:
            raise  # blokada – nie ponawiamy (bezpiecznik w cached_fetch)
        except httpx.TimeoutException:
            last = f"usługa nie odpowiada (przekroczono {settings.nmt_timeout_s:.0f} s)"
            continue
        except httpx.TransportError as exc:
            last = f"brak połączenia z usługą ({exc.__class__.__name__})"
            continue
        except SourceError as exc:  # odpowiedź-śmieć za duża / za długa – ponawiamy
            last = exc.message
            continue
        if resp.status_code == 429:
            raise SourceError(SOURCE, "przekroczony limit zapytań (HTTP 429)")
        if resp.status_code >= 400:
            last = f"usługa zwróciła błąd HTTP {resp.status_code}"
            continue
        return match_heights(e, n, resp.text)
    raise SourceError(SOURCE, last)


async def _download(e: np.ndarray, n: np.ndarray) -> tuple[np.ndarray, dict]:
    idx = [np.arange(k, min(k + CHUNK_POINTS, e.size)) for k in range(0, e.size, CHUNK_POINTS)]
    sem = asyncio.Semaphore(max(1, settings.nmt_parallel))

    async def job(i, ix):
        async with sem:
            if i and settings.nmt_parallel <= 1:
                await asyncio.sleep(settings.nmt_chunk_pause_s)  # spokojnie – paczki po kolei z przerwą (A8)
            return ix, await _chunk(e[ix], n[ix])

    results = await asyncio.gather(*(job(i, ix) for i, ix in enumerate(idx)))
    h = np.full(e.size, np.nan)
    for ix, res in results:
        h[ix] = res
    zeros = 0
    if np.isfinite(h).any() and np.nanmedian(h) > 5.0:  # 0,0 = brak danych (Żuławy < 0 m zostają)
        zmask = h == 0.0
        zeros = int(zmask.sum())
        h[zmask] = np.nan
    missing = float(np.isnan(h).mean())
    if missing > 0.3:
        raise SourceError(SOURCE, f"brak {round(100 * missing)}% wysokości w odpowiedzi")
    return h, {"requests": len(idx), "failed_requests": 0, "zero_values": zeros, "missing_share": missing,
               "points": int(e.size)}


async def heights_for_grid(key: tuple, e: np.ndarray, n: np.ndarray) -> tuple[np.ndarray, dict]:
    """Wysokości NMT dla punktów (E, N) siatki działki – z cache albo POST po ≤ 1000 punktów (równolegle)."""
    e = np.asarray(e, dtype=float).ravel()
    n = np.asarray(n, dtype=float).ravel()
    return await cached_fetch(_cache, key, SOURCE, lambda: _download(e, n), timeout_s=settings.nmt_total_timeout_s,
                              breaker_s=120)


def clear_cache() -> None:
    _cache.clear()
