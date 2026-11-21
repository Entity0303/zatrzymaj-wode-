"""Nominatim OSM – rezerwa geokodera (A5c, D73): gdy PRNG GUGiK nie odpowiada albo nie zna nazwy (np. gmina, nazwa bez
ogonków), oraz odwrotne geokodowanie środka narysowanego pola (gmina / powiat / województwo).

Zasady OSM (https://operations.osmfoundation.org/policies/nominatim/): najwyżej 1 zapytanie na sekundę, identyfikujący
User-Agent („Wodoskop/0.1 …” z `settings.user_agent`), wyniki w cache, atrybucja „© autorzy OpenStreetMap”.
Sprawdzone na żywo 2026-11-21: `search?q=Tczów&countrycodes=pl&format=jsonv2&addressdetails=1` – 0,2 s, gmina i powiat w
`address`, `boundingbox` = [południe, północ, zachód, wschód]; „Nowa Wieś” → 40 trafień z gminami.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass

import httpx

from app.core.cache import FOREVER, TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, request
from app.core.search_query import fold

SOURCE = "OpenStreetMap Nominatim"
SOURCE_URL = "https://nominatim.openstreetmap.org/"
ATTRIBUTION = "© autorzy OpenStreetMap (ODbL)"
LIMIT = 40
# addresstype → rodzaj wyniku w naszym kontrakcie
_PLACE_TYPES = {"village", "hamlet", "town", "city", "suburb", "neighbourhood", "isolated_dwelling", "locality",
                "borough", "quarter", "farm"}
_ADMIN_TYPES = {"municipality": "gmina"}

_cache: TTLCache[list[dict]] = TTLCache(ttl_s=None, max_items=4096, name=SOURCE)
_gate = asyncio.Lock()
_last_request = 0.0


@dataclass
class OsmPlace:
    osm_id: str
    name: str
    type: str                # miejscowosc | gmina
    type_label: str          # wieś, miasto, gmina …
    gmina: str
    powiat: str
    wojewodztwo: str
    lon: float
    lat: float
    bbox: tuple[float, float, float, float] | None  # lon_min, lat_min, lon_max, lat_max


def strip_prefix(value: str | None, prefix: str) -> str:
    """„województwo mazowieckie” → „mazowieckie”, „powiat zwoleński” → „zwoleński”, „gmina Tczów” → „Tczów”."""
    v = (value or "").strip()
    return v[len(prefix):].strip() if v.lower().startswith(prefix) else v


async def _get(path: str, params: dict) -> list | dict:
    global _last_request
    headers = {"Accept-Language": "pl"}
    async with _gate:
        wait = settings.nominatim_min_interval_s - (time.monotonic() - _last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request = time.monotonic()
        try:
            resp = await request("GET", settings.nominatim_url.rstrip("/") + path, source=SOURCE,
                                 timeout_s=settings.nominatim_timeout_s, params=params, headers=headers,
                                 max_bytes=3_000_000)
        except RedirectBlocked as exc:
            raise SourceError(SOURCE, exc.message) from exc
        except httpx.TimeoutException as exc:
            raise SourceError(SOURCE, f"usługa nie odpowiada (przekroczono {settings.nominatim_timeout_s:.0f} s)") from exc
        except httpx.TransportError as exc:
            raise SourceError(SOURCE, f"brak połączenia z usługą ({exc.__class__.__name__})") from exc
    if resp.status_code == 429:
        raise SourceError(SOURCE, "usługa ogranicza liczbę zapytań (HTTP 429)")
    if resp.status_code != 200:
        raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
    try:
        return json.loads(resp.text)
    except ValueError as exc:
        raise SourceError(SOURCE, "nieprawidłowa odpowiedź usługi (JSON)") from exc


def parse_search(items: list) -> list[OsmPlace]:
    out: list[OsmPlace] = []
    seen: set[tuple] = set()
    for it in items if isinstance(items, list) else []:
        atype = it.get("addresstype") or it.get("type") or ""
        if atype in _PLACE_TYPES:
            kind = "miejscowosc"
        elif atype in _ADMIN_TYPES:
            kind = _ADMIN_TYPES[atype]
        else:
            continue
        addr = it.get("address") or {}
        name = it.get("name") or addr.get(atype) or ""
        if not name:
            continue
        gmina = strip_prefix(addr.get("municipality"), "gmina")
        powiat = strip_prefix(addr.get("county"), "powiat")
        woj = strip_prefix(addr.get("state"), "województwo")
        if kind == "gmina":
            name = strip_prefix(name, "gmina")  # OSM: „gmina Tczów”
            gmina = gmina or name
        key = (fold(name), gmina, powiat, kind)
        if key in seen:
            continue
        seen.add(key)
        try:
            lon, lat = float(it["lon"]), float(it["lat"])
        except (KeyError, ValueError, TypeError):
            continue
        bb = it.get("boundingbox")
        bbox = None
        if isinstance(bb, list) and len(bb) == 4:
            try:
                s_, n_, w_, e_ = (float(x) for x in bb)
                bbox = (w_, s_, e_, n_)
            except ValueError:
                bbox = None
        label = {"municipality": "gmina", "city": "miasto", "town": "miasto", "village": "wieś", "hamlet": "osada",
                 "suburb": "dzielnica", "neighbourhood": "osiedle", "quarter": "dzielnica", "borough": "dzielnica",
                 "isolated_dwelling": "osada", "farm": "osada", "locality": "miejscowość"}.get(atype, "miejscowość")
        out.append(OsmPlace(osm_id=f"{it.get('osm_type', 'osm')}/{it.get('osm_id', '')}", name=name, type=kind,
                            type_label=label, gmina=gmina, powiat=powiat, wojewodztwo=woj, lon=lon, lat=lat, bbox=bbox))
    return out


async def search(name: str) -> list[OsmPlace]:
    q = re.sub(r"\s+", " ", name).strip()
    key = ("search", fold(q))

    async def download() -> list[dict]:
        data = await _get("/search", {"q": q, "countrycodes": "pl", "format": "jsonv2", "addressdetails": "1",
                                      "limit": str(LIMIT), "dedupe": "1", "accept-language": "pl"})
        return data if isinstance(data, list) else []

    items = await cached_fetch(_cache, key, SOURCE, download, ttl_s=FOREVER, breaker_s=settings.nominatim_breaker_s)
    want = fold(q)
    return [p for p in parse_search(items) if fold(p.name).startswith(want)]


@dataclass
class Admin:
    wojewodztwo: str
    powiat: str
    gmina: str
    miejscowosc: str


async def reverse(lon: float, lat: float) -> Admin | None:
    """Gmina / powiat / województwo / miejscowość w punkcie (środek narysowanego pola). Wynik zaokrąglony do ~100 m
    i trzymany w cache bez wygasania."""
    key = ("reverse", round(lon, 3), round(lat, 3))

    async def download() -> list[dict]:
        data = await _get("/reverse", {"lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2", "zoom": "14",
                                       "addressdetails": "1", "accept-language": "pl"})
        return [data] if isinstance(data, dict) else []

    items = await cached_fetch(_cache, key, SOURCE, download, ttl_s=FOREVER, breaker_s=settings.nominatim_breaker_s)
    if not items:
        return None
    addr = items[0].get("address") or {}
    woj = strip_prefix(addr.get("state"), "województwo")
    if not woj:
        return None
    town = addr.get("village") or addr.get("hamlet") or addr.get("town") or addr.get("city") or addr.get("suburb") or ""
    return Admin(wojewodztwo=woj, powiat=strip_prefix(addr.get("county"), "powiat"),
                 gmina=strip_prefix(addr.get("municipality"), "gmina"), miejscowosc=town)


def clear_cache() -> None:
    global _last_request
    _cache.clear()
    _last_request = 0.0
