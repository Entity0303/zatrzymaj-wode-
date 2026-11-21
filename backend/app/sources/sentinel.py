"""Sentinel-2 L2A – STAC Earth Search (Element 84, AWS) + odczyt okna działki z plików COG (A11, D86).

Port prototypu osoby C (research/satellite/sentinel.py, bez merge c/research), przepisany na `core/http.request`
(async, bez przekierowań – treści 3xx nie czytamy, limit rozmiaru) i pyproj zamiast własnych wzorów UTM:
- STAC: https://earth-search.aws.element84.com/v1/search, kolekcja `sentinel-2-l2a`, assety red (B04, 10 m),
  nir (B08, 10 m), swir16 (B11, 20 m), scl (Scene Classification Layer, 20 m); georeferencja z `proj:transform`,
  skala / offset odbicia z `raster:bands` (0,0001 / −0,1; 0 = brak danych),
- COG: nagłówek (pierwsze 64 kB, w razie potrzeby więcej) czyta tifffile (BSD-3) z rzadkiego bufora; potem TYLKO
  kafle (512 × 512 px) przecinające okno działki – każdy kafel jednym zapytaniem HTTP Range,
- najpierw SCL (kafel ~30 kB) → udział ważnych pikseli w obrysie; pasma (kafel 10 m ~0,3–1,4 MB) tylko dla scen,
  które przeszły maskę.
SCL (ESA): 0 brak, 1 nasycone, 2 cień terenu, 3 cień chmur, 4 roślinność, 5 gleba odkryta, 6 woda,
7 niesklasyfikowane, 8–9 chmury, 10 cirrus, 11 śnieg. Ważne do NDVI / NDMI: 4 i 5.
"""

from __future__ import annotations

import asyncio
import io
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import httpx
import numpy as np
import tifffile

from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, request

SOURCE = "Sentinel-2 L2A (Earth Search)"
SOURCE_SHORT = "Sentinel-2 L2A"
SOURCE_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
ASSETS = ("red", "nir", "swir16", "scl")
SCL_VALID = (4, 5)          # roślinność, gleba odkryta
SCL_CLOUD = (3, 8, 9, 10)   # cień chmur, chmury, cirrus
SCL_SNOW = (11,)
HEADER_BYTES = 65_536


@dataclass
class Stats:
    """Licznik pobrania (budżet trybu na żywo: ok. 15 s i 10 MB na działkę)."""

    bytes: int = 0
    requests: int = 0
    started: float = field(default_factory=time.monotonic)

    @property
    def mb(self) -> float:
        return self.bytes / 1e6

    @property
    def seconds(self) -> float:
        return time.monotonic() - self.started


@dataclass
class Asset:
    href: str
    transform: list[float]   # [res, 0, x0, 0, −res, y0] (CRS sceny)
    shape: list[int]
    scale: float
    offset: float


@dataclass
class Scene:
    id: str
    date: date
    cloud: float             # eo:cloud_cover całej sceny, %
    epsg: int
    assets: dict[str, Asset]


# ── STAC ────────────────────────────────────────────────────────────────────────────────────


def scene_from_feature(f: dict) -> Scene:
    p = f["properties"]
    epsg = p.get("proj:epsg") or int(str(p.get("proj:code", "EPSG:0")).split(":")[1])
    assets = {}
    for k in ASSETS:
        a = f["assets"][k]
        rb = (a.get("raster:bands") or [{}])[0]
        assets[k] = Asset(a["href"], list(a["proj:transform"]), list(a["proj:shape"]), float(rb.get("scale", 1.0)),
                          float(rb.get("offset", 0.0)))
    return Scene(f["id"], datetime.fromisoformat(p["datetime"].replace("Z", "+00:00")).date(),
                 float(p.get("eo:cloud_cover") or 0.0), int(epsg), assets)


def unique_by_date(scenes: list[Scene]) -> list[Scene]:
    """Jedna scena na datę (dwa kafle MGRS tego samego przelotu) – mniej chmur wygrywa."""
    by: dict[date, Scene] = {}
    for s in scenes:
        if s.date not in by or s.cloud < by[s.date].cloud:
            by[s.date] = s
    return sorted(by.values(), key=lambda s: s.date, reverse=True)


async def search(bbox: tuple[float, float, float, float], start: date, end: date, stats: Stats,
                 max_cloud: float = 80.0, limit: int = 100) -> list[Scene]:
    """Sceny przecinające bbox [lon_min, lat_min, lon_max, lat_max] w okresie start–end (najmniej chmur najpierw)."""
    payload = {"collections": [COLLECTION], "bbox": list(bbox),
               "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
               "query": {"eo:cloud_cover": {"lt": max_cloud}}, "limit": limit,
               "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
               "fields": {"include": ["id", "properties.datetime", "properties.eo:cloud_cover", "properties.proj:epsg",
                                      "properties.proj:code"] + [f"assets.{a}" for a in ASSETS]}}
    try:
        resp = await request("POST", settings.sentinel_stac_url, source=SOURCE, timeout_s=settings.sentinel_timeout_s,
                             content=json.dumps(payload).encode(), headers={"Content-Type": "application/json"},
                             max_bytes=10_000_000)
    except RedirectBlocked as exc:
        raise SourceError(SOURCE, exc.message) from exc
    except httpx.TimeoutException as exc:
        raise SourceError(SOURCE, "katalog scen (STAC) nie odpowiada") from exc
    except httpx.TransportError as exc:
        raise SourceError(SOURCE, f"brak połączenia z katalogiem scen ({exc.__class__.__name__})") from exc
    stats.bytes += len(resp.content)
    stats.requests += 1
    if resp.status_code != 200:
        raise SourceError(SOURCE, f"katalog scen zwrócił błąd HTTP {resp.status_code}")
    out = []
    for f in resp.json().get("features", []):
        try:
            out.append(scene_from_feature(f))
        except (KeyError, ValueError, IndexError, TypeError):
            continue  # scena bez potrzebnych assetów – pomijamy
    return unique_by_date(out)


# ── COG: nagłówek z rzadkiego bufora, kafle przez Range ─────────────────────────────────────


class NeedBytes(BaseException):
    """Brak fragmentu pliku w buforze (BaseException – tifffile nie połknie go jako zwykłego błędu)."""

    def __init__(self, offset: int, length: int):
        super().__init__(offset, length)
        self.offset, self.length = offset, length


class SparseFile(io.RawIOBase):
    """Plik złożony z pobranych fragmentów; odczyt brakującego zakresu → NeedBytes (pobierzemy i spróbujemy znowu)."""

    def __init__(self, size: int):
        self.size, self.pos = size, 0
        self.parts: list[tuple[int, bytes]] = []

    def add(self, offset: int, data: bytes) -> None:
        self.parts.append((offset, data))

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n == 0:
            return b""
        for off, data in self.parts:
            if off <= self.pos and self.pos + n <= off + len(data):
                out = data[self.pos - off: self.pos - off + n]
                self.pos += n
                return out
        raise NeedBytes(self.pos, n)

    def readinto(self, b):
        d = self.read(len(b))
        b[: len(d)] = d
        return len(d)


async def _range(url: str, a: int, b: int, stats: Stats) -> tuple[bytes, int | None]:
    """Bajty [a, b] (włącznie) – zwraca (dane, rozmiar pliku z Content-Range). Jedna ponowna próba po przerwanym
    odczycie / błędzie połączenia (S3 bywa chwilowo wolne)."""
    try:
        return await _range_once(url, a, b, stats)
    except SourceError as exc:
        if isinstance(exc, RedirectBlocked) or "HTTP" in exc.message:
            raise
        return await _range_once(url, a, b, stats)


async def _range_once(url: str, a: int, b: int, stats: Stats) -> tuple[bytes, int | None]:
    try:
        resp = await request("GET", url, source=SOURCE, timeout_s=settings.sentinel_timeout_s,
                             headers={"Range": f"bytes={a}-{b}"}, max_bytes=b - a + 1 + 1024)
    except RedirectBlocked as exc:
        raise SourceError(SOURCE, exc.message) from exc
    except httpx.TimeoutException as exc:
        raise SourceError(SOURCE, "plik sceny nie odpowiada") from exc
    except httpx.TransportError as exc:
        raise SourceError(SOURCE, f"brak połączenia z plikiem sceny ({exc.__class__.__name__})") from exc
    stats.bytes += len(resp.content)
    stats.requests += 1
    if resp.status_code not in (200, 206):
        raise SourceError(SOURCE, f"plik sceny zwrócił błąd HTTP {resp.status_code}")
    cr = resp.headers.get("content-range")
    size = int(cr.split("/")[1]) if cr and "/" in cr and cr.split("/")[1].isdigit() else None
    return resp.content, size


@dataclass
class CogMeta:
    tif: tifffile.TiffFile
    page: object
    tile_w: int
    tile_h: int
    width: int
    height: int


_META: OrderedDict[str, CogMeta] = OrderedDict()  # nagłówki ostatnich plików (szereg czyta te same kafle MGRS)
_META_MAX = 64


async def cog_meta(url: str, stats: Stats) -> CogMeta:
    if url in _META:
        _META.move_to_end(url)
        return _META[url]
    data, size = await _range(url, 0, HEADER_BYTES - 1, stats)
    sf = SparseFile(size or len(data))
    sf.add(0, data)
    for _attempt in range(6):
        try:
            tif = tifffile.TiffFile(sf)
            page = tif.pages[0]
            _ = page.dataoffsets, page.databytecounts  # wymusza odczyt tablic przesunięć kafli
            meta = CogMeta(tif, page, int(page.tilewidth), int(page.tilelength), int(page.shape[1]), int(page.shape[0]))
            break
        except NeedBytes as need:  # nagłówek dłuższy niż 64 kB – dociągamy brakujący fragment
            a = max(0, need.offset)
            b = min(sf.size - 1, max(need.offset + need.length, a + HEADER_BYTES) - 1)
            more, _ = await _range(url, a, b, stats)
            sf.add(a, more)
            sf.seek(0)
    else:
        raise SourceError(SOURCE, "nie udało się odczytać nagłówka pliku sceny")
    if not meta.tile_w or not meta.tile_h:
        raise SourceError(SOURCE, "plik sceny nie jest kafelkowanym COG")
    _META[url] = meta
    while len(_META) > _META_MAX:
        _META.popitem(last=False)
    return meta


def decode_tile(meta: CogMeta, index: int, data: bytes) -> np.ndarray:
    tile, _idx, _shape = meta.page.decode(data, index)
    return np.asarray(tile).reshape(meta.tile_h, meta.tile_w)


async def read_window(url: str, rows: tuple[int, int], cols: tuple[int, int], stats: Stats) -> np.ndarray:
    """Okno (rows, cols) pełnej rozdzielczości; poza obrazem – 0 (brak danych). Kafle pobierane równolegle."""
    meta = await cog_meta(url, stats)
    r0, r1 = max(0, rows[0]), min(meta.height, rows[1])
    c0, c1 = max(0, cols[0]), min(meta.width, cols[1])
    out = np.zeros((rows[1] - rows[0], cols[1] - cols[0]), dtype=meta.page.dtype)
    if r0 >= r1 or c0 >= c1:
        return out
    tw, tl = meta.tile_w, meta.tile_h
    ntx = (meta.width + tw - 1) // tw
    jobs = [(ty, tx) for ty in range(r0 // tl, (r1 - 1) // tl + 1) for tx in range(c0 // tw, (c1 - 1) // tw + 1)]

    async def one(ty: int, tx: int):
        idx = ty * ntx + tx
        off, cnt = int(meta.page.dataoffsets[idx]), int(meta.page.databytecounts[idx])
        if cnt == 0:
            return ty, tx, None
        data, _ = await _range(url, off, off + cnt - 1, stats)
        return ty, tx, decode_tile(meta, idx, data)

    for ty, tx, tile in await asyncio.gather(*(one(ty, tx) for ty, tx in jobs)):
        if tile is None:
            continue
        ya, xa = ty * tl, tx * tw
        rr0, rr1 = max(r0, ya), min(r1, ya + tl)
        cc0, cc1 = max(c0, xa), min(c1, xa + tw)
        out[rr0 - rows[0]: rr1 - rows[0], cc0 - cols[0]: cc1 - cols[0]] = tile[rr0 - ya: rr1 - ya, cc0 - xa: cc1 - xa]
    return out


# ── wskaźniki ───────────────────────────────────────────────────────────────────────────────


def pixel_window(transform: list[float], bounds: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """(row0, row1, col0, col1) – piksele pokrywające bounds (xmin, ymin, xmax, ymax) w CRS sceny."""
    res, _, x0, _, neg_res, y0 = transform[:6]
    xmin, ymin, xmax, ymax = bounds
    c0 = int(np.floor((xmin - x0) / res))
    c1 = int(np.ceil((xmax - x0) / res))
    r0 = int(np.floor((y0 - ymax) / -neg_res))
    r1 = int(np.ceil((y0 - ymin) / -neg_res))
    return r0, r1, c0, c1


def upsample2(a: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """20 m → 10 m (każdy piksel 20 m = 2 × 2 piksele 10 m), wycięte do kształtu okna 10 m."""
    return np.repeat(np.repeat(a, 2, axis=0), 2, axis=1)[: shape[0], : shape[1]]


def reflectance(dn: np.ndarray, scale: float, offset: float) -> np.ndarray:
    r = dn.astype(float) * scale + offset
    r[dn == 0] = np.nan  # 0 = brak danych
    return r


def scl_shares(scl: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    """Udziały w obrysie: ważne (roślinność, gleba), chmury z cieniem, śnieg – w %."""
    n = max(int(mask.sum()), 1)
    return {"valid_pct": 100.0 * float((np.isin(scl, SCL_VALID) & mask).sum()) / n,
            "cloud_pct": 100.0 * float((np.isin(scl, SCL_CLOUD) & mask).sum()) / n,
            "snow_pct": 100.0 * float((np.isin(scl, SCL_SNOW) & mask).sum()) / n}


def indices(red: np.ndarray, nir: np.ndarray, swir: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """NDVI = (B08 − B04)/(B08 + B04), NDMI = (B08 − B11)/(B08 + B11) na odbiciu (po skali i offsecie).
    Odbicie ≤ 0 (offset −0,1 przy bardzo ciemnych pikselach, np. niskie słońce zimą) = brak – inaczej NDVI wychodzi 1,0."""
    red = np.where(red > 0, red, np.nan)
    nir = np.where(nir > 0, nir, np.nan)
    swir = np.full_like(nir, np.nan) if swir is None else np.where(swir > 0, swir, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
        ndmi = (nir - swir) / (nir + swir)
    ndvi[~np.isfinite(ndvi)] = np.nan
    ndmi[~np.isfinite(ndmi)] = np.nan
    return np.clip(ndvi, -1, 1), np.clip(ndmi, -1, 1)


def median_in(a: np.ndarray, m: np.ndarray) -> float | None:
    v = a[m & np.isfinite(a)]
    return round(float(np.median(v)), 3) if v.size else None


def window_dates(on: date, days_back: int) -> tuple[date, date]:
    return on - timedelta(days=days_back), on


def clear_cache() -> None:
    _META.clear()
