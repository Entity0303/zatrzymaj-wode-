"""OpenStreetMap Overpass API – cieki, rowy, kanały i zbiorniki wokół działki (A9, D92).

https://overpass-api.de/api/interpreter (POST data=…). Sprawdzone 22.11.2026: odpowiada, ale wolno (ok. 30 s przy
obciążeniu; druga instancja kumi.systems – przekroczony czas) – dlatego woda w okolicy liczy się W TLE, a wynik jest
w cache bez wygasania (obiekty wodne zmieniają się rzadko). Licencja danych: ODbL – atrybucja „© autorzy
OpenStreetMap”. Zakres: waterway=river/stream/canal/ditch/drain, natural=water (+ water=pond/reservoir/lake/…).
Zapytania po jednym naraz (lock) – polityka publicznych instancji Overpass.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from app.core.cache import FOREVER, TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, request

SOURCE = "OpenStreetMap Overpass"
SOURCE_URL = "https://www.openstreetmap.org/copyright"
ATTRIBUTION = "© autorzy OpenStreetMap (ODbL)"
_cache: TTLCache[list] = TTLCache(ttl_s=None, max_items=2048, name=SOURCE)
_gate = asyncio.Lock()


def query(bbox: tuple[float, float, float, float]) -> str:
    """bbox = (lon_min, lat_min, lon_max, lat_max) → zapytanie Overpass QL (kolejność S, W, N, E)."""
    w, s, e, n = bbox
    b = f"({s:.5f},{w:.5f},{n:.5f},{e:.5f})"
    return (f'[out:json][timeout:{int(settings.overpass_timeout_s)}];('
            f'way["waterway"~"^(river|stream|canal|ditch|drain)$"]{b};'
            f'way["natural"="water"]{b};relation["natural"="water"]{b};'
            f');out geom;')


def urls() -> list[str]:
    extra = [u.strip() for u in (settings.overpass_fallback_urls or "").split(",") if u.strip()]
    return [settings.overpass_url, *extra]


async def _one(url: str, bbox: tuple[float, float, float, float]) -> list:
    try:
        resp = await request("POST", url, source=SOURCE, timeout_s=settings.overpass_timeout_s + 5,
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
        return json.loads(resp.text).get("elements", [])
    except ValueError as exc:
        raise SourceError(SOURCE, "nieprawidłowa odpowiedź (JSON)") from exc


async def _download(bbox: tuple[float, float, float, float]) -> list:
    """Instancje po kolei – następna tylko po błędzie poprzedniej (jedno zapytanie naraz)."""
    last: SourceError | None = None
    async with _gate:
        for url in urls():
            try:
                return await _one(url, bbox)
            except SourceError as exc:
                last = exc
    raise last or SourceError(SOURCE, "brak instancji Overpass")


async def water_elements(bbox: tuple[float, float, float, float]) -> list:
    key = tuple(round(v, 4) for v in bbox)
    return await cached_fetch(_cache, key, SOURCE, lambda: _download(bbox), ttl_s=FOREVER,
                              breaker_s=settings.overpass_breaker_s)


def cached_elements(bbox: tuple[float, float, float, float]) -> list | None:
    key = tuple(round(v, 4) for v in bbox)
    hit = _cache.get(key)
    if hit is None:
        stale = _cache.get_stale(key)
        hit = stale[0] if stale else None
    return hit


def clear_cache() -> None:
    _cache.clear()
