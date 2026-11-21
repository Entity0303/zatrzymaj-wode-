"""Pomocnicze funkcje geometryczne. Układ roboczy: PL-1992 (EPSG:2180), metry."""

from functools import lru_cache

import numpy as np
from pyproj import Transformer
import shapely
from shapely import wkt
from shapely.geometry import Point, Polygon, MultiPolygon, mapping
from shapely.geometry.base import BaseGeometry


@lru_cache
def _tr(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def _reproject(geom: BaseGeometry, src: str, dst: str) -> BaseGeometry:
    tr = _tr(src, dst)
    return shapely.transform(geom, lambda x, y: tr.transform(x, y), interleaved=False)


def to_wgs84(geom_2180: BaseGeometry) -> BaseGeometry:
    """EPSG:2180 (wschód, północ) -> EPSG:4326 (lon, lat)."""
    return _reproject(geom_2180, "EPSG:2180", "EPSG:4326")


def to_2180(geom_4326: BaseGeometry) -> BaseGeometry:
    """EPSG:4326 (lon, lat) -> EPSG:2180 (wschód, północ)."""
    return _reproject(geom_4326, "EPSG:4326", "EPSG:2180")


def lonlat_to_2180(lon: float, lat: float) -> tuple[float, float]:
    return _tr("EPSG:4326", "EPSG:2180").transform(lon, lat)


def parse_wkt(text: str) -> BaseGeometry:
    """Parsuje WKT/EWKT (ULDK zwraca np. 'SRID=2180;POLYGON((...))')."""
    if ";" in text:
        text = text.split(";", 1)[1]
    geom = wkt.loads(text)
    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise ValueError(f"Oczekiwano poligonu, otrzymano {geom.geom_type}")
    return geom


def sample_points(geom_2180: BaseGeometry, n: int) -> list[Point]:
    """Równomiernie rozłożone punkty wewnątrz poligonu (zawsze co najmniej 1)."""
    minx, miny, maxx, maxy = geom_2180.bounds
    pts: list[Point] = []
    side = max(2, int(np.ceil(np.sqrt(n * 2))))
    for _ in range(4):
        xs = np.linspace(minx, maxx, side + 2)[1:-1]
        ys = np.linspace(miny, maxy, side + 2)[1:-1]
        pts = [Point(x, y) for x in xs for y in ys if geom_2180.contains(Point(x, y))]
        if len(pts) >= n:
            break
        side *= 2
    if len(pts) > n:
        idx = np.linspace(0, len(pts) - 1, n).round().astype(int)
        pts = [pts[i] for i in idx]
    if not pts:
        pts = [geom_2180.representative_point()]
    return pts


def geojson(geom_4326: BaseGeometry) -> dict:
    return mapping(geom_4326)
