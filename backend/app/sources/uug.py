"""UUG GUGiK – Usługa Uniwersalnego Geokodowania (adresy z PRG), A9 / A5f.

https://services.gugik.gov.pl/uug/?request=GetAddress&address=Tczów 123  (wieś bez ulic)
https://services.gugik.gov.pl/uug/?request=GetAddress&address=Kraków, Długa 5  (miejscowość, ulica numer)
Sprawdzone na żywo 22.11.2026 (VPN): JSON, `results` = słownik {"1": {city, citypart, street, number, teryt, simc, ulic,
code, jednostka „{Polska,woj.,powiat,gmina}”, x, y (EPSG:2180, x = wschód), accuracy}}, 0,2 s. Brak wyników =
`results: null` / „found objects: 0”. Z sali hackathonu wcześniej „blocked for abuse” – dlatego klucz `uug`
w OFFLINE_SOURCES (D89), cache bez wygasania, bezpiecznik i wspólny limit zapytań GUGiK (2 naraz, 0,5 s).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from pyproj import Transformer

from app.core.cache import FOREVER, TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import NotFoundError, RedirectBlocked, SourceError, request
from app.core.search_query import fold

SOURCE = "UUG GUGiK (adresy PRG)"
SOURCE_URL = "https://services.gugik.gov.pl/uug/"
ATTRIBUTION = "Adresy: PRG GUGiK"
_TR = Transformer.from_crs(2180, 4326, always_xy=True)
_cache: TTLCache[list] = TTLCache(ttl_s=None, max_items=4096, name=SOURCE)


@dataclass
class Address:
    id: str
    locality: str
    street: str | None
    house_number: str
    gmina: str
    powiat: str
    wojewodztwo: str
    lon: float
    lat: float
    source: str  # "prg" | "osm"


def parse(payload: dict | str) -> list[Address]:
    d = json.loads(payload) if isinstance(payload, str) else payload
    res = d.get("results") if isinstance(d, dict) else None
    items = res.values() if isinstance(res, dict) else (res or [])
    out: list[Address] = []
    for it in items:
        try:
            x, y = float(it["x"]), float(it["y"])
        except (KeyError, TypeError, ValueError):
            continue
        lon, lat = _TR.transform(x, y)
        parts = [p.strip() for p in str(it.get("jednostka") or "").strip("{}").split(",")]
        woj, pow_, gm = (parts + ["", "", "", ""])[1:4]
        street = (it.get("street") or "").strip() or None
        out.append(Address(
            id=f"prg:{it.get('simc') or ''}-{it.get('ulic') or ''}-{it.get('number')}", locality=it.get("city") or "",
            street=street, house_number=str(it.get("number") or ""), gmina=gm, powiat=pow_, wojewodztwo=woj,
            lon=round(lon, 6), lat=round(lat, 6), source="prg"))
    return out


async def _download(address: str) -> list:
    try:
        resp = await request("GET", settings.uug_url, source=SOURCE, timeout_s=settings.uug_timeout_s,
                             params={"request": "GetAddress", "address": address}, max_bytes=2_000_000)
    except RedirectBlocked as exc:
        raise SourceError(SOURCE, exc.message) from exc
    except httpx.TimeoutException as exc:
        raise SourceError(SOURCE, "usługa nie odpowiada") from exc
    except httpx.TransportError as exc:
        raise SourceError(SOURCE, f"brak połączenia z usługą ({exc.__class__.__name__})") from exc
    if resp.status_code != 200:
        raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
    text = resp.text.strip()
    if "blocked" in text[:300].lower() or not text.startswith("{"):
        raise SourceError(SOURCE, "usługa odrzuciła zapytanie (blokada)")
    try:
        return [a.__dict__ for a in parse(text)]
    except ValueError as exc:
        raise SourceError(SOURCE, "nieprawidłowa odpowiedź usługi (JSON)") from exc


async def find(locality: str, number: str, street: str | None = None) -> list[Address]:
    """Adresy z PRG: „Tczów 123” (wieś bez ulic) albo „Kraków, Długa 5”. Tylko dokładny numer i zgodna miejscowość."""
    q = f"{locality}, {street} {number}" if street else f"{locality} {number}"
    rows = await cached_fetch(_cache, ("addr", fold(q)), SOURCE, lambda: _download(q), ttl_s=FOREVER,
                              breaker_s=settings.uug_breaker_s)
    out = [Address(**r) for r in rows]
    want = fold(locality)
    return [a for a in out if a.house_number.lower() == number.lower()
            and (fold(a.locality) == want or fold(a.locality).startswith(want))]


def clear_cache() -> None:
    _cache.clear()


__all__ = ["Address", "find", "parse", "SOURCE", "ATTRIBUTION", "NotFoundError"]
