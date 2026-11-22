"""OpenStreetMap Overpass API – cieki, rowy, kanały i zbiorniki wokół działki (A9, D92).

https://overpass-api.de/api/interpreter (POST data=…). Sprawdzone 22.11.2026: odpowiada, ale wolno (ok. 30 s przy
obciążeniu; druga instancja kumi.systems – przekroczony czas) – dlatego woda w okolicy liczy się W TLE, a wynik jest
w cache bez wygasania (obiekty wodne zmieniają się rzadko). Licencja danych: ODbL – atrybucja „© autorzy
OpenStreetMap”. Zakres: waterway=river/stream/canal/ditch/drain, natural=water (+ water=pond/reservoir/lake/…).
Zapytania po jednym naraz (lock) – polityka publicznych instancji Overpass.

P1 (pomiar 22.11.2026: overpass-api.de – błąd połączenia po 21 s, private.coffee – 504 / limit czasu po 30–60 s,
mail.ru – 15–59 s; odpowiedzi mają 0,3 kB, więc hamulcem są serwery, nie rozmiar): wszystkie instancje pytane
RÓWNOLEGLE, pierwsza dobra odpowiedź wygrywa (reszta anulowana); najwyżej 8 s na serwer i 15 s łącznie; w zapytaniu
[timeout:10]; wynik w cache 30 dni; gdy żaden serwer nie odpowie – „brak danych” pamiętany tylko 10 minut dla tego
miejsca (bez bezpiecznika na całe źródło).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, request

SOURCE = "OpenStreetMap Overpass"
SOURCE_URL = "https://www.openstreetmap.org/copyright"
ATTRIBUTION = "© autorzy OpenStreetMap (ODbL)"
_cache: TTLCache[list] = TTLCache(ttl_s=None, max_items=2048, name=SOURCE)
_gate = asyncio.Lock()
log = logging.getLogger("uvicorn.error")
CACHE_TTL_S = 30 * 86400.0  # P1: rowy i zbiorniki zmieniają się rzadko – 30 dni
FAIL_TTL_S = 600.0          # P1: żaden serwer nie odpowiedział – nie pytamy o to miejsce przez 10 minut
FAIL_MESSAGE = "Mapa rowów (OpenStreetMap) chwilowo nie odpowiada – spróbuj za chwilę"
_failed: dict[tuple, float] = {}  # klucz bbox → do kiedy (time.time()) pamiętamy „brak danych”
last_fetch: dict = {}             # diagnostyka: który serwer odpowiedział, ilu próbowano, czas, rozmiar


def query(bbox: tuple[float, float, float, float]) -> str:
    """bbox = (lon_min, lat_min, lon_max, lat_max) → zapytanie Overpass QL (kolejność S, W, N, E)."""
    w, s, e, n = bbox
    b = f"({s:.5f},{w:.5f},{n:.5f},{e:.5f})"
    # P1: tylko rowy / cieki / kanały i zbiorniki; limit po stronie serwera 10 s
    return (f'[out:json][timeout:{int(settings.overpass_query_timeout_s)}];('
            f'way["waterway"~"^(ditch|drain|stream|canal|river)$"]{b};'
            f'way["natural"="water"]{b};relation["natural"="water"]{b};'
            f'way["water"]{b};way["landuse"="reservoir"]{b};'
            f');out geom;')


def urls() -> list[str]:
    extra = [u.strip() for u in (settings.overpass_fallback_urls or "").split(",") if u.strip()]
    return [settings.overpass_url, *extra]


async def _one(url: str, bbox: tuple[float, float, float, float]) -> list:
    try:
        resp = await request("POST", url, source=SOURCE, timeout_s=settings.overpass_server_timeout_s,
                             data={"data": query(bbox)}, max_bytes=20_000_000)
    except RedirectBlocked as exc:
        raise SourceError(SOURCE, exc.message) from exc
    except httpx.TimeoutException as exc:
        raise SourceError(SOURCE, "usługa nie odpowiada (przekroczony czas)") from exc
    except httpx.TransportError as exc:
        raise SourceError(SOURCE, f"brak połączenia z usługą ({exc.__class__.__name__})") from exc
    if resp.status_code == 429:
        raise SourceError(SOURCE, "usługa ogranicza liczbę zapytań (HTTP 429)")
    if resp.status_code != 200:
        raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
    try:
        data = json.loads(resp.text)
    except ValueError as exc:
        raise SourceError(SOURCE, "nieprawidłowa odpowiedź (JSON)") from exc
    if "elements" not in data:  # np. komunikat o przeciążeniu w treści 200
        raise SourceError(SOURCE, "odpowiedź bez danych")
    last_fetch["bytes"] = len(resp.content)
    return data["elements"]


async def _download(bbox: tuple[float, float, float, float]) -> list:
    """P1: wszystkie instancje równolegle – pierwsza dobra odpowiedź wygrywa, reszta anulowana; najwyżej
    `overpass_server_timeout_s` na serwer i `overpass_total_timeout_s` łącznie. Jedno miejsce naraz (lock)."""
    servers = urls()
    if not servers:
        raise SourceError(SOURCE, "brak instancji Overpass")
    async with _gate:
        t0 = time.monotonic()
        tasks = {asyncio.ensure_future(_one(u, bbox)): u for u in servers}
        pending = set(tasks)
        errors: list[str] = []
        try:
            while pending:
                left = settings.overpass_total_timeout_s - (time.monotonic() - t0)
                if left <= 0:
                    break
                done, pending = await asyncio.wait(pending, timeout=left, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    if t.cancelled():
                        continue
                    exc = t.exception()
                    if exc is None:
                        last_fetch.update(server=tasks[t].split("/")[2], tried=len(servers),
                                          seconds=round(time.monotonic() - t0, 1), elements=len(t.result()))
                        log.info("Overpass: odpowiedział %s w %.1f s (pytano %d serwery równolegle, %d obiektów)",
                                 last_fetch["server"], last_fetch["seconds"], len(servers), len(t.result()))
                        return t.result()
                    errors.append(f"{tasks[t].split('/')[2]}: {getattr(exc, 'message', exc.__class__.__name__)}")
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
        last_fetch.update(server=None, tried=len(servers), seconds=round(time.monotonic() - t0, 1), elements=None)
        log.warning("Overpass: żaden z %d serwerów nie odpowiedział w %.1f s (%s)", len(servers),
                    time.monotonic() - t0, "; ".join(errors) or "limit czasu")
    raise SourceError(SOURCE, FAIL_MESSAGE)


def _key(bbox: tuple[float, float, float, float]) -> tuple:
    return tuple(round(v, 4) for v in bbox)


async def water_elements(bbox: tuple[float, float, float, float]) -> list:
    """Obiekty wodne w bbox – cache 30 dni; po nieudanej próbie wszystkich serwerów „brak danych” przez 10 minut
    (bez kolejnych zapytań o to miejsce), potem znowu próba."""
    key = _key(bbox)
    until = _failed.get(key)
    if until is not None:
        if time.time() < until and _cache.get(key) is None:
            stale = _cache.get_stale(key)
            if stale is not None:
                return stale[0]
            raise SourceError(SOURCE, FAIL_MESSAGE)
        _failed.pop(key, None)
    try:
        return await cached_fetch(_cache, key, SOURCE, lambda: _download(bbox), ttl_s=CACHE_TTL_S)
    except SourceError:
        _failed[key] = time.time() + FAIL_TTL_S
        raise


def cached_elements(bbox: tuple[float, float, float, float]) -> list | None:
    key = _key(bbox)
    hit = _cache.get(key)
    if hit is None:
        stale = _cache.get_stale(key)
        hit = stale[0] if stale else None
    return hit


def clear_cache() -> None:
    _cache.clear()
    _failed.clear()
