"""IUNG-PIB — kategorie podatności gleb na suszę (System Monitoringu Suszy Rolniczej, D3).

Raster Susza:katgl_landuse2024 (siatka 5 m, EPSG:2180) na GeoServerze IUNG. Dwie metody (D19):
1. GŁÓWNA – WCS 2.0.1 GetCoverage, FORMAT=text/plain: surowe kody wszystkich komórek w bbox
   działki (~0,3 s), zliczamy komórki, których środek leży w obrysie. Osie WCS w konwencji
   polskiej: x = PÓŁNOC, y = WSCHÓD (SUBSET=x(N…)&SUBSET=y(E…)); wiersz 0 = północ.
2. ZAPASOWA – WMS GetFeatureInfo (WMS 1.3.0, CRS EPSG:4326 => BBOX lat,lon, INFO_FORMAT
   application/json, properties.GRAY_INDEX) w siatce do 16 punktów w obrysie, równolegle.
Kody i zakresy WOD wg https://susza.iung.pulawy.pl/kategorie/ ; legenda (kolory) –
GetLegendGraphic FORMAT=application/json.
"""

import asyncio
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry.base import BaseGeometry

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.geo import sample_points, to_wgs84
from app.core.http import SourceError, get_with_retry

SOURCE = "IUNG-PIB SMSR (kategorie glebowe)"
SOURCE_SHORT = "IUNG-PIB"
SOURCE_URL = "https://susza.iung.pulawy.pl/kategorie/"
RESOLUTION = "siatka 5 m"

# kod rastra -> (opis, WOD min [mm], WOD max [mm], czy grunt rolny mineralny)
CODES: dict[int, tuple[str, float | None, float | None, bool]] = {
    1: ("Kategoria I – bardzo podatna na suszę", None, 127.5, True),
    2: ("Kategoria II – podatna na suszę", 127.5, 169.9, True),
    3: ("Kategoria III – średnio podatna na suszę", 170.0, 202.5, True),
    4: ("Kategoria IV – mało podatna na suszę", 202.5, None, True),
    5: ("Gleby organiczne i pochodzenia organicznego", None, None, False),
    11: ("Lasy, zadrzewienia", None, None, False),
    12: ("Wody", None, None, False),
    13: ("Tereny zabudowane", None, None, False),
    14: ("Tereny komunikacyjne, nieużytki", None, None, False),
    19: ("Tereny niesklasyfikowane", None, None, False),
    99: ("Tereny niesklasyfikowane", None, None, False),
}
NODATA = {0, 255}
MINERAL = {1, 2, 3, 4}
NOT_AGRICULTURAL = {5, 11, 12, 13, 14}  # gdy > 50% działki – ocena suszy rolniczej nie ma zastosowania

# Reprezentatywna WOD kategorii (D20): środek przedziału; dla otwartych kategorii I i IV –
# granica ± połowa szerokości sąsiedniej kategorii (II: 42,4 mm, III: 32,5 mm).
REPRESENTATIVE_WOD_MM = {1: 106.3, 2: 148.7, 3: 186.2, 4: 218.8}

_cache: TTLCache["SoilResult"] = TTLCache(ttl_s=None, max_items=512, name="IUNG-PIB")


@dataclass
class SoilSample:
    lon: float
    lat: float
    code: int | None


@dataclass
class SoilResult:
    """Liczba komórek (lub punktów) wg kodu IUNG w obrysie działki."""

    counts: dict[int, int]
    method: str  # "wcs" | "punkty"
    nodata: int = 0  # komórki/punkty bez danych (0, 255)
    cell_size_m: float | None = None
    samples: list[SoilSample] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def shares(self) -> dict[int, float]:
        """Udziały kodów wśród komórek z danymi, od największego."""
        if not self.total:
            return {}
        return {c: round(n / self.total, 3) for c, n in Counter(self.counts).most_common()}

    @property
    def dominant(self) -> int | None:
        return next(iter(self.shares), None)

    @property
    def nodata_share(self) -> float:
        n = self.total + self.nodata
        return round(self.nodata / n, 3) if n else 1.0

    @property
    def agricultural_share(self) -> float:
        """Udział gruntów rolnych mineralnych (kody 1–4)."""
        return round(sum(v for c, v in self.shares.items() if c in MINERAL), 3)

    @property
    def wod_mm(self) -> float | None:
        """Średnia ważona WOD dla mineralnej części działki."""
        agri = {c: n for c, n in self.counts.items() if c in MINERAL}
        total = sum(agri.values())
        if not total:
            return None
        return round(sum(REPRESENTATIVE_WOD_MM[c] * n for c, n in agri.items()) / total, 1)

    @property
    def dominant_mineral(self) -> int | None:
        agri = {c: n for c, n in self.counts.items() if c in MINERAL}
        return max(agri, key=agri.get) if agri else None

    @property
    def not_agricultural_code(self) -> int | None:
        """Kod dominujący, jeśli to las/woda/zabudowa/drogi/gleby organiczne i zajmuje > 50%."""
        shares = self.shares
        non_agri = sum(v for c, v in shares.items() if c in NOT_AGRICULTURAL)
        if non_agri <= 0.5:
            return None
        return max((c for c in shares if c in NOT_AGRICULTURAL), key=lambda c: shares[c])


# ── 1. WCS: surowe kody komórek ─────────────────────────────────────────────────────────────

_BOUNDS = re.compile(r"Grid bounds:\s*GeneralBounds\[\(([-\d.]+),\s*([-\d.]+)\),\s*\(([-\d.]+),\s*([-\d.]+)\)\]")
_ROW = re.compile(r"^\s*\d+(\s+\d+)*\s*$")


def parse_wcs_text(text: str) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Odpowiedź WCS text/plain -> (siatka kodów [wiersz 0 = północ], (E_min, N_min, E_max, N_max))."""
    m = _BOUNDS.search(text)
    if not m:
        raise SourceError(SOURCE, "nieoczekiwany format odpowiedzi WCS (brak granic siatki)")
    bounds = tuple(float(v) for v in m.groups())
    body = text.split("Band 0:", 1)[-1]
    rows = [ln.split() for ln in body.splitlines() if _ROW.match(ln)]
    if not rows or len({len(r) for r in rows}) != 1:
        raise SourceError(SOURCE, "nieoczekiwany format odpowiedzi WCS (siatka)")
    return np.array(rows, dtype=np.int32), bounds  # type: ignore[return-value]


def count_cells(geom_2180: BaseGeometry, grid: np.ndarray, bounds: tuple[float, float, float, float]) -> SoilResult:
    """Zlicza kody komórek, których środek leży w obrysie (wektorowo, shapely.contains_xy)."""
    e0, n0, e1, n1 = bounds
    rows, cols = grid.shape
    dx, dy = (e1 - e0) / cols, (n1 - n0) / rows
    ee = e0 + (np.arange(cols) + 0.5) * dx
    nn = n1 - (np.arange(rows) + 0.5) * dy
    E, N = np.meshgrid(ee, nn)
    inside = shapely.contains_xy(geom_2180, E, N)
    if not inside.any():  # działka mniejsza niż komórka – komórka z punktem wewnątrz obrysu
        pt = geom_2180.representative_point()
        c = min(cols - 1, max(0, int((pt.x - e0) / dx)))
        r = min(rows - 1, max(0, int((n1 - pt.y) / dy)))
        inside = np.zeros_like(inside)
        inside[r, c] = True
    codes, n = np.unique(grid[inside], return_counts=True)
    counts = {int(c): int(k) for c, k in zip(codes, n) if int(c) not in NODATA}
    nodata = int(sum(k for c, k in zip(codes, n) if int(c) in NODATA))
    return SoilResult(counts=counts, method="wcs", nodata=nodata, cell_size_m=round((dx + dy) / 2, 2))


async def fetch_wcs(geom_2180: BaseGeometry) -> SoilResult:
    e0, n0, e1, n1 = geom_2180.bounds
    params: list[tuple[str, str]] = [
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", settings.iung_coverage_id),
        ("FORMAT", "text/plain"),
        ("SUBSET", f"x({n0:.1f},{n1:.1f})"),  # x = północ (konwencja PL-1992)
        ("SUBSET", f"y({e0:.1f},{e1:.1f})"),  # y = wschód
    ]
    cells = (e1 - e0) / 5 * (n1 - n0) / 5
    if cells > settings.iung_wcs_max_cells:
        params.append(("SCALEFACTOR", f"{(settings.iung_wcs_max_cells / cells) ** 0.5:.3f}"))
    resp = await get_with_retry(
        settings.iung_wcs_url,
        params,  # lista par – SUBSET występuje dwa razy
        source=SOURCE,
        timeout_s=settings.iung_timeout_s,
        retries=1,
    )
    if "ExceptionReport" in resp.text[:500]:
        raise SourceError(SOURCE, "usługa WCS zwróciła błąd")
    grid, bounds = parse_wcs_text(resp.text)
    return count_cells(geom_2180, grid, bounds)


# ── 2. Zapasowo: GetFeatureInfo w punktach ──────────────────────────────────────────────────


def parse_gfi(payload: dict) -> int | None:
    features = payload.get("features") or []
    if not features:
        return None
    value = features[0].get("properties", {}).get("GRAY_INDEX")
    if value is None:
        return None
    code = int(value)
    return None if code in NODATA else code


async def _code_at(lon: float, lat: float) -> int | None:
    d = 0.0005
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": settings.iung_soil_layer,
        "QUERY_LAYERS": settings.iung_soil_layer,
        "CRS": "EPSG:4326",  # WMS 1.3.0 + EPSG:4326 => kolejność osi: lat, lon
        "BBOX": f"{lat - d},{lon - d},{lat + d},{lon + d}",
        "WIDTH": "101",
        "HEIGHT": "101",
        "I": "50",
        "J": "50",
        "INFO_FORMAT": "application/json",
    }
    resp = await get_with_retry(settings.iung_wms_url, params, source=SOURCE, timeout_s=settings.iung_timeout_s, retries=1)
    try:
        return parse_gfi(resp.json())
    except ValueError as exc:
        raise SourceError(SOURCE, "nieoczekiwany format odpowiedzi GetFeatureInfo") from exc


async def fetch_points(geom_2180: BaseGeometry, n: int | None = None) -> SoilResult:
    pts = [to_wgs84(p) for p in sample_points(geom_2180, n or settings.soil_sample_points)]
    codes = await asyncio.gather(*(_code_at(p.x, p.y) for p in pts))
    samples = [SoilSample(p.x, p.y, c) for p, c in zip(pts, codes)]
    counts = Counter(c for c in codes if c is not None)
    return SoilResult(counts=dict(counts), method="punkty", nodata=sum(c is None for c in codes), samples=samples)


# ── wejście ─────────────────────────────────────────────────────────────────────────────────


def _key(geom_2180: BaseGeometry) -> str:
    return hashlib.sha1(shapely.to_wkt(geom_2180, rounding_precision=1).encode()).hexdigest()


async def soil_for_parcel(geom_2180: BaseGeometry) -> SoilResult:
    """WCS, a gdy zawiedzie – punkty GetFeatureInfo. Obie metody zawiodą -> SourceError."""
    return await cached_fetch(_cache, _key(geom_2180), SOURCE_SHORT, lambda: _download(geom_2180), timeout_s=14.0,
                              breaker_s=60)


async def _download(geom_2180: BaseGeometry) -> SoilResult:
    try:
        res = await fetch_wcs(geom_2180)
    except SourceError as wcs_err:
        try:
            res = await fetch_points(geom_2180)
        except SourceError as gfi_err:
            raise SourceError(SOURCE, f"WCS: {wcs_err.message}; GetFeatureInfo: {gfi_err.message}") from gfi_err
        if not res.total:
            raise SourceError(SOURCE, f"WCS: {wcs_err.message}; GetFeatureInfo: brak danych w punktach") from wcs_err
    return res


def clear_cache() -> None:
    _cache.clear()
