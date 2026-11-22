"""PIG-PIB (Państwowy Instytut Geologiczny, CBDG) – obszary zagrożone podtopieniami (A27).

Usługa (sprawdzona na żywo 22.11.2026): ArcGIS REST
https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/podtopienia/MapServer/0 – warstwa poligonowa „obszary
zagrożone powodzią od wód gruntowych (podtopienia)” w obrębie dużych dolin rzecznych (Mapa obszarów zagrożonych
podtopieniami, MOZP). Zapytanie `query` punktem w EPSG:4326 (`esriSpatialRelIntersects`) – ok. 0,2 s; pola: `OPIS`,
`REG_WOD`. Pusta lista `features` = punkt poza obszarem.

Czego NIE ma: głębokości do pierwszego zwierciadła wód podziemnych (Mapa hydrogeologiczna Polski 1:50 000, warstwa
„Pierwszy poziom wodonośny”) – w katalogu usług CBDG (`hydrogeologia`: cbdh_otwory, gzwp, jcwpd, mineralne, mwp,
mwp_auto, pobory, podtopienia) nie ma jej jako usługi do odpytania w punkcie; e-PSH udostępnia tylko harmonogram
arkuszy. Dlatego głębokości NIE podajemy (nie zgadujemy) – patrz `DEPTH_NOTE`.

Warunki: metadane usługi nie podają opłat ani ograniczeń (`copyrightText` puste); podajemy źródło „PIG-PIB”.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.cache import TTLCache, cached_fetch
from app.core.http import RedirectBlocked, SourceError, request

SOURCE = "PIG-PIB"
SOURCE_LABEL = "PIG-PIB – obszary zagrożone podtopieniami (CBDG)"
SOURCE_URL = "https://cbdgmapa.pgi.gov.pl/"
QUERY_URL = "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/podtopienia/MapServer/0/query"
TIMEOUT_S = 8.0
TTL_S = 30 * 86400.0  # dane statyczne
DEPTH_NOTE = ("Głębokości do wody gruntowej nie podajemy – PIG-PIB nie udostępnia jej usługą, którą da się odpytać "
              "dla punktu działki.")
UNAVAILABLE_NOTE = "usługa PIG niedostępna"
_cache: TTLCache["FloodZone"] = TTLCache(ttl_s=TTL_S, max_items=4096, name=SOURCE)


@dataclass(frozen=True)
class FloodZone:
    """Czy punkt leży na obszarze zagrożonym podtopieniami (MOZP)."""

    in_zone: bool
    description: str | None = None  # pole OPIS
    water_region: str | None = None  # pole REG_WOD


def parse(payload: dict) -> FloodZone:
    if not isinstance(payload, dict) or "error" in payload or "features" not in payload:
        raise SourceError(SOURCE, "nieoczekiwana odpowiedź usługi")
    feats = payload.get("features") or []
    if not feats:
        return FloodZone(False)
    attrs = feats[0].get("attributes") or {}
    return FloodZone(True, (attrs.get("OPIS") or None), (attrs.get("REG_WOD") or None))


async def flood_zone(lon: float, lat: float) -> FloodZone:
    """Punkt (WGS84) w obszarze zagrożonym podtopieniami? Cache 30 dni; błąd usługi → SourceError."""
    key = (round(lon, 4), round(lat, 4))

    async def download() -> FloodZone:
        params = {"geometry": f"{lon:.6f},{lat:.6f}", "geometryType": "esriGeometryPoint", "inSR": "4326",
                  "spatialRel": "esriSpatialRelIntersects", "outFields": "OPIS,REG_WOD", "returnGeometry": "false",
                  "f": "json"}
        try:
            resp = await request("GET", QUERY_URL, source=SOURCE, timeout_s=TIMEOUT_S, params=params, max_bytes=500_000)
        except RedirectBlocked as exc:
            raise SourceError(SOURCE, exc.message) from exc
        except httpx.TimeoutException as exc:
            raise SourceError(SOURCE, f"usługa nie odpowiada (przekroczono {TIMEOUT_S:.0f} s)") from exc
        except httpx.TransportError as exc:
            raise SourceError(SOURCE, f"brak połączenia z usługą ({exc.__class__.__name__})") from exc
        if resp.status_code != 200:
            raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
        try:
            return parse(resp.json())
        except ValueError as exc:
            raise SourceError(SOURCE, "odpowiedź nie jest poprawnym JSON-em") from exc

    return await cached_fetch(_cache, key, SOURCE, download, ttl_s=TTL_S, breaker_s=120, breaker_after=3,
                              breaker_window_s=60)


def clear_cache() -> None:
    _cache.clear()
