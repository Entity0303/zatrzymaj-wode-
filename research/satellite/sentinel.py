"""C9 – Sentinel-2 L2A dla działki: NDVI (kondycja roślin) i NDMI (wilgotność roślin), research.

Źródło: Earth Search (Element 84, AWS) STAC https://earth-search.aws.element84.com/v1, kolekcja
`sentinel-2-l2a`, pliki COG w publicznym S3 (`sentinel-cogs`). Bez konta i bez klucza.

Zasady:
- czytamy TYLKO kafle COG, które przecinają okno działki (zapytania HTTP Range), nigdy całych scen,
- nigdy nie podążamy za przekierowaniami (odpowiedź 3xx = błąd, treść nieczytana),
- najpierw maska SCL (kafel ~30 kB), pasma (kafel 10 m ~1,4 MB) tylko dla czystych scen,
- georeferencja z metadanych STAC (`proj:transform`, `proj:epsg`), skala/offset z `raster:bands`.

Funkcje (do przeniesienia 1:1 do backendu):
  search_scenes(bbox, start, end, max_cloud)        → lista scen (jedna na datę)
  read_window(href, transform, bounds, res, opener)  → tablica okna (uint16/uint8) + statystyki bajtów
  indices(red, nir, swir, scl, scale, offset)        → ndvi, ndmi, maska ważnych pikseli
  parcel_summary(geom, ...)                          → ostatnia czysta scena, mediany, zdanie
  timeseries(geom, start, end, ...)                  → szereg (data, ndvi, ndmi, % chmur)

Licencje: numpy (BSD-3), tifffile (BSD-3), biblioteka standardowa Pythona (PSF).
"""

from __future__ import annotations

import io
import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import tifffile

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
UA = "zatrzymaj-wode-research/0.1"

# SCL (Scene Classification Layer, ESA): 0 brak danych, 1 piksele nasycone, 2 ciemne/cień terenu,
# 3 cień chmur, 4 roślinność, 5 gleba odkryta, 6 woda, 7 niesklasyfikowane, 8 chmury średnie,
# 9 chmury wysokie, 10 cirrus, 11 śnieg/lód
SCL_VALID = (4, 5)            # do NDVI/NDMI tylko roślinność i odkryta gleba
SCL_CLOUD = (3, 8, 9, 10)     # cień chmur + chmury + cirrus
SCL_SNOW = (11,)
CLEAR_MAX_CLOUD = 10.0        # scena „czysta” dla działki: chmury + śnieg <= 10 % obrysu
USABLE_MIN_VALID = 50.0       # minimum ważnych pikseli, żeby liczyć mediany (%)

# Offset −0,1 z metadanych STAC (`raster:bands`) NIE jest stosowany: sprawdzone na żywo 2026-11-22
# (S2C_34UED_20260806, działka 201305) – DN czerwieni nad roślinnością: mediana 356, czyli pliki COG są już
# zharmonizowane (bez +1000). Z offsetem odbicie czerwieni wychodzi ujemne i NDVI > 1.
APPLY_STAC_OFFSET = False

# progi zdań (SZACUNEK – do kalibracji): różnica median NDVI / NDMI względem tego samego okresu rok wcześniej
DNDVI = 0.10
DNDMI = 0.08


# ---------------------------------------------------------------------------------- HTTP bez przekierowań

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


@dataclass
class Stats:
    bytes: int = 0
    requests: int = 0
    seconds: float = 0.0

    def add(self, other: "Stats") -> None:
        self.bytes += other.bytes
        self.requests += other.requests
        self.seconds += other.seconds


class RangeFile(io.RawIOBase):
    """Plik zdalny czytany zakresami HTTP (Range), z buforem bloków. Liczy bajty i zapytania."""

    def __init__(self, url: str, block: int = 65536, timeout: float = 30.0, opener=OPENER):
        self.url, self.block, self.timeout, self.opener = url, block, timeout, opener
        self.pos, self.size = 0, None
        self.cache: dict[int, bytes] = {}
        self.stats = Stats()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self._size() + off
        return self.pos

    def get_range(self, a: int, b: int) -> bytes:
        t0 = time.monotonic()
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={a}-{b}", "User-Agent": UA})
                with self.opener.open(req, timeout=self.timeout) as r:
                    data = r.read(b - a + 1 + 1)
                    cr = r.headers.get("Content-Range")
                    if cr and self.size is None:
                        self.size = int(cr.split("/")[1])
                self.stats.bytes += len(data)
                self.stats.requests += 1
                self.stats.seconds += time.monotonic() - t0
                return data
            except urllib.error.HTTPError as e:
                e.close()  # 3xx/4xx – treści nie czytamy
                raise RuntimeError(f"HTTP {e.code}: {self.url}") from None
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(1 + attempt)
        raise RuntimeError(f"błąd odczytu {self.url}: {last}")

    def _size(self):
        if self.size is None:
            self.get_range(0, 0)
        return self.size

    def read(self, n=-1):
        if n is None or n < 0:
            n = self._size() - self.pos
        out, a, end = bytearray(), self.pos, self.pos + n
        while a < end:
            bi = a // self.block
            if bi not in self.cache:
                self.cache[bi] = self.get_range(bi * self.block, bi * self.block + self.block - 1)
            blk = self.cache[bi]
            off = a - bi * self.block
            take = min(end - a, len(blk) - off)
            if take <= 0:
                break
            out += blk[off:off + take]
            a += take
        self.pos = a
        return bytes(out)

    def read_exact(self, offset: int, count: int) -> bytes:
        """Jeden kafel = jedno zapytanie (bez buforowania bloków)."""
        return self.get_range(offset, offset + count - 1)

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


def http_json(url: str, payload: dict | None = None, timeout: float = 60.0) -> tuple[dict, float]:
    t0 = time.monotonic()
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    try:
        with OPENER.open(req, timeout=timeout) as r:
            body = r.read(50_000_000)
    except urllib.error.HTTPError as e:
        e.close()
        raise RuntimeError(f"HTTP {e.code}: {url}") from None
    return json.loads(body), time.monotonic() - t0


# ---------------------------------------------------------------------------------- odwzorowanie UTM

_A, _F = 6378137.0, 1 / 298.257223563  # WGS84
_N = _F / (2 - _F)
_AR = _A / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64)
_ALPHA = [_N / 2 - 2 / 3 * _N**2 + 5 / 16 * _N**3 + 41 / 180 * _N**4,
          13 / 48 * _N**2 - 3 / 5 * _N**3 + 557 / 1440 * _N**4,
          61 / 240 * _N**3 - 103 / 140 * _N**4,
          49561 / 161280 * _N**4]
_BETA = [_N / 2 - 2 / 3 * _N**2 + 37 / 96 * _N**3 - 1 / 360 * _N**4,
         1 / 48 * _N**2 + 1 / 15 * _N**3 - 437 / 1440 * _N**4,
         17 / 480 * _N**3 - 37 / 840 * _N**4,
         4397 / 161280 * _N**4]
_DELTA = [2 * _N - 2 / 3 * _N**2 - 2 * _N**3 + 116 / 45 * _N**4,
          7 / 3 * _N**2 - 8 / 5 * _N**3 - 227 / 45 * _N**4,
          56 / 15 * _N**3 - 136 / 35 * _N**4,
          4279 / 630 * _N**4]


def utm_zone_params(epsg: int) -> tuple[float, float, float]:
    """EPSG 326ZZ (WGS84 / UTM ZZN) → (lon0, FE, FN)."""
    zone = epsg - 32600
    if not 1 <= zone <= 60:
        raise ValueError(f"obsługiwane tylko UTM północ (326ZZ), jest {epsg}")
    return 6.0 * zone - 183.0, 500000.0, 0.0


def lonlat_to_utm(lon, lat, epsg: int):
    lon0, fe, fn = utm_zone_params(epsg)
    lon, lat = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    c = 2 * math.sqrt(_N) / (1 + _N)
    t = np.sinh(np.arctanh(np.sin(lat)) - c * np.arctanh(c * np.sin(lat)))
    dl = lon - math.radians(lon0)
    xi = np.arctan2(t, np.cos(dl))
    eta = np.arctanh(np.sin(dl) / np.sqrt(1 + t * t))
    e = eta + sum(a * np.cos(2 * j * xi) * np.sinh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    n = xi + sum(a * np.sin(2 * j * xi) * np.cosh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    return fe + 0.9996 * _AR * e, fn + 0.9996 * _AR * n


def utm_to_lonlat(x, y, epsg: int):
    lon0, fe, fn = utm_zone_params(epsg)
    xi = (np.asarray(y, float) - fn) / (0.9996 * _AR)
    eta = (np.asarray(x, float) - fe) / (0.9996 * _AR)
    xp, ep = xi.copy(), eta.copy()
    for j, b in enumerate(_BETA, 1):
        xp = xp - b * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
        ep = ep - b * np.cos(2 * j * xi) * np.sinh(2 * j * eta)
    chi = np.arcsin(np.sin(xp) / np.cosh(ep))
    lon = math.radians(lon0) + np.arctan2(np.sinh(ep), np.cos(xp))
    phi = chi + sum(d * np.sin(2 * j * chi) for j, d in enumerate(_DELTA, 1))
    return np.degrees(lon), np.degrees(phi)


# ---------------------------------------------------------------------------------- geometria

def points_in_ring(x, y, ring: np.ndarray) -> np.ndarray:
    inside = np.zeros(np.shape(x), bool)
    x1, y1 = ring[:, 0], ring[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
    for k in range(len(x1)):
        if y1[k] == y2[k]:
            continue
        cond = (y1[k] > y) != (y2[k] > y)
        xint = x1[k] + (y - y1[k]) * (x2[k] - x1[k]) / (y2[k] - y1[k])
        inside ^= cond & (x < xint)
    return inside


def square_around(lon: float, lat: float, half_m: float = 150.0) -> list[list[float]]:
    """Kwadrat ~2·half_m wokół punktu (lon/lat) – gdy nie mamy obrysu działki."""
    dlat = half_m / 110574.0
    dlon = half_m / (111320.0 * math.cos(math.radians(lat)))
    return [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat],
            [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]


# ---------------------------------------------------------------------------------- STAC

@dataclass
class Scene:
    id: str
    date: date
    cloud: float
    epsg: int
    assets: dict  # nazwa → {href, transform, shape, scale, offset}


def _scene_from_feature(f: dict) -> Scene:
    p = f["properties"]
    epsg = p.get("proj:epsg") or int(str(p.get("proj:code", "EPSG:0")).split(":")[1])
    assets = {}
    for k in ("red", "nir", "swir16", "scl"):
        a = f["assets"][k]
        rb = (a.get("raster:bands") or [{}])[0]
        assets[k] = {"href": a["href"], "transform": a["proj:transform"], "shape": a["proj:shape"],
                     "scale": rb.get("scale", 1.0), "offset": rb.get("offset", 0.0)}
    return Scene(f["id"], datetime.fromisoformat(p["datetime"].replace("Z", "+00:00")).date(),
                 float(p.get("eo:cloud_cover", 0.0)), int(epsg), assets)


def search_scenes(bbox: list[float], start: date, end: date, max_cloud: float = 40.0,
                  cache: Path | None = None) -> tuple[list[Scene], dict]:
    """Sceny przecinające bbox [lon_min, lat_min, lon_max, lat_max]; jedna na datę (najmniej chmur,
    przy remisie kafel, którego środek jest bliżej działki – nieistotne dla wyniku)."""
    payload = {"collections": [COLLECTION], "bbox": bbox,
               "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
               "query": {"eo:cloud_cover": {"lt": max_cloud}}, "limit": 200,
               "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
    info = {"seconds": None, "matched": None, "cached": False}
    if cache and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        info["cached"] = True
    else:
        d, dt = http_json(STAC_URL, payload)
        info["seconds"] = round(dt, 2)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            slim = {"context": d.get("context"), "features": [
                {"id": f["id"], "properties": {k: f["properties"].get(k) for k in
                                               ("datetime", "eo:cloud_cover", "proj:epsg", "proj:code")},
                 "assets": {k: {kk: f["assets"][k].get(kk) for kk in ("href", "proj:transform", "proj:shape",
                                                                      "raster:bands")}
                            for k in ("red", "nir", "swir16", "scl")}} for f in d["features"]]}
            cache.write_text(json.dumps(slim), encoding="utf-8")
            d = slim
    info["matched"] = (d.get("context") or {}).get("matched", len(d["features"]))
    by_date: dict[date, Scene] = {}
    for f in d["features"]:
        s = _scene_from_feature(f)
        if s.date not in by_date or s.cloud < by_date[s.date].cloud:
            by_date[s.date] = s
    return sorted(by_date.values(), key=lambda s: s.date, reverse=True), info


# ---------------------------------------------------------------------------------- COG – okno

def pixel_window(transform: list[float], bounds: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """(row0, row1, col0, col1) – okno pikseli pokrywające bounds (xmin, ymin, xmax, ymax) w CRS sceny."""
    res, _, x0, _, neg_res, y0 = transform[:6]
    xmin, ymin, xmax, ymax = bounds
    c0 = int(math.floor((xmin - x0) / res))
    c1 = int(math.ceil((xmax - x0) / res))
    r0 = int(math.floor((y0 - ymax) / -neg_res))
    r1 = int(math.ceil((y0 - ymin) / -neg_res))
    return r0, r1, c0, c1


def read_window(src, rows: tuple[int, int], cols: tuple[int, int]) -> tuple[np.ndarray, Stats]:
    """Okno (rows, cols) z pierwszej strony (pełna rozdzielczość) kafelkowanego GeoTIFF/COG.

    src: URL (czytany zakresami HTTP) albo ścieżka / obiekt pliku (testy offline). Czyta tylko kafle,
    które przecinają okno – każdy kafel jednym zapytaniem Range."""
    rf = RangeFile(src) if isinstance(src, str) and src.startswith("http") else None
    fh = rf if rf else (open(src, "rb") if isinstance(src, (str, Path)) else src)
    stats = Stats()
    try:
        with tifffile.TiffFile(fh) as tif:
            page = tif.pages[0]
            tw, tl = page.tilewidth, page.tilelength
            h, w = page.shape[:2]
            r0, r1 = max(0, rows[0]), min(h, rows[1])
            c0, c1 = max(0, cols[0]), min(w, cols[1])
            out = np.zeros((rows[1] - rows[0], cols[1] - cols[0]), dtype=page.dtype)
            ntx = (w + tw - 1) // tw
            for ty in range(r0 // tl, (r1 - 1) // tl + 1):
                for tx in range(c0 // tw, (c1 - 1) // tw + 1):
                    idx = ty * ntx + tx
                    off, cnt = page.dataoffsets[idx], page.databytecounts[idx]
                    if rf:
                        data = rf.read_exact(off, cnt)
                    else:
                        fh.seek(off)
                        data = fh.read(cnt)
                    tile, _, _ = page.decode(data, idx)
                    tile = np.asarray(tile).reshape(tl, tw)
                    ya, xa = ty * tl, tx * tw
                    rr0, rr1 = max(r0, ya), min(r1, ya + tl)
                    cc0, cc1 = max(c0, xa), min(c1, xa + tw)
                    out[rr0 - rows[0]:rr1 - rows[0], cc0 - cols[0]:cc1 - cols[0]] = \
                        tile[rr0 - ya:rr1 - ya, cc0 - xa:cc1 - xa]
    finally:
        if rf:
            stats.add(rf.stats)
        elif isinstance(src, (str, Path)):
            fh.close()
    return out, stats


def upsample2(a: np.ndarray, r_off: int, c_off: int, shape: tuple[int, int]) -> np.ndarray:
    """20 m → 10 m (najbliższy sąsiad: każdy piksel 20 m = 2×2 piksele 10 m), wycięcie do kształtu okna 10 m."""
    up = np.repeat(np.repeat(a, 2, axis=0), 2, axis=1)
    return up[r_off:r_off + shape[0], c_off:c_off + shape[1]]


# ---------------------------------------------------------------------------------- wskaźniki

def reflectance(dn: np.ndarray, scale: float, offset: float) -> np.ndarray:
    r = dn.astype(float) * scale + offset
    r[dn == 0] = np.nan  # 0 = nodata
    return r


def indices(red, nir, swir, scl, mask_parcel=None):
    """NDVI = (B08 − B04)/(B08 + B04), NDMI = (B08 − B11)/(B08 + B11) na odbiciu (po skali i offsecie).
    Zwraca ndvi, ndmi, valid (SCL ∈ {4, 5} i obrys działki) oraz udziały chmur/śniegu/ważnych w obrysie."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red) if red is not None else None
        ndmi = (nir - swir) / (nir + swir) if swir is not None else None
    inside = np.ones(scl.shape, bool) if mask_parcel is None else mask_parcel
    valid = np.isin(scl, SCL_VALID) & inside
    n = max(int(inside.sum()), 1)
    shares = {"cloud_pct": 100.0 * float((np.isin(scl, SCL_CLOUD) & inside).sum()) / n,
              "snow_pct": 100.0 * float((np.isin(scl, SCL_SNOW) & inside).sum()) / n,
              "valid_pct": 100.0 * float(valid.sum()) / n}
    return ndvi, ndmi, valid, shares


def _median(a, m):
    if a is None:
        return None
    v = a[m & np.isfinite(a)]
    return round(float(np.median(v)), 3) if v.size else None


# ---------------------------------------------------------------------------------- działka × scena

@dataclass
class ParcelGrid:
    epsg: int
    rows10: tuple[int, int]
    cols10: tuple[int, int]
    mask: np.ndarray            # obrys na siatce 10 m
    bounds_utm: tuple


def parcel_grid(ring_lonlat: list[list[float]], scene: Scene, margin_m: float = 20.0) -> ParcelGrid:
    ring = np.array(ring_lonlat, float)
    x, y = lonlat_to_utm(ring[:, 0], ring[:, 1], scene.epsg)
    b = (x.min() - margin_m, y.min() - margin_m, x.max() + margin_m, y.max() + margin_m)
    t10 = scene.assets["red"]["transform"]
    r0, r1, c0, c1 = pixel_window(t10, b)
    # wyrównanie do siatki 20 m (parzyste indeksy) – SCL i B11 mają ten sam początek co pasma 10 m
    r0, c0 = r0 - r0 % 2, c0 - c0 % 2
    r1, c1 = r1 + r1 % 2, c1 + c1 % 2
    xs = t10[2] + (np.arange(c0, c1) + 0.5) * t10[0]
    ys = t10[5] + (np.arange(r0, r1) + 0.5) * t10[4]
    X, Y = np.meshgrid(xs, ys)
    mask = points_in_ring(X, Y, np.column_stack([x, y]))
    return ParcelGrid(scene.epsg, (r0, r1), (c0, c1), mask, b)


def read_scene(scene: Scene, grid: ParcelGrid, bands: bool = True, src_override: dict | None = None):
    """SCL zawsze; pasma tylko gdy bands=True. Zwraca słownik z tablicami 10 m i statystyką pobrania."""
    st = Stats()
    src = src_override or {k: v["href"] for k, v in scene.assets.items()}
    r0, r1 = grid.rows10
    c0, c1 = grid.cols10
    shape = (r1 - r0, c1 - c0)
    scl20, s = read_window(src["scl"], (r0 // 2, r1 // 2), (c0 // 2, c1 // 2))
    st.add(s)
    out = {"scl": upsample2(scl20, 0, 0, shape)}
    if bands:
        for k in ("red", "nir"):
            a, s = read_window(src[k], (r0, r1), (c0, c1))
            st.add(s)
            out[k] = reflectance(a, scene.assets[k]["scale"],
                                 scene.assets[k]["offset"] if APPLY_STAC_OFFSET else 0.0)
        a, s = read_window(src["swir16"], (r0 // 2, r1 // 2), (c0 // 2, c1 // 2))
        st.add(s)
        out["swir16"] = reflectance(upsample2(a, 0, 0, shape), scene.assets["swir16"]["scale"],
                                    scene.assets["swir16"]["offset"] if APPLY_STAC_OFFSET else 0.0)
    out["stats"] = st
    return out


def scene_point(scene: Scene, grid: ParcelGrid, bands: bool = True, src_override=None) -> dict:
    d = read_scene(scene, grid, bands, src_override)
    ndvi, ndmi, valid, sh = indices(d.get("red"), d.get("nir"), d.get("swir16"), d["scl"], grid.mask)
    usable = bands and sh["valid_pct"] >= USABLE_MIN_VALID
    return {"date": scene.date.isoformat(), "scene": scene.id, "scene_cloud_pct": round(scene.cloud, 1),
            "cloud_pct": round(sh["cloud_pct"], 1), "snow_pct": round(sh["snow_pct"], 1),
            "valid_pct": round(sh["valid_pct"], 1),
            "ndvi": _median(ndvi, valid) if usable else None, "ndmi": _median(ndmi, valid) if usable else None,
            "bytes": d["stats"].bytes, "requests": d["stats"].requests,
            "_arrays": {"ndvi": ndvi, "ndmi": ndmi, "valid": valid, "scl": d["scl"]} if bands else None}


def is_clear(p: dict) -> bool:
    return p["cloud_pct"] + p["snow_pct"] <= CLEAR_MAX_CLOUD and p["valid_pct"] >= USABLE_MIN_VALID


# ---------------------------------------------------------------------------------- szereg i podsumowanie

def timeseries(ring_lonlat, scenes: list[Scene], start: date, end: date, bin_days: int = 15,
               src_override=None) -> tuple[list[dict], Stats]:
    """Szereg: dla każdej sceny maska SCL (tanio); pasma czytane dla pierwszej czystej sceny w każdym
    oknie bin_days dni (ogranicza pobieranie ~1,4 MB na pasmo 10 m)."""
    st = Stats()
    pts, taken_bins = [], set()
    grids = {}
    for sc in sorted([s for s in scenes if start <= s.date <= end], key=lambda s: s.date):
        key = tuple(sc.assets["red"]["transform"][:6])  # siatka zależy od kafla (początek układu), nie tylko od strefy
        g = grids.get(key) or grids.setdefault(key, parcel_grid(ring_lonlat, sc))
        p = scene_point(sc, g, bands=False, src_override=src_override and src_override(sc))
        st.bytes += p["bytes"]
        st.requests += p["requests"]
        b = (sc.date - start).days // bin_days
        if is_clear(p) and b not in taken_bins:
            p = scene_point(sc, g, bands=True, src_override=src_override and src_override(sc))
            st.bytes += p["bytes"]
            st.requests += p["requests"]
            if p["ndvi"] is not None:
                taken_bins.add(b)
        p.pop("_arrays", None)
        pts.append(p)
    return pts, st


def compare_sentence(now: dict, last_year: dict | None, month: int) -> str:
    """Jedno zdanie dla rolnika (progi DNDVI/DNDMI – szacunek). Porównujemy z tym samym okresem rok
    wcześniej, nie z latem – w listopadzie niska zieleń jest normalna."""
    if now.get("ndvi") is None:
        return "Brak bezchmurnego zdjęcia satelitarnego działki – nie oceniamy zieleni."
    off_season = month in (11, 12, 1, 2, 3)
    base = ("Poza sezonem wegetacji – niska zieleń o tej porze jest normalna. "
            if off_season and now["ndvi"] < 0.5 else "")
    if not last_year or last_year.get("ndvi") is None:
        return base + f"Zieleń (NDVI) {now['ndvi']:.2f}; brak zdjęcia z tego okresu rok temu do porównania."
    d = now["ndvi"] - last_year["ndvi"]
    dm = (now["ndmi"] - last_year["ndmi"]) if now.get("ndmi") is not None and last_year.get("ndmi") is not None else 0
    if d <= -DNDVI:
        s = "Słabsza zieleń niż rok temu o tej porze"
        s += " i mniej wilgotne rośliny – możliwy stres wodny." if dm <= -DNDMI else \
             " – możliwy stres wodny albo inna uprawa / termin siewu."
    elif d >= DNDVI:
        s = "Zieleń lepsza niż rok temu o tej porze."
    else:
        s = "Zieleń podobna jak rok temu o tej porze."
        if dm <= -DNDMI:
            s += " Rośliny suchsze niż rok temu – obserwuj wilgotność."
    return base + s + f" (NDVI {now['ndvi']:.2f} vs {last_year['ndvi']:.2f} rok temu)"


def last_year_match(points: list[dict], ref: date, tol_days: int = 20) -> dict | None:
    target = ref - timedelta(days=365)
    cand = [p for p in points if p.get("ndvi") is not None and abs((date.fromisoformat(p["date"]) - target).days) <= tol_days]
    return min(cand, key=lambda p: abs((date.fromisoformat(p["date"]) - target).days)) if cand else None


def parcel_summary(ring_lonlat, scenes: list[Scene], today: date, max_scenes: int = 15,
                   src_override=None) -> tuple[dict, dict | None, Stats]:
    """Ostatnia czysta scena (SCL najpierw, od najnowszej; najwyżej max_scenes masek). Gdy żadna nie
    jest czysta – ostatnia z ważnymi pikselami, z ostrzeżeniem. Zwraca (punkt, tablice, statystyki)."""
    st = Stats()
    fallback = None
    for sc in [s for s in scenes if s.date <= today][:max_scenes]:
        g = parcel_grid(ring_lonlat, sc)
        p = scene_point(sc, g, bands=False, src_override=src_override and src_override(sc))
        st.bytes += p["bytes"]
        st.requests += p["requests"]
        if is_clear(p) or (fallback is None and p["valid_pct"] > 0):
            full = scene_point(sc, g, bands=True, src_override=src_override and src_override(sc))
            st.bytes += full["bytes"]
            st.requests += full["requests"]
            full["grid"] = g
            if is_clear(full):
                full["warning"] = None
                return full, full.pop("_arrays"), st
            if fallback is None and full["ndvi"] is not None:
                fallback = full
    if fallback:
        fallback["warning"] = (f"Brak bezchmurnej sceny w ostatnich {max_scenes} przelotach – pokazujemy "
                               f"ostatnią dostępną ({fallback['date']}, chmury {fallback['cloud_pct']:.0f} % działki).")
        return fallback, fallback.pop("_arrays"), st
    return {"warning": "Brak użytecznej sceny Sentinel-2.", "ndvi": None, "ndmi": None}, None, st
