"""Miejscowości po nazwie (A5c, D73): słownik demo (offline) + PRNG GUGiK (główne) + Nominatim OSM (rezerwa).

Kolejność: słownik demo → PRNG → Nominatim, gdy PRNG nie odpowiada albo nic nie zna. Awaria źródła nie wywraca
wyszukiwania – trafia do `notices`. W trybie DEMO_OFFLINE tylko słownik i cache. Wyniki scalane bez powtórzeń
(nazwa + gmina + powiat), dokładna nazwa przed początkiem nazwy, miasta przed wsiami, potem województwo / powiat / gmina.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.core.http import SourceError
from app.core.search_query import fold
from app.sources import nominatim, prng

DEMO_FILE = Path(__file__).parents[1] / "data" / "places_demo.json"
SOURCE_DEMO = "słownik demo"
# bbox wokół punktu (PRNG podaje tylko punkt): wieś ~2 × 2 km, miasto ~6 × 5 km
HALF_VILLAGE = (0.015, 0.010)
HALF_TOWN = (0.04, 0.025)


@dataclass
class Place:
    id: str
    name: str
    type: str                       # miejscowosc | gmina | obreb
    type_label: str
    gmina: str
    powiat: str
    wojewodztwo: str
    lon: float
    lat: float
    bbox: tuple[float, float, float, float] | None
    bbox_approx: bool
    source: str


@dataclass
class PlacesResult:
    places: list[Place]
    truncated: bool
    notices: list[str]
    attribution: str | None = None


def point_bbox(lon: float, lat: float, town: bool) -> tuple[float, float, float, float]:
    dx, dy = HALF_TOWN if town else HALF_VILLAGE
    return (round(lon - dx, 5), round(lat - dy, 5), round(lon + dx, 5), round(lat + dy, 5))


@lru_cache
def _local() -> tuple[Place, ...]:
    try:
        raw = json.loads(DEMO_FILE.read_text(encoding="utf-8"))["places"]
    except FileNotFoundError:
        return ()
    out = []
    for d in raw:
        town = d.get("type_label") == "miasto"
        out.append(Place(id=f"demo:{d['name']}|{d['gmina']}", name=d["name"], type=d.get("type", "miejscowosc"),
                         type_label=d.get("type_label", "miejscowość"), gmina=d["gmina"], powiat=d["powiat"],
                         wojewodztwo=d["wojewodztwo"], lon=d["lon"], lat=d["lat"],
                         bbox=tuple(d["bbox"]) if d.get("bbox") else point_bbox(d["lon"], d["lat"], town),
                         bbox_approx=not d.get("bbox"), source=SOURCE_DEMO))
    return tuple(out)


def _matches_hint(p: Place, hint: list[str]) -> bool:
    if not hint:
        return True
    hay = fold(" ".join([p.gmina, p.powiat, p.wojewodztwo]))
    return all(fold(h) in hay for h in hint)


def _from_prng(p: prng.PrngPlace) -> Place:
    town = p.kind == "miasto"
    return Place(id=f"prng:{p.prng_id}", name=p.name, type="miejscowosc", type_label=p.kind or "miejscowość",
                 gmina=p.gmina, powiat=p.powiat, wojewodztwo=p.wojewodztwo, lon=p.lon, lat=p.lat,
                 bbox=point_bbox(p.lon, p.lat, town), bbox_approx=True, source=prng.SOURCE)


def _from_osm(p: nominatim.OsmPlace) -> Place:
    return Place(id=f"osm:{p.osm_id}", name=p.name, type=p.type, type_label=p.type_label, gmina=p.gmina,
                 powiat=p.powiat, wojewodztwo=p.wojewodztwo, lon=p.lon, lat=p.lat,
                 bbox=p.bbox or point_bbox(p.lon, p.lat, p.type_label == "miasto"), bbox_approx=p.bbox is None,
                 source=nominatim.SOURCE)


def _rank(p: Place, want: str) -> tuple:
    exact = fold(p.name) != want
    town = p.type_label != "miasto"
    return (exact, town, fold(p.wojewodztwo), fold(p.powiat), fold(p.gmina), p.source)


def _dedupe(places: list[Place]) -> list[Place]:
    seen: set[tuple] = set()
    out = []
    for p in places:  # kolejność źródeł = priorytet (słownik, PRNG, OSM)
        key = (fold(p.name), fold(p.gmina), fold(p.powiat), p.type)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


async def _osm(name: str, hint: list[str], notices: list[str]) -> list[Place]:
    try:
        return [p for p in (_from_osm(r) for r in await nominatim.search(name)) if _matches_hint(p, hint)]
    except SourceError as exc:
        notices.append(f"{exc.source}: {exc.message}")
        return []


async def _find_one(name: str, hint: list[str], osm: bool = True) -> PlacesResult:
    """PRNG; rezerwa Nominatim (gdy `osm`), jeśli PRNG nic nie zwrócił albo nie działa; słownik demo na końcu
    (przy powtórzeniu wygrywa źródło zewnętrzne, bo jest aktualne; offline – tylko słownik)."""
    want = fold(name)
    notices: list[str] = []
    found: list[Place] = []
    truncated = False
    attribution = None
    if not settings.demo_offline:
        prng_found = False
        try:
            rows, truncated = await prng.search(name, hint)
            found += [p for p in (_from_prng(r) for r in rows) if _matches_hint(p, hint)]
            prng_found = bool(rows)
        except SourceError as exc:
            notices.append(f"{exc.source}: {exc.message}")
        if not prng_found and osm:  # PRNG nie zna nazwy albo nie działa – rezerwa
            extra = await _osm(name, hint, notices)
            if extra:
                found += extra
                attribution = nominatim.ATTRIBUTION
    found += [p for p in _local() if fold(p.name).startswith(want) and _matches_hint(p, hint)]
    found = _dedupe(found)
    found.sort(key=lambda p: _rank(p, want))
    return PlacesResult(found, truncated, notices, attribution)


async def find(name: str, area_hint: list[str] | None = None) -> PlacesResult:
    """Miejscowości o nazwie zaczynającej się od `name` (+ filtr gmina / powiat / województwo z `area_hint`).
    Gdy dla całej frazy brak wyników, a fraza ma kilka słów („Nowa Wieś Busko”), próbuje „nazwa + ostatnie słowo jako
    gmina” (jedna próba). Nominatim – dopiero na końcu (limit czasu jednego wyszukiwania)."""
    hint = list(area_hint or [])
    words = name.split()
    multi = len(words) > 1 and not hint
    res = await _find_one(name, hint, osm=not multi)
    if res.places or not multi:
        return res
    sub = await _find_one(" ".join(words[:-1]), [words[-1]], osm=False)
    if sub.places:
        return PlacesResult(sub.places, sub.truncated, [*res.notices, *sub.notices], sub.attribution)
    extra = await _osm(name, hint, res.notices) if not settings.demo_offline else []
    return PlacesResult(extra, False, [*res.notices, *sub.notices], nominatim.ATTRIBUTION if extra else None)


def clear_cache() -> None:
    _local.cache_clear()
    prng.clear_cache()
    nominatim.clear_cache()
