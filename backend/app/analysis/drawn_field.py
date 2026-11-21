"""Własny obrys pola (A5c, D75) – opcja dodatkowa obok działki z ULDK.

Rolnik rysuje wielokąt na mapie (GeoJSON Polygon, WGS84, [lon, lat]). Walidacja: poprawny wielokąt, bez
samoprzecięć, powierzchnia 0,05–200 ha, w granicach Polski. Pole dostaje stabilny identyfikator z kształtu (ten sam
obrys = ten sam id → te same wyniki z cache), nazwę „Pole narysowane przez rolnika” i powierzchnię liczoną z kształtu
(EPSG:2180). Gmina / powiat / województwo – z działki ULDK w środku pola (gdy znana / ULDK odpowiada), potem z
odwrotnego geokodowania (Nominatim), na końcu najbliższy środek województwa (przybliżenie). Reszta analizy – jak dla działki.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Polygon
from shapely.validation import explain_validity

from app.analysis.approx_area import nearest_voivodeship
from app.core.config import settings
from app.core.geo import to_2180
from app.core.http import SourceError, in_poland
from app.sources import nominatim, uldk

NAME = "Pole narysowane przez rolnika"
ID_PREFIX = "narysowane"
MIN_HA = 0.05
MAX_HA = 200.0
MAX_VERTICES = 2000


class DrawnError(ValueError):
    """Błąd obrysu – komunikat po polsku, pokazywany rolnikowi (HTTP 422)."""


def _pl(x: float, nd: int) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def _ring(raw: Any, what: str) -> list[tuple[float, float]]:
    if not isinstance(raw, list) or len(raw) < 3:
        raise DrawnError(f"{what} ma za mało punktów – narysuj wielokąt o co najmniej 3 wierzchołkach.")
    pts: list[tuple[float, float]] = []
    for c in raw:
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            raise DrawnError("Obrys ma niepoprawne współrzędne – oczekiwano par [długość, szerokość].")
        try:
            lon, lat = float(c[0]), float(c[1])
        except (TypeError, ValueError) as exc:
            raise DrawnError("Obrys ma niepoprawne współrzędne – oczekiwano liczb.") from exc
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise DrawnError("Obrys ma niepoprawne współrzędne – oczekiwano skończonych liczb.")
        pts.append((lon, lat))
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 4:
        raise DrawnError(f"{what} ma za mało punktów – narysuj wielokąt o co najmniej 3 wierzchołkach.")
    return pts


def parse_polygon(geometry: dict | None) -> Polygon:
    """GeoJSON Polygon (albo Feature z Polygon) w WGS84 → poprawny `Polygon`. Błędy → DrawnError z czytelnym komunikatem."""
    if not isinstance(geometry, dict):
        raise DrawnError("Brak obrysu pola – narysuj wielokąt na mapie.")
    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry") or {}
    gtype = geometry.get("type")
    if gtype != "Polygon":
        raise DrawnError("Obrys musi być jednym wielokątem (GeoJSON Polygon)."
                         + (" Kilka oddzielnych pól policz osobno." if gtype == "MultiPolygon" else ""))
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or not rings:
        raise DrawnError("Obrys nie ma współrzędnych.")
    if sum(len(r) for r in rings if isinstance(r, list)) > MAX_VERTICES:
        raise DrawnError(f"Obrys ma za dużo punktów (maks. {MAX_VERTICES}) – uprość kształt.")
    shell = _ring(rings[0], "Obrys")
    holes = [_ring(r, "Otwór w obrysie") for r in rings[1:]]
    lons, lats = [p[0] for p in shell], [p[1] for p in shell]
    if not (in_poland(min(lons), min(lats)) and in_poland(max(lons), max(lats))):
        if all(14 <= la <= 24.2 for la in lats) and all(49 <= lo <= 55 for lo in lons):
            raise DrawnError("Współrzędne mają odwróconą kolejność – w GeoJSON najpierw długość (lon), potem szerokość (lat).")
        raise DrawnError("Obrys leży poza Polską – analiza działa tylko dla pól w Polsce.")
    poly = Polygon(shell, holes)
    if not poly.is_valid:
        why = explain_validity(poly)
        if "self-intersection" in why.lower() or "ring self-intersection" in why.lower():
            raise DrawnError("Obrys przecina sam siebie – popraw kształt tak, by linie się nie krzyżowały.")
        raise DrawnError("Obrys jest niepoprawny geometrycznie – narysuj go ponownie.")
    ha = area_ha(poly)
    if ha < MIN_HA:
        raise DrawnError(f"Pole jest za małe ({_pl(ha, 3)} ha) – najmniejsze obsługiwane to {_pl(MIN_HA, 2)} ha (ok. 22 × 22 m).")
    if ha > MAX_HA:
        raise DrawnError(f"Pole jest za duże ({_pl(ha, 0)} ha) – największe obsługiwane to {MAX_HA:.0f} ha. "
                         "Podziel je na mniejsze części.")
    return poly


def area_ha(poly_4326: Polygon) -> float:
    return to_2180(poly_4326).area / 10_000


def drawn_id(poly_4326: Polygon) -> str:
    """Stabilny identyfikator z kształtu (współrzędne w EPSG:2180 zaokrąglone do 1 m)."""
    g = to_2180(poly_4326).normalize()
    coords = ";".join(f"{x:.0f},{y:.0f}" for x, y in g.exterior.coords)
    return f"{ID_PREFIX}_{hashlib.sha1(coords.encode()).hexdigest()[:10]}"


@dataclass
class Admin:
    wojewodztwo: str
    powiat: str
    gmina: str
    obreb: str
    teryt: str | None
    note: str
    url: str


async def admin_for(lon: float, lat: float) -> Admin:
    """Gmina / powiat / województwo środka pola: działka ULDK (znana albo z ULDK) → Nominatim → najbliższy środek
    województwa. Każdy krok ma krótki limit czasu – analiza nie czeka na geokoder."""
    if not settings.demo_offline:
        try:
            p = await asyncio.wait_for(uldk.by_point(lon, lat), timeout=min(6.0, settings.uldk_timeout_s))
            return Admin(p.voivodeship, p.county, p.commune, p.region, p.teryt_commune,
                         "Gmina, powiat i województwo z działki ewidencyjnej w środku pola (ULDK GUGiK).", uldk.SOURCE_URL)
        except (SourceError, asyncio.TimeoutError):
            pass
    else:
        if (p := uldk.known_at(lon, lat)) is not None:
            return Admin(p.voivodeship, p.county, p.commune, p.region, p.teryt_commune,
                         "Gmina, powiat i województwo z zapisanej działki w środku pola (ULDK GUGiK).", uldk.SOURCE_URL)
    try:
        osm = await asyncio.wait_for(nominatim.reverse(lon, lat), timeout=settings.nominatim_timeout_s + 2)
        if osm is not None:
            return Admin(osm.wojewodztwo, f"powiat {osm.powiat}" if osm.powiat else "nieznany", osm.gmina or "nieznana",
                         osm.miejscowosc or "—", None,
                         f"Gmina, powiat i województwo z geokodera ({nominatim.ATTRIBUTION}).", nominatim.SOURCE_URL)
    except (SourceError, asyncio.TimeoutError):
        pass
    return Admin(nearest_voivodeship(lon, lat), "nieznany", "nieznana", "—", None,
                 "Województwo przybliżone (najbliższy środek województwa) – gmina i powiat nieznane.", uldk.SOURCE_URL)


async def build_parcel(poly_4326: Polygon) -> uldk.Parcel:
    """Pole narysowane jako `uldk.Parcel` (source = drawn) – dalej analiza traktuje je jak działkę."""
    rp = poly_4326.representative_point()
    adm = await admin_for(rp.x, rp.y)
    return uldk.Parcel(id=drawn_id(poly_4326), voivodeship=adm.wojewodztwo, county=adm.powiat, commune=adm.gmina,
                       region=adm.obreb, number="—", geom_2180=to_2180(poly_4326), source="drawn", name=NAME,
                       teryt=adm.teryt, admin_note=adm.note, admin_url=adm.url)


async def resolve(geometry: dict | None) -> uldk.Parcel:
    return await build_parcel(parse_polygon(geometry))
