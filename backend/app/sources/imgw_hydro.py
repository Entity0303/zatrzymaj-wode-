"""IMGW-PIB – bieżące stany wody na wodowskazach (A9, D92).

https://danepubliczne.imgw.pl/api/data/hydro – lista ok. 900 stacji (sprawdzone 22.11.2026, 0,55 MB, 1 s): id_stacji,
stacja, rzeka, lon, lat, stan_wody [cm], stan_wody_data_pomiaru, stan_ostrzegawczy, stan_alarmowy. Cache 1 h (stan
zmienia się w ciągu dnia), bez przekierowań, limit rozmiaru. „Niski / średni / wysoki” – względem percentyli stanu
z tego samego miesiąca w latach 2016–2025 (app/data/imgw/hydro_levels.json, scripts/build_imgw_hydro.py); stan
≥ ostrzegawczego = wysoki. Licencja: dane IMGW-PIB z podaniem źródła.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, request

SOURCE = "IMGW-PIB (stany wód)"
SOURCE_URL = "https://danepubliczne.imgw.pl"
LEVELS_FILE = Path(__file__).parents[1] / "data" / "imgw" / "hydro_levels.json"
_cache: TTLCache[list] = TTLCache(ttl_s=3600, max_items=4, name=SOURCE)


@dataclass
class Gauge:
    code: str
    name: str
    river: str
    lon: float
    lat: float
    level_cm: float | None
    date: str | None
    warning_cm: float | None
    alarm_cm: float | None


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse(items: list) -> list[Gauge]:
    out = []
    for it in items if isinstance(items, list) else []:
        lon, lat = _f(it.get("lon")), _f(it.get("lat"))
        if lon is None or lat is None:
            continue
        out.append(Gauge(code=str(it.get("id_stacji") or ""), name=(it.get("stacja") or "").strip().title(),
                         river=(it.get("rzeka") or "").strip(), lon=lon, lat=lat, level_cm=_f(it.get("stan_wody")),
                         date=(it.get("stan_wody_data_pomiaru") or "")[:10] or None,
                         warning_cm=_f(it.get("stan_ostrzegawczy")), alarm_cm=_f(it.get("stan_alarmowy"))))
    return out


async def _download() -> list:
    try:
        resp = await request("GET", settings.imgw_hydro_url, source=SOURCE, timeout_s=15, max_bytes=5_000_000)
    except RedirectBlocked as exc:
        raise SourceError(SOURCE, exc.message) from exc
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise SourceError(SOURCE, f"brak połączenia z usługą ({exc.__class__.__name__})") from exc
    if resp.status_code != 200:
        raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
    try:
        return json.loads(resp.text)
    except ValueError as exc:
        raise SourceError(SOURCE, "nieprawidłowa odpowiedź (JSON)") from exc


def cached() -> list[Gauge] | None:
    """Stany z cache (bez sieci) – analiza nie czeka; None = jeszcze nie pobrano."""
    hit = _cache.get(("hydro",))
    if hit is None:
        stale = _cache.get_stale(("hydro",))
        hit = stale[0] if stale else None
    return None if hit is None else parse(hit)


async def gauges() -> list[Gauge]:
    return parse(await cached_fetch(_cache, ("hydro",), SOURCE, _download, breaker_s=300))


@lru_cache(maxsize=1)
def _levels() -> dict:
    try:
        return json.loads(LEVELS_FILE.read_text(encoding="utf-8")).get("stations", {})
    except FileNotFoundError:
        return {}


def state(g: Gauge, month: int) -> str | None:
    """niski / sredni / wysoki – względem P33 / P66 z 10 lat (ten sam miesiąc); ≥ ostrzegawczego = wysoki."""
    if g.level_cm is None:
        return None
    if g.warning_cm is not None and g.level_cm >= g.warning_cm:
        return "wysoki"
    p = (_levels().get(g.code) or {}).get("p", {}).get(str(month))
    if not p:
        return None
    return "niski" if g.level_cm <= p[1] else "wysoki" if g.level_cm >= p[2] else "sredni"


def km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest(gs: list[Gauge], lon: float, lat: float, month: int, max_km: float = 40.0) -> tuple[Gauge, float, str] | None:
    """Najbliższy wodowskaz z bieżącym stanem i oceną (stacje bez percentyli / bez stanu – pomijane)."""
    best = None
    for g in gs:
        st = state(g, month)
        if st is None:
            continue
        d = km(lon, lat, g.lon, g.lat)
        if d <= max_km and (best is None or d < best[1]):
            best = (g, d, st)
    return best


def clear_cache() -> None:
    _cache.clear()
