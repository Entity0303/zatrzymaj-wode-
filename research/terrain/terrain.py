"""Prototyp analizy terenu i spływu wody dla działki rolnej (research C1).

To NIE jest część aplikacji – osobny skrypt badawczy. Czysty Python + numpy
(bez pysheds / richdem / innych bibliotek GPL; bez shapely/pyproj, żeby moduł był
samowystarczalny – odwzorowanie PL-1992 → WGS84 liczone wzorami Krügera).

Dane:
- ULDK GUGiK  – obrys działki (EPSG:2180, współrzędne (wschód, północ)),
- NMT GUGiK   – wysokości (GetHByPointList, EPSG:2180, kolejność x = PÓŁNOC, y = WSCHÓD!).

Główne wejścia:
- analyze_parcel(parcel_id | wkt)  → TerrainResult (rastry + fakty + GeoJSON + czasy),
- terrain_facts(parcel_geom)       → dict (fakty do reguł rekomendacji),
- terrain_layers(parcel_geom)      → GeoJSON FeatureCollection (EPSG:4326),
- analyze_surface(z, step, inside) → rdzeń obliczeń na gotowej siatce (testowalny bez sieci).

Konwencja siatki: wiersz 0 = PÓŁNOC, kolumna 0 = ZACHÓD; środek komórki (i, j) ma
E = e0 + j*step, N = n0 - i*step.
"""

from __future__ import annotations

import heapq
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import numpy as np

ULDK_URL = "https://uldk.gugik.gov.pl/"
NMT_URL = "https://services.gugik.gov.pl/nmt/"
USER_AGENT = "zatrzymaj-wode-research/0.1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """NIGDY nie podążamy za przekierowaniem: GUGiK przy limicie odpowiada 302 i serwuje plik ~126 MB.
    redirect_request → None sprawia, że urllib zgłasza HTTPError z kodem 3xx; treści 3xx nie czytamy."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

# --------------------------------------------------------------------------------------
# Parametry i progi (jawne – patrz NOTES.md „Progi i dlaczego”)
# --------------------------------------------------------------------------------------

DEFAULT_PARAMS: dict[str, Any] = {
    # siatka / pobieranie
    "buffer_m": 100.0,            # bufor wokół działki – zlewnia z sąsiednich pól i miejsce odpływu
    "max_points": 6000,           # max punktów NMT (6 zapytań POST po 1000, równolegle)
    "chunk_points": 1000,         # limit punktów w jednym POST
    "min_step_m": 3.0,
    "max_step_m": 40.0,
    "workers": 6,
    "timeout_s": 12.0,            # twardy limit na jedno zapytanie (NMT potrafi „zawisnąć”)
    "retries": 2,
    "uldk_timeout_s": 4.0,        # ULDK zwykle odpowiada w 0,2–0,4 s; dłużej = zawieszone połączenie
    # wygładzenie mikrorzeźby (NMT podaje wysokości co 0,1 m → szum spadku 0,1/krok)
    "smooth_sigma_m": 6.0,        # 0 = bez wygładzania
    # strefy
    "flat_slope_pct": 3.0,        # < 3 % = płasko, >= 3 % = stok
    "tpi_radius_m": 40.0,         # promień okna położenia względnego (TPI)
    "hill_tpi_m": 0.30,           # górka: wyżej od otoczenia o >= 0,3 m i wypukło
    "wet_tpi_m": -0.30,           # dołek: niżej od otoczenia o >= 0,3 m (przy małym spadku)
    "twi_wet": 11.0,              # dołek: TWI >= 11 (zbieżny spływ) przy małym spadku
    "twi_min_tan": 0.005,         # dolne ograniczenie tan β w TWI (0,5 % – poniżej precyzji NMT)
    "min_zone_area_m2": 100.0,    # mniejsze plamy nie liczą się jako osobna górka
    # zagłębienia bez odpływu
    "depression_min_depth_m": 0.20,   # 2× precyzja NMT (0,1 m)
    "depression_min_area_m2": 50.0,
    # spływ
    "flow_method_twi": "dinf",    # "d8" albo "dinf" (akumulacja do TWI)
    "outlet_min_share": 0.05,     # wyjście wody pokazujemy, gdy odprowadza >= 5 % działki
    "max_outlets": 5,
    # propozycje
    "rain_mm": 20.0,
    "runoff_coeff": 0.3,          # współczynnik spływu dla gruntu ornego przy deszczu 20 mm
    "pond_depth_m": 1.5,          # projektowa głębokość oczka (do sugerowanej powierzchni)
    "buffer_strip_slope_pct": 5.0,    # pas buforowy, gdy spadek > 5 % ...
    "buffer_strip_min_share": 0.10,   # ... na >= 10 % powierzchni działki
    "buffer_strip_width_m": 10.0,
    "buffer_strip_spacing_m": 120.0,  # kolejny pas co ~120 m długości stoku
}

# D8: kolejność N, NE, E, SE, S, SW, W, NW (wiersz rośnie na południe)
D8_DI = np.array([-1, -1, 0, 1, 1, 1, 0, -1])
D8_DJ = np.array([0, 1, 1, 1, 0, -1, -1, -1])
D8_AZ = np.array([0, 45, 90, 135, 180, 225, 270, 315], dtype=float)
D8_DIST = np.array([1, math.sqrt(2)] * 4)

AZ_NAMES = ["północ", "północny wschód", "wschód", "południowy wschód",
            "południe", "południowy zachód", "zachód", "północny zachód"]
AZ_SHORT = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

ZONE_FLAT, ZONE_SLOPE, ZONE_HILL, ZONE_WET = 0, 1, 2, 3
ZONE_KEYS = {ZONE_FLAT: "plasko", ZONE_SLOPE: "stok", ZONE_HILL: "sucha_gorka", ZONE_WET: "mokry_dolek"}
ZONE_LABELS = {ZONE_FLAT: "płasko", ZONE_SLOPE: "stok", ZONE_HILL: "sucha górka", ZONE_WET: "mokry dołek"}


def az_name(az: float) -> tuple[str, str]:
    k = int(((az % 360) + 22.5) // 45) % 8
    return AZ_NAMES[k], AZ_SHORT[k]


# --------------------------------------------------------------------------------------
# Geometria
# --------------------------------------------------------------------------------------

Polygons = list[list[np.ndarray]]  # [polygon][ring] -> (n, 2) tablica (E, N)


def parse_wkt(text: str) -> Polygons:
    """WKT/EWKT POLYGON lub MULTIPOLYGON (np. 'SRID=2180;POLYGON((E N, ...))') → Polygons."""
    t = text.strip()
    if ";" in t:
        t = t.split(";", 1)[1].strip()
    up = t.upper()
    if not (up.startswith("POLYGON") or up.startswith("MULTIPOLYGON")):
        raise ValueError(f"Obsługiwane tylko POLYGON/MULTIPOLYGON, jest: {t[:30]}")
    body = t[t.index("("):]
    polys: Polygons = []
    depth = 0
    cur_poly: list[np.ndarray] = []
    buf = ""
    multi = up.startswith("MULTIPOLYGON")
    ring_depth = 3 if multi else 2
    for ch in body:
        if ch == "(":
            depth += 1
            if depth == ring_depth:
                buf = ""
        elif ch == ")":
            if depth == ring_depth:
                pts = [tuple(map(float, p.split()[:2])) for p in buf.split(",") if p.strip()]
                cur_poly.append(np.array(pts, dtype=float))
            if depth == ring_depth - 1:
                polys.append(cur_poly)
                cur_poly = []
            depth -= 1
        elif depth == ring_depth:
            buf += ch
    return polys


def to_polygons(geom: Any) -> Polygons:
    """Akceptuje: WKT/EWKT (EPSG:2180), obiekt z atrybutem .wkt (np. shapely), Polygons."""
    if isinstance(geom, str):
        return parse_wkt(geom)
    if hasattr(geom, "wkt"):
        return parse_wkt(geom.wkt)
    if isinstance(geom, list):
        return [[np.asarray(r, dtype=float) for r in poly] for poly in geom]
    raise TypeError("parcel_geom: WKT (EPSG:2180), obiekt z .wkt albo lista pierścieni")


def ring_area(ring: np.ndarray) -> float:
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def polygons_area(polys: Polygons) -> float:
    return sum(abs(ring_area(p[0])) - sum(abs(ring_area(h)) for h in p[1:]) for p in polys)


def points_in_polygons(e: np.ndarray, n: np.ndarray, polys: Polygons) -> np.ndarray:
    """Maska punktów wewnątrz (reguła parzystości po wszystkich pierścieniach poligonu)."""
    e = np.asarray(e, dtype=float)
    n = np.asarray(n, dtype=float)
    out = np.zeros(e.shape, dtype=bool)
    for poly in polys:
        inside = np.zeros(e.shape, dtype=bool)
        for ring in poly:
            x1, y1 = ring[:, 0], ring[:, 1]
            x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
            for k in range(len(x1)):
                if y1[k] == y2[k]:
                    continue
                cond = (y1[k] > n) != (y2[k] > n)
                xint = x1[k] + (n - y1[k]) * (x2[k] - x1[k]) / (y2[k] - y1[k])
                inside ^= cond & (e < xint)
        out |= inside
    return out


# PL-1992 (EPSG:2180): odwzorowanie Gaussa-Krügera na GRS80, L0 = 19°, k0 = 0,9993,
# FE = 500 000, FN = -5 300 000. Odwrotne wzory Krügera (szereg w n do n^4, dokładność << 1 mm).
_A = 6378137.0
_F = 1 / 298.257222101
_N = _F / (2 - _F)
_AR = _A / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64)
_BETA = [
    _N / 2 - 2 / 3 * _N**2 + 37 / 96 * _N**3 - 1 / 360 * _N**4,
    1 / 48 * _N**2 + 1 / 15 * _N**3 - 437 / 1440 * _N**4,
    17 / 480 * _N**3 - 37 / 840 * _N**4,
    4397 / 161280 * _N**4,
]
_DELTA = [
    2 * _N - 2 / 3 * _N**2 - 2 * _N**3 + 116 / 45 * _N**4,
    7 / 3 * _N**2 - 8 / 5 * _N**3 - 227 / 45 * _N**4,
    56 / 15 * _N**3 - 136 / 35 * _N**4,
    4279 / 630 * _N**4,
]


def puwg1992_to_wgs84(e, n):
    """EPSG:2180 (wschód, północ) → EPSG:4326 (lon, lat) w stopniach."""
    e = np.asarray(e, dtype=float)
    n = np.asarray(n, dtype=float)
    k0, fe, fn, lon0 = 0.9993, 500000.0, -5300000.0, math.radians(19.0)
    xi = (n - fn) / (k0 * _AR)
    eta = (e - fe) / (k0 * _AR)
    xi_p, eta_p = xi.copy(), eta.copy()
    for j, b in enumerate(_BETA, start=1):
        xi_p -= b * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
        eta_p -= b * np.cos(2 * j * xi) * np.sinh(2 * j * eta)
    chi = np.arcsin(np.sin(xi_p) / np.cosh(eta_p))
    lam = lon0 + np.arctan2(np.sinh(eta_p), np.cos(xi_p))
    phi = chi.copy()
    for j, d in enumerate(_DELTA, start=1):
        phi += d * np.sin(2 * j * chi)
    return np.degrees(lam), np.degrees(phi)


# --------------------------------------------------------------------------------------
# Pobieranie danych (równolegle, timeout, ponowienie)
# --------------------------------------------------------------------------------------

def http_request(url: str, data: dict | None = None, timeout: float = 12.0,
                 retries: int = 2, max_bytes: int = 5_000_000) -> str:
    """GET/POST z twardym limitem czasu CAŁEGO odczytu i rozmiaru odpowiedzi.

    NMT potrafi zawiesić odpowiedź albo zadeklarować kilka GB – socket timeout to za mało.
    """
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    last: Exception | None = None
    for attempt in range(retries + 1):
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT,
                                                                 "Connection": "close"})
            with _OPENER.open(req, timeout=timeout) as resp:
                chunks, size = [], 0
                while True:
                    if time.monotonic() - t0 > timeout:
                        raise TimeoutError(f"odczyt > {timeout} s")
                    part = resp.read(65536)
                    if not part:
                        break
                    size += len(part)
                    if size > max_bytes:
                        raise ValueError(f"odpowiedź > {max_bytes} B")
                    chunks.append(part)
            return b"".join(chunks).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:  # przekierowanie = usługa ogranicza ruch; treści nie czytamy
                exc.close()
                last = RuntimeError(f"HTTP {exc.code} (przekierowanie – usługa ogranicza ruch)")
            else:
                last = exc
        except Exception as exc:  # noqa: BLE001 – każde źródło może zawieść, ponawiamy
            last = exc
            time.sleep(0.3 * (attempt + 1))
    raise RuntimeError(f"Zapytanie nieudane po {retries + 1} próbach: {last}")


def fetch_parcel_wkt(parcel_id: str, timeout: float = 10.0) -> str:
    url = ULDK_URL + "?" + urllib.parse.urlencode(
        {"request": "GetParcelById", "id": parcel_id, "result": "geom_wkt", "srid": "2180"})
    text = http_request(url, timeout=timeout)
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines or lines[0].strip().startswith("-1") or len(lines) < 2:
        raise LookupError(f"ULDK: brak działki {parcel_id!r} ({text[:80]!r})")
    return lines[1].split("|")[0].strip()


def parcel_id_by_lonlat(lon: float, lat: float, timeout: float = 10.0) -> str:
    url = ULDK_URL + "?" + urllib.parse.urlencode(
        {"request": "GetParcelByXY", "xy": f"{lon},{lat},4326", "result": "id"})
    lines = [ln for ln in http_request(url, timeout=timeout).strip().splitlines() if ln.strip()]
    if not lines or lines[0].strip().startswith("-1") or len(lines) < 2:
        raise LookupError(f"ULDK: brak działki w punkcie {lon},{lat}")
    return lines[1].split("|")[0].strip()


def choose_step(area_m2: float, bbox_w: float, bbox_h: float, p: dict) -> float:
    """Krok siatki: ~5 m dla 1 ha, ~15 m dla 20 ha (krok ∝ pow^0,37), w limicie punktów."""
    area_ha = max(area_m2 / 1e4, 0.01)
    step = 5.0 * area_ha ** 0.367
    step = min(max(step, p["min_step_m"]), p["max_step_m"])
    while True:
        npts = (math.floor(bbox_w / step) + 1) * (math.floor(bbox_h / step) + 1)
        if npts <= p["max_points"] or step >= p["max_step_m"]:
            break
        step *= math.sqrt(npts / p["max_points"]) * 1.01
    return math.ceil(step * 2) / 2  # w górę do 0,5 m (żeby nie przekroczyć limitu punktów)


@dataclass
class Grid:
    e0: float
    n0: float
    step: float
    nrows: int
    ncols: int

    def centers(self) -> tuple[np.ndarray, np.ndarray]:
        jj, ii = np.meshgrid(np.arange(self.ncols), np.arange(self.nrows))
        return self.e0 + jj * self.step, self.n0 - ii * self.step

    def cell_to_en(self, i, j):
        return self.e0 + np.asarray(j) * self.step, self.n0 - np.asarray(i) * self.step


def make_grid(polys: Polygons, buffer_m: float, step: float) -> Grid:
    allpts = np.vstack([r for p in polys for r in p])
    emin, nmin = allpts.min(axis=0) - buffer_m
    emax, nmax = allpts.max(axis=0) + buffer_m
    ncols = int(math.floor((emax - emin) / step)) + 1
    nrows = int(math.floor((nmax - nmin) / step)) + 1
    return Grid(e0=float(emin), n0=float(nmax), step=step, nrows=nrows, ncols=ncols)


def _nmt_chunk(e: np.ndarray, n: np.ndarray, p: dict) -> dict[tuple[float, float], float]:
    # NMT: x = PÓŁNOC, y = WSCHÓD (odwrotnie niż ULDK!)
    lst = ",".join(f"{nn:.2f} {ee:.2f}" for ee, nn in zip(e, n))
    text = http_request(NMT_URL, data={"request": "GetHByPointList", "list": lst},
                        timeout=p["timeout_s"], retries=p["retries"],
                        max_bytes=80 * len(e) + 10_000)
    out: dict[tuple[float, float], float] = {}
    for trip in text.strip().split(","):
        parts = trip.split()
        if len(parts) < 3:
            continue
        try:
            x, y, h = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        if not math.isfinite(h) or h < -100 or h > 3000:
            continue
        out[(round(y, 1), round(x, 1))] = h  # klucz (E, N)
    return out


def fetch_heights(e: np.ndarray, n: np.ndarray, p: dict | None = None) -> tuple[np.ndarray, dict]:
    """Wysokości NMT dla punktów (E, N) – POST po <= 1000 punktów, równolegle."""
    p = {**DEFAULT_PARAMS, **(p or {})}
    e = np.asarray(e, dtype=float).ravel()
    n = np.asarray(n, dtype=float).ravel()
    m = p["chunk_points"]
    idx = [np.arange(k, min(k + m, e.size)) for k in range(0, e.size, m)]
    h = np.full(e.size, np.nan)
    failed = 0

    def job(ix):
        return ix, _nmt_chunk(e[ix], n[ix], p)

    with ThreadPoolExecutor(max_workers=min(p["workers"], len(idx))) as ex:
        futures = [ex.submit(job, ix) for ix in idx]
        for f in futures:
            try:
                ix, res = f.result()
            except Exception:  # noqa: BLE001 – brak paczki = brak danych, nie wywracamy analizy
                failed += 1
                continue
            for k in ix:
                h[k] = res.get((round(e[k], 1), round(n[k], 1)), np.nan)
    # NMT dla punktów bez danych zwraca 0.0 zamiast błędu (sprawdzone na żywo w małopolskim).
    # Zero traktujemy jako brak, gdy teren wyraźnie leży wyżej (Żuławy < 0 m zostają nietknięte).
    zeros = 0
    if np.isfinite(h).any() and np.nanmedian(h) > 5.0:
        zmask = h == 0.0
        zeros = int(zmask.sum())
        h[zmask] = np.nan
    info = {"requests": len(idx), "failed_requests": failed, "zero_values": zeros,
            "missing_share": float(np.isnan(h).mean())}
    return h, info


def despike(z: np.ndarray, max_dev_m: float = 25.0) -> tuple[np.ndarray, int]:
    """Usuwa pojedyncze błędne wysokości (odchyłka od mediany 8 sąsiadów > max_dev_m)."""
    nb = _neighbors_padded(np.where(np.isnan(z), np.nan, z))
    med = np.nanmedian(nb, axis=0)
    bad = np.isfinite(z) & np.isfinite(med) & (np.abs(z - med) > max_dev_m)
    out = z.copy()
    out[bad] = np.nan
    return out, int(bad.sum())


def fill_nans(z: np.ndarray, max_iter: int = 200) -> np.ndarray:
    """Uzupełnia braki średnią z sąsiadów (iteracyjnie)."""
    z = z.copy()
    for _ in range(max_iter):
        bad = np.isnan(z)
        if not bad.any():
            break
        zp = np.pad(z, 1, mode="constant", constant_values=np.nan)
        stack = np.stack([zp[1 + di:1 + di + z.shape[0], 1 + dj:1 + dj + z.shape[1]]
                          for di, dj in zip(D8_DI, D8_DJ)])
        cnt = (~np.isnan(stack)).sum(axis=0)
        mean = np.where(cnt > 0, np.nansum(stack, axis=0) / np.maximum(cnt, 1), np.nan)
        z[bad] = mean[bad]
    if np.isnan(z).any():
        z[np.isnan(z)] = np.nanmean(z)
    return z


# --------------------------------------------------------------------------------------
# Operacje rastrowe
# --------------------------------------------------------------------------------------

def gaussian_smooth(z: np.ndarray, sigma_cells: float) -> np.ndarray:
    if sigma_cells <= 0.3:
        return z.copy()
    r = int(math.ceil(3 * sigma_cells))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_cells) ** 2)
    k /= k.sum()
    zp = np.pad(z, ((0, 0), (r, r)), mode="edge")
    tmp = sum(k[t] * zp[:, t:t + z.shape[1]] for t in range(2 * r + 1))
    zp = np.pad(tmp, ((r, r), (0, 0)), mode="edge")
    return sum(k[t] * zp[t:t + z.shape[0], :] for t in range(2 * r + 1))


def _neighbors_padded(z: np.ndarray) -> np.ndarray:
    zp = np.pad(z, 1, mode="edge")
    h, w = z.shape
    return np.stack([zp[1 + di:1 + di + h, 1 + dj:1 + dj + w] for di, dj in zip(D8_DI, D8_DJ)])


def slope_aspect(z: np.ndarray, step: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Metoda Horna. Zwraca spadek [%], ekspozycję [° od N, kierunek w dół stoku; -1 = płasko],
    dz/dE, dz/dN."""
    zp = np.pad(z, 1, mode="edge")
    h, w = z.shape
    a, b, c = zp[0:h, 0:w], zp[0:h, 1:w + 1], zp[0:h, 2:w + 2]
    d, f = zp[1:h + 1, 0:w], zp[1:h + 1, 2:w + 2]
    g, hh, i = zp[2:h + 2, 0:w], zp[2:h + 2, 1:w + 1], zp[2:h + 2, 2:w + 2]
    dzde = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * step)
    dzdn = ((a + 2 * b + c) - (g + 2 * hh + i)) / (8 * step)
    slope = 100 * np.hypot(dzde, dzdn)
    aspect = np.degrees(np.arctan2(-dzde, -dzdn)) % 360
    aspect = np.where(slope < 0.5, -1.0, aspect)
    return slope, aspect, dzde, dzdn


def laplacian(z: np.ndarray, step: float) -> np.ndarray:
    zp = np.pad(z, 1, mode="edge")
    h, w = z.shape
    return (zp[0:h, 1:w + 1] + zp[2:h + 2, 1:w + 1] + zp[1:h + 1, 0:w] + zp[1:h + 1, 2:w + 2]
            - 4 * z) / step**2


def tpi(z: np.ndarray, radius_cells: int) -> np.ndarray:
    """Topographic Position Index = z − średnia w oknie (2r+1)². Brzeg siatki (niepełne okno) = 0."""
    r = max(1, int(radius_cells))
    h, w = z.shape
    s = np.zeros((h + 1, w + 1))
    s[1:, 1:] = z.cumsum(0).cumsum(1)
    out = np.zeros_like(z)
    if h <= 2 * r or w <= 2 * r:
        return out
    win = (s[2 * r + 1:, 2 * r + 1:] - s[:-2 * r - 1, 2 * r + 1:]
           - s[2 * r + 1:, :-2 * r - 1] + s[:-2 * r - 1, :-2 * r - 1])
    mean = win / (2 * r + 1) ** 2
    out[r:h - r, r:w - r] = z[r:h - r, r:w - r] - mean
    return out


def dilate(mask: np.ndarray, it: int = 1) -> np.ndarray:
    m = mask.copy()
    for _ in range(it):
        m = _neighbors_padded(m.astype(float)).max(axis=0).astype(bool) | m
    return m


def label(mask: np.ndarray, conn: int = 8) -> tuple[np.ndarray, int]:
    """Etykietowanie spójnych składowych (BFS, 4- lub 8-sąsiedztwo)."""
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    offs = list(zip(D8_DI, D8_DJ)) if conn == 8 else [(-1, 0), (1, 0), (0, -1), (0, 1)]
    cur = 0
    for si, sj in zip(*np.nonzero(mask)):
        if lab[si, sj]:
            continue
        cur += 1
        lab[si, sj] = cur
        stack = [(si, sj)]
        while stack:
            i, j = stack.pop()
            for di, dj in offs:
                a, b = i + di, j + dj
                if 0 <= a < h and 0 <= b < w and mask[a, b] and not lab[a, b]:
                    lab[a, b] = cur
                    stack.append((a, b))
    return lab, cur


# --------------------------------------------------------------------------------------
# Hydrologia: priority-flood, D8, D-infinity, akumulacja
# --------------------------------------------------------------------------------------

def priority_flood(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Priority-Flood (Barnes i in. 2014). Zwraca:
    filled – DEM z wypełnionymi zagłębieniami (do poziomu przelewu),
    order  – kolejność zdejmowania z kolejki (niemalejąca wysokość wypełniona; odbiorca
             spływu zawsze wcześniej ⇒ odwrócona kolejność = porządek topologiczny),
    parent – komórka, z której dotarła fala (kierunek przez płaskie i wypełnione obszary).
    """
    h, w = z.shape
    zf = z.ravel()
    filled = zf.copy()
    closed = np.zeros(h * w, dtype=bool)
    parent = np.full(h * w, -1, dtype=np.int64)
    heap: list[tuple[float, int, int]] = []
    cnt = 0
    edge = np.zeros((h, w), dtype=bool)
    edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
    for c in np.flatnonzero(edge.ravel()):
        closed[c] = True
        heap.append((float(zf[c]), cnt, int(c)))
        cnt += 1
    heapq.heapify(heap)
    order = np.empty(h * w, dtype=np.int64)
    k = 0
    pop, push = heapq.heappop, heapq.heappush
    di_l, dj_l = D8_DI.tolist(), D8_DJ.tolist()
    while heap:
        hc, _, c = pop(heap)
        order[k] = c
        k += 1
        i, j = divmod(c, w)
        for di, dj in zip(di_l, dj_l):
            a, b = i + di, j + dj
            if a < 0 or a >= h or b < 0 or b >= w:
                continue
            nb = a * w + b
            if closed[nb]:
                continue
            closed[nb] = True
            v = zf[nb]
            if v < hc:
                v = hc
            filled[nb] = v
            parent[nb] = c
            push(heap, (float(v), cnt, nb))
            cnt += 1
    return filled.reshape(h, w), order, parent


def d8_receivers(filled: np.ndarray, parent: np.ndarray, step: float) -> np.ndarray:
    """Odbiorca D8 (indeks płaski; -1 = wypływ poza siatkę). Najstromszy spadek po
    wypełnionym DEM; na płaskich / w wypełnionych zagłębieniach – kierunek z priority-flood."""
    h, w = filled.shape
    nbz = _neighbors_padded(filled)
    drop = (filled[None] - nbz) / (D8_DIST[:, None, None] * step)
    ii, jj = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    valid = np.stack([(ii + di >= 0) & (ii + di < h) & (jj + dj >= 0) & (jj + dj < w)
                      for di, dj in zip(D8_DI, D8_DJ)])
    drop = np.where(valid, drop, -np.inf)
    k = drop.argmax(axis=0)
    best = drop.max(axis=0)
    recv_steep = (ii + D8_DI[k]) * w + (jj + D8_DJ[k])
    recv = np.where(best > 1e-9, recv_steep, parent.reshape(h, w))
    return recv.ravel().astype(np.int64)


def accumulate_d8(recv: np.ndarray, order: np.ndarray, weights: np.ndarray) -> np.ndarray:
    acc = weights.ravel().astype(float).copy()
    rl = recv.tolist()
    al = acc.tolist()
    for c in order[::-1].tolist():
        r = rl[c]
        if r >= 0:
            al[r] += al[c]
    return np.array(al).reshape(weights.shape)


# Fasety D-infinity (Tarboton 1997): (sąsiad kardynalny, sąsiad diagonalny) jako indeksy D8
_DINF_FACETS = [(2, 1), (0, 1), (0, 7), (6, 7), (6, 5), (4, 5), (4, 3), (2, 3)]


def dinf_weights(filled: np.ndarray, step: float):
    """Kierunki D-infinity: dla każdej komórki dwaj odbiorcy (indeksy D8) i udział diagonalnego."""
    nbz = _neighbors_padded(filled)
    best_s = np.full(filled.shape, -np.inf)
    best_card = np.zeros(filled.shape, dtype=np.int64)
    best_diag = np.zeros(filled.shape, dtype=np.int64)
    best_frac = np.zeros(filled.shape)
    for kc, kd in _DINF_FACETS:
        e1, e2 = nbz[kc], nbz[kd]
        s1 = (filled - e1) / step
        s2 = (e1 - e2) / step
        r = np.arctan2(s2, s1)
        s = np.hypot(s1, s2)
        lo = r < 0
        hi = r > math.pi / 4
        r = np.where(lo, 0.0, np.where(hi, math.pi / 4, r))
        s = np.where(lo, s1, np.where(hi, (filled - e2) / (step * math.sqrt(2)), s))
        better = s > best_s
        best_s = np.where(better, s, best_s)
        best_card = np.where(better, kc, best_card)
        best_diag = np.where(better, kd, best_diag)
        best_frac = np.where(better, r / (math.pi / 4), best_frac)
    return best_s, best_card, best_diag, best_frac


def accumulate_dinf(filled: np.ndarray, order: np.ndarray, recv_d8: np.ndarray,
                    weights: np.ndarray, step: float) -> np.ndarray:
    """Akumulacja D-infinity (podział na dwóch odbiorców); na płaskich – odbiorca D8."""
    h, w = filled.shape
    s, kc, kd, frac = dinf_weights(filled, step)
    rank = np.empty(h * w, dtype=np.int64)
    rank[order] = np.arange(h * w)
    ii, jj = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")

    def target(k):
        a, b = ii + D8_DI[k], jj + D8_DJ[k]
        ok = (a >= 0) & (a < h) & (b >= 0) & (b < w)
        return np.where(ok, a * w + b, -1).ravel()

    t1, t2 = target(kc), target(kd)
    f2 = frac.ravel()
    sl = s.ravel()
    acc = weights.ravel().astype(float).copy()
    rl, t1l, t2l, f2l, sll, rkl = (recv_d8.tolist(), t1.tolist(), t2.tolist(), f2.tolist(),
                                   sl.tolist(), rank.tolist())
    al = acc.tolist()
    for c in order[::-1].tolist():
        a = al[c]
        rc = rkl[c]
        if sll[c] > 1e-9:
            x1, x2, p2 = t1l[c], t2l[c], f2l[c]
            ok1 = x1 >= 0 and rkl[x1] < rc and p2 < 1
            ok2 = x2 >= 0 and rkl[x2] < rc and p2 > 0
            if ok1 and ok2:
                al[x1] += a * (1 - p2)
                al[x2] += a * p2
                continue
            if ok1:
                al[x1] += a
                continue
            if ok2:
                al[x2] += a
                continue
        r = rl[c]
        if r >= 0:
            al[r] += a
    return np.array(al).reshape(h, w)


# --------------------------------------------------------------------------------------
# Wektoryzacja (raster → poligony) i GeoJSON
# --------------------------------------------------------------------------------------

def mask_to_rings(mask: np.ndarray) -> list[list[list[tuple[int, int]]]]:
    """Obrys maski po krawędziach komórek. Wierzchołki w narożnikach (wiersz, kolumna).
    Zwraca listę poligonów: [pierścień zewnętrzny CCW, dziury CW...]."""
    h, w = mask.shape
    m = np.pad(mask, 1)
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add(a, b):
        edges.setdefault(a, []).append(b)

    for i, j in zip(*np.nonzero(mask)):
        pi, pj = i + 1, j + 1
        if not m[pi + 1, pj]:   # dół: (i+1,j) → (i+1,j+1)
            add((i + 1, j), (i + 1, j + 1))
        if not m[pi, pj + 1]:   # prawo: (i+1,j+1) → (i,j+1)
            add((i + 1, j + 1), (i, j + 1))
        if not m[pi - 1, pj]:   # góra: (i,j+1) → (i,j)
            add((i, j + 1), (i, j))
        if not m[pi, pj - 1]:   # lewo: (i,j) → (i+1,j)
            add((i, j), (i + 1, j))

    def turn_rank(d_in, d_out):
        # w układzie (x=kolumna, y=−wiersz): preferuj skręt w lewo → stykające się po skosie
        # komórki dają osobne poligony
        ax, ay = d_in[1], -d_in[0]
        bx, by = d_out[1], -d_out[0]
        cross = ax * by - ay * bx
        return 0 if cross > 0 else (1 if cross == 0 else 2)

    rings = []
    while edges:
        start = next(iter(edges))
        nxt = edges[start].pop()
        if not edges[start]:
            del edges[start]
        ring = [start, nxt]
        prev, cur = start, nxt
        while cur != start:
            outs = edges[cur]
            d_in = (cur[0] - prev[0], cur[1] - prev[1])
            outs.sort(key=lambda o: turn_rank(d_in, (o[0] - cur[0], o[1] - cur[1])))
            nb = outs.pop(0)
            if not outs:
                del edges[cur]
            prev, cur = cur, nb
            ring.append(cur)
        # usuń wierzchołki współliniowe
        pts = ring[:-1]
        simp = []
        for k in range(len(pts)):
            p0, p1, p2 = pts[k - 1], pts[k], pts[(k + 1) % len(pts)]
            if (p1[0] - p0[0]) * (p2[1] - p1[1]) != (p1[1] - p0[1]) * (p2[0] - p1[0]):
                simp.append(p1)
        simp.append(simp[0])
        rings.append(simp)

    def signed(r):  # w układzie x=kolumna, y=−wiersz
        x = np.array([p[1] for p in r], float)
        y = -np.array([p[0] for p in r], float)
        return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(y[:-1], x[1:]))

    outers = [r for r in rings if signed(r) > 0]
    holes = [r for r in rings if signed(r) < 0]
    polys = [[o] for o in outers]
    for hole in holes:
        # punkt próbny: środek komórki po prawej stronie pierwszej krawędzi dziury
        # (wnętrze maski jest po lewej, więc po prawej leży komórka „pusta” wewnątrz dziury)
        (r0, c0), (r1, c1) = hole[0], hole[1]
        x0, y0, x1, y1 = c0, -r0, c1, -r1
        ln = math.hypot(x1 - x0, y1 - y0)
        dx, dy = (x1 - x0) / ln, (y1 - y0) / ln
        px, py = x0 + dx * 0.5 + dy * 0.5, y0 + dy * 0.5 - dx * 0.5
        for poly in sorted(polys, key=lambda pl: signed(pl[0])):  # najmniejszy zawierający
            ring = np.array([[q[1], -q[0]] for q in poly[0]], float)
            if points_in_polygons(np.array([px]), np.array([py]), [[ring]])[0]:
                poly.append(hole)
                break
    return polys


@dataclass
class _Geo:
    grid: Grid

    def corner_lonlat(self, ring):
        g = self.grid
        rr = np.array([p[0] for p in ring], float)
        cc = np.array([p[1] for p in ring], float)
        e = g.e0 + (cc - 0.5) * g.step
        n = g.n0 - (rr - 0.5) * g.step
        lon, lat = puwg1992_to_wgs84(e, n)
        return [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]

    def en_lonlat(self, e, n):
        lon, lat = puwg1992_to_wgs84(np.atleast_1d(e), np.atleast_1d(n))
        return [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]

    def cell_lonlat(self, i, j):
        e, n = self.grid.cell_to_en(i, j)
        return self.en_lonlat(e, n)[0]

    def mask_geometry(self, mask):
        polys = mask_to_rings(mask)
        if not polys:
            return None
        coords = [[self.corner_lonlat(r) for r in poly] for poly in polys]
        return {"type": "MultiPolygon", "coordinates": coords}


def _feature(geom, **props):
    return {"type": "Feature", "geometry": geom, "properties": props}


def _r(x, nd=2):
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


# --------------------------------------------------------------------------------------
# Rdzeń analizy
# --------------------------------------------------------------------------------------

@dataclass
class TerrainResult:
    facts: dict
    geojson: dict
    rasters: dict = field(default_factory=dict)
    grid: Grid | None = None
    polygons: Polygons | None = None


def analyze_surface(z: np.ndarray, step: float, inside: np.ndarray,
                    grid: Grid | None = None, params: dict | None = None,
                    polygons: Polygons | None = None) -> TerrainResult:
    """Pełna analiza na gotowej siatce wysokości (wiersz 0 = północ).

    z – wysokości [m], step – krok [m], inside – maska komórek działki.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    t0 = time.perf_counter()
    z = np.asarray(z, dtype=float)
    inside = np.asarray(inside, dtype=bool)
    h, w = z.shape
    if grid is None:
        grid = Grid(e0=500000.0, n0=500000.0 + (h - 1) * step, step=step, nrows=h, ncols=w)
    cell_a = step * step
    geo = _Geo(grid)
    if not inside.any():
        raise ValueError("Działka nie obejmuje żadnej komórki siatki – zmniejsz krok.")

    # 1. wygładzenie mikrorzeźby
    sigma_cells = p["smooth_sigma_m"] / step if p["smooth_sigma_m"] else 0.0
    zs = gaussian_smooth(z, sigma_cells)

    # 2. spadek, ekspozycja, krzywizna, TPI
    slope, aspect, dzde, dzdn = slope_aspect(zs, step)
    lap = laplacian(zs, step)
    tpi_r = max(2, int(round(p["tpi_radius_m"] / step)))
    tp = tpi(zs, tpi_r)

    # 3. wypełnienie zagłębień + kierunki + akumulacja
    filled, order, parent = priority_flood(zs)
    recv = d8_receivers(filled, parent, step)
    ones = np.ones_like(zs)
    acc_cells = accumulate_d8(recv, order, ones)                 # liczba komórek zlewni
    acc_m2 = acc_cells * cell_a
    acc_parcel_m2 = accumulate_d8(recv, order, inside.astype(float)) * cell_a
    if p["flow_method_twi"] == "dinf":
        acc_twi_m2 = accumulate_dinf(filled, order, recv, ones, step) * cell_a
    else:
        acc_twi_m2 = acc_m2

    # 4. TWI = ln(a / tan β), a = powierzchnia zlewni / szerokość komórki
    tanb = np.maximum(slope / 100.0, p["twi_min_tan"])
    twi = np.log((acc_twi_m2 / step) / tanb)

    # 5. zagłębienia bez odpływu
    depth = filled - zs
    dlab, nd = label(depth > 0.01, conn=8)
    dep_stats = []
    keep_lab = np.zeros_like(dlab)
    for k in range(1, nd + 1):
        mk = dlab == k
        dmax = float(depth[mk].max())
        area = float(mk.sum() * cell_a)
        if dmax < p["depression_min_depth_m"] or area < p["depression_min_area_m2"]:
            continue
        idx = len(dep_stats) + 1
        keep_lab[mk] = idx
        flat_i = int(np.flatnonzero((depth * mk).ravel() == (depth * mk).max())[0])
        di_, dj_ = divmod(flat_i, w)
        dep_stats.append({
            "id": idx, "mask": mk,
            "max_depth_m": dmax, "area_m2": area,
            "volume_m3": float(depth[mk].sum() * cell_a),
            "area_in_parcel_m2": float((mk & inside).sum() * cell_a),
            "deepest_cell": (di_, dj_),
            "deepest_in_parcel": bool(inside[di_, dj_]),
            "spill_level_m": float(filled[mk].max()),
        })
    # zlewnie zagłębień: komórka dziedziczy etykietę odbiorcy (odbiorca zdjęty wcześniej)
    clab = keep_lab.ravel().copy()
    for c in order.tolist():
        if clab[c] == 0:
            r = recv[c]
            if r >= 0:
                clab[c] = clab[r]
    clab = clab.reshape(h, w)
    for d in dep_stats:
        d["catchment_m2"] = float((clab == d["id"]).sum() * cell_a)
        d["catchment_in_parcel_m2"] = float(((clab == d["id"]) & inside).sum() * cell_a)
    deps_parcel = [d for d in dep_stats if d["area_in_parcel_m2"] > 0]

    # 6. strefy (kolejność ważności: mokry dołek > sucha górka > stok > płasko)
    wet = (keep_lab > 0) | ((tp <= p["wet_tpi_m"]) & (slope < p["flat_slope_pct"])) | \
          ((twi >= p["twi_wet"]) & (slope < p["flat_slope_pct"]))
    hill = (tp >= p["hill_tpi_m"]) & (lap < 0)
    zones = np.full((h, w), ZONE_FLAT, dtype=np.int8)
    zones[slope >= p["flat_slope_pct"]] = ZONE_SLOPE
    zones[hill] = ZONE_HILL
    zones[wet] = ZONE_WET

    hill_lab, nh = label(hill & inside)
    min_cells = max(1, int(math.ceil(p["min_zone_area_m2"] / cell_a)))
    hills = []
    for k in range(1, nh + 1):
        mk = hill_lab == k
        if mk.sum() < min_cells:
            continue
        zi = np.where(mk, zs, -np.inf)
        ti, tj = np.unravel_index(int(zi.argmax()), zi.shape)
        hills.append({"area_m2": float(mk.sum() * cell_a), "top_cell": (int(ti), int(tj)),
                      "top_elev_m": float(z[ti, tj]), "tpi_max_m": float(tp[mk].max())})
    hills.sort(key=lambda d: -d["area_m2"])

    # 7. wyjścia wody z działki (komórka w działce, której odbiorca D8 jest poza nią)
    recv2 = recv.reshape(h, w)
    rec_in = np.zeros((h, w), dtype=bool)
    valid_r = recv2 >= 0
    rec_in[valid_r] = inside.ravel()[recv2[valid_r]]
    out_cells = inside & ~rec_in
    olab, no = label(out_cells)
    parcel_area = float(inside.sum() * cell_a)
    outlets = []
    for k in range(1, no + 1):
        mk = olab == k
        share = float(acc_parcel_m2[mk].sum() / parcel_area)
        ci = np.flatnonzero(mk.ravel())
        best = ci[np.argmax(acc_m2.ravel()[ci])]
        bi, bj = divmod(int(best), w)
        r = recv[best]
        if r >= 0:
            ri, rj = divmod(int(r), w)
        else:
            ri, rj = bi + (1 if bi == h - 1 else -1 if bi == 0 else 0), bj + (1 if bj == w - 1 else -1 if bj == 0 else 0)
        # kierunek: średnia wektorowa kierunków komórek wyjścia ważona akumulacją
        vx = vy = 0.0
        for c in ci:
            rc = recv[c]
            if rc < 0:
                continue
            a_i, a_j = divmod(int(c), w)
            b_i, b_j = divmod(int(rc), w)
            wgt = acc_parcel_m2.ravel()[c]
            dist = math.hypot(b_i - a_i, b_j - a_j)
            vx += wgt * (b_j - a_j) / dist
            vy += wgt * -(b_i - a_i) / dist
        az = math.degrees(math.atan2(vx, vy)) % 360
        e_b, n_b = grid.cell_to_en(bi, bj)
        e_r, n_r = grid.cell_to_en(ri, rj)
        outlets.append({
            "share_of_parcel": share,
            "parcel_area_drained_m2": float(acc_parcel_m2[mk].sum()),
            "total_upstream_m2": float(acc_m2[bi, bj]),
            "width_m": float(mk.sum() * step),
            "azimuth_deg": az,
            "cell": (bi, bj),
            "en": (float((e_b + e_r) / 2), float((n_b + n_r) / 2)),
        })
    outlets.sort(key=lambda d: -d["share_of_parcel"])
    main_outlets = [o for o in outlets if o["share_of_parcel"] >= p["outlet_min_share"]][:p["max_outlets"]]
    if not main_outlets and outlets:
        main_outlets = outlets[:1]

    # dopływ z zewnątrz: komórki spoza działki, których odbiorca jest w działce
    in_cells = ~inside & rec_in
    inflow_m2 = float(acc_m2[in_cells].sum())
    ilab, ni = label(in_cells)
    inlets = []
    for k in range(1, ni + 1):
        mk = ilab == k
        a = float(acc_m2[mk].sum())
        if a < max(0.05 * parcel_area, 5 * cell_a):
            continue
        ci = np.flatnonzero(mk.ravel())
        best = int(ci[np.argmax(acc_m2.ravel()[ci])])
        bi, bj = divmod(best, w)
        inlets.append({"upstream_m2": a, "cell": (bi, bj)})
    inlets.sort(key=lambda d: -d["upstream_m2"])

    # 8. główny kierunek spływu (średnia wektorowa gradientu w działce, ważona spadkiem)
    gx, gy = -dzde[inside], -dzdn[inside]  # wektor w dół stoku (E, N)
    mvx, mvy = float(gx.sum()), float(gy.sum())
    main_az = math.degrees(math.atan2(mvx, mvy)) % 360
    consistency = math.hypot(mvx, mvy) / max(float(np.hypot(gx, gy).sum()), 1e-12)

    # 9. propozycje
    proposals = []
    rain_m = p["rain_mm"] / 1000.0
    pond = None
    if deps_parcel:
        d = max(deps_parcel, key=lambda x: (x["volume_m3"], x["area_in_parcel_m2"]))
        inflow_gross = d["catchment_m2"] * rain_m
        inflow_run = inflow_gross * p["runoff_coeff"]
        pond = {
            "type": "oczko_w_zaglebieniu",
            "reason": "największe zagłębienie bez odpływu na działce – tu naturalnie zbiera się woda",
            "depression_id": d["id"],
            "cell": d["deepest_cell"],
            "depression_area_m2": d["area_m2"],
            "depression_area_in_parcel_m2": d["area_in_parcel_m2"],
            "max_depth_m": d["max_depth_m"],
            "storage_volume_m3": d["volume_m3"],
            "catchment_m2": d["catchment_m2"],
            "inflow_20mm_gross_m3": inflow_gross,
            "inflow_20mm_runoff_m3": inflow_run,
            "suggested_pond_area_m2": min(d["area_in_parcel_m2"],
                                          max(inflow_run / p["pond_depth_m"], 25.0)),
        }
    elif main_outlets:
        o = main_outlets[0]
        catch = o["total_upstream_m2"]
        inflow_gross = catch * rain_m
        inflow_run = inflow_gross * p["runoff_coeff"]
        pond = {
            "type": "oczko_przy_odplywie",
            "reason": "brak wyraźnego zagłębienia – najlepsze miejsce to najniższy punkt "
                      "działki przy głównym miejscu odpływu wody",
            "cell": o["cell"],
            "depression_area_m2": 0.0, "depression_area_in_parcel_m2": 0.0,
            "max_depth_m": 0.0, "storage_volume_m3": 0.0,
            "catchment_m2": catch,
            "inflow_20mm_gross_m3": inflow_gross,
            "inflow_20mm_runoff_m3": inflow_run,
            "suggested_pond_area_m2": max(inflow_run / p["pond_depth_m"], 25.0),
        }
    if pond:
        proposals.append(pond)

    E, N = grid.centers()
    steep = inside & (slope > p["buffer_strip_slope_pct"])
    steep_share = float(steep.sum() / inside.sum())
    strips = []
    if steep_share >= p["buffer_strip_min_share"] and steep.sum() >= 3 and polygons is not None:
        # oś główna = kierunek spływu na stromej części działki
        sx, sy = float(-dzde[steep].sum()), float(-dzdn[steep].sum())
        az_s = math.degrees(math.atan2(sx, sy)) % 360
        ux, uy = math.sin(math.radians(az_s)), math.cos(math.radians(az_s))
        vx_, vy_ = -uy, ux
        ce, cn = float(E[inside].mean()), float(N[inside].mean())
        s_vals = (E[steep] - ce) * ux + (N[steep] - cn) * uy
        lo, hi = np.quantile(s_vals, [0.05, 0.95])
        extent = float(hi - lo)
        n_strips = max(1, int(extent // p["buffer_strip_spacing_m"]))
        qs = [0.7] if n_strips == 1 else list(np.linspace(0.3, 0.8, n_strips))
        allpts = np.vstack([r for pl in polygons for r in pl])
        half = float(np.hypot(*(allpts.max(0) - allpts.min(0))))
        for q in qs:
            s_star = float(np.quantile(s_vals, q))
            t = np.arange(-half, half, step / 2)
            pe = ce + s_star * ux + t * vx_
            pn = cn + s_star * uy + t * vy_
            ins = points_in_polygons(pe, pn, polygons)
            # najdłuższy ciągły odcinek wewnątrz działki
            best_run, cur = (0, -1), None
            for k, v in enumerate(ins):
                if v and cur is None:
                    cur = k
                if (not v or k == len(ins) - 1) and cur is not None:
                    end = k if v else k - 1
                    if end - cur > best_run[1] - best_run[0]:
                        best_run = (cur, end)
                    cur = None
            a, b = best_run
            if b <= a:
                continue
            length = float((b - a) * step / 2)
            if length < 20:
                continue
            ia = np.clip(np.round((grid.n0 - pn[a:b + 1]) / step).astype(int), 0, h - 1)
            ja = np.clip(np.round((pe[a:b + 1] - grid.e0) / step).astype(int), 0, w - 1)
            strips.append({
                "type": "pas_buforowy",
                "reason": f"spadek > {p['buffer_strip_slope_pct']:.0f} % na "
                          f"{steep_share * 100:.0f} % działki – pas w poprzek spływu hamuje wodę i erozję",
                "line_en": [(float(pe[a]), float(pn[a])), (float(pe[b]), float(pn[b]))],
                "length_m": length,
                "width_m": p["buffer_strip_width_m"],
                "area_m2": length * p["buffer_strip_width_m"],
                "flow_azimuth_deg": az_s,
                "mean_slope_pct": float(slope[ia, ja].mean()),
                "upslope_parcel_area_m2": float(acc_parcel_m2[ia, ja].sum()),
            })
    proposals.extend(strips)

    # 10. statystyki działki
    zin, sin_ = z[inside], slope[inside]
    zone_share = {ZONE_KEYS[k]: float((zones[inside] == k).mean()) for k in ZONE_KEYS}
    main_name, main_short = az_name(main_az)
    largest = None
    if deps_parcel:
        d = max(deps_parcel, key=lambda x: x["volume_m3"])
        largest = {
            "area_m2": _r(d["area_m2"], 0), "area_in_parcel_m2": _r(d["area_in_parcel_m2"], 0),
            "max_depth_m": _r(d["max_depth_m"]), "volume_m3": _r(d["volume_m3"], 1),
            "catchment_m2": _r(d["catchment_m2"], 0),
            "location_lonlat": geo.cell_lonlat(*d["deepest_cell"]),
        }
    share_to_deps = float(sum(d["catchment_in_parcel_m2"] for d in deps_parcel) / parcel_area)

    def outlet_fact(o):
        nm, sh = az_name(o["azimuth_deg"])
        return {
            "location_lonlat": geo.en_lonlat(*o["en"])[0],
            "direction": nm, "direction_short": sh, "azimuth_deg": _r(o["azimuth_deg"], 0),
            "share_of_parcel_pct": _r(100 * o["share_of_parcel"], 1),
            "parcel_area_drained_m2": _r(o["parcel_area_drained_m2"], 0),
            "total_upstream_m2": _r(o["total_upstream_m2"], 0),
            "width_m": _r(o["width_m"], 0),
        }

    def proposal_fact(pr):
        if pr["type"] == "pas_buforowy":
            return {
                "type": pr["type"], "reason": pr["reason"],
                "line_lonlat": [geo.en_lonlat(*xy)[0] for xy in pr["line_en"]],
                "length_m": _r(pr["length_m"], 0), "width_m": _r(pr["width_m"], 0),
                "area_m2": _r(pr["area_m2"], 0),
                "flow_azimuth_deg": _r(pr["flow_azimuth_deg"], 0),
                "mean_slope_pct": _r(pr["mean_slope_pct"], 1),
            }
        return {
            "type": pr["type"], "reason": pr["reason"],
            "location_lonlat": geo.cell_lonlat(*pr["cell"]),
            "depression_area_m2": _r(pr["depression_area_m2"], 0),
            "max_depth_m": _r(pr["max_depth_m"]),
            "storage_volume_m3": _r(pr["storage_volume_m3"], 1),
            "catchment_m2": _r(pr["catchment_m2"], 0),
            "rain_mm": p["rain_mm"],
            "inflow_gross_m3": _r(pr["inflow_20mm_gross_m3"], 1),
            "runoff_coeff": p["runoff_coeff"],
            "inflow_runoff_m3": _r(pr["inflow_20mm_runoff_m3"], 1),
            "suggested_pond_area_m2": _r(pr["suggested_pond_area_m2"], 0),
            "pond_depth_m": p["pond_depth_m"],
        }

    facts = {
        "parcel_area_ha": _r(parcel_area / 1e4, 3),
        "grid_step_m": step,
        "grid_cells": int(h * w), "parcel_cells": int(inside.sum()),
        "smoothing_sigma_m": p["smooth_sigma_m"],
        "elev_min_m": _r(zin.min(), 1), "elev_max_m": _r(zin.max(), 1),
        "elev_mean_m": _r(zin.mean(), 1), "relief_m": _r(zin.max() - zin.min(), 1),
        "slope_mean_pct": _r(sin_.mean(), 1), "slope_median_pct": _r(np.median(sin_), 1),
        "slope_p90_pct": _r(np.quantile(sin_, 0.9), 1), "slope_max_pct": _r(sin_.max(), 1),
        "steep_share_pct": _r(100 * steep_share, 1),
        "main_flow_azimuth_deg": _r(main_az, 0), "main_flow_direction": main_name,
        "main_flow_direction_short": main_short,
        "flow_consistency": _r(consistency, 2),  # 1 = cała działka spada w jedną stronę
        "zone_share_pct": {k: _r(100 * v, 1) for k, v in zone_share.items()},
        "n_hills": len(hills),
        "hills": [{"area_m2": _r(hh_["area_m2"], 0), "top_elev_m": _r(hh_["top_elev_m"], 1),
                   "tpi_max_m": _r(hh_["tpi_max_m"]),
                   "location_lonlat": geo.cell_lonlat(*hh_["top_cell"])} for hh_ in hills[:5]],
        "n_depressions": len(deps_parcel),
        "depressions_total_volume_m3": _r(sum(d["volume_m3"] for d in deps_parcel), 1),
        "largest_depression": largest,
        "parcel_share_draining_to_depressions_pct": _r(100 * share_to_deps, 1),
        "twi_mean": _r(twi[inside].mean(), 2), "twi_p90": _r(np.quantile(twi[inside], 0.9), 2),
        "n_outlets": len(main_outlets),
        "outlets": [outlet_fact(o) for o in main_outlets],
        "inflow_from_outside_m2": _r(inflow_m2, 0),
        "inflow_from_outside_ratio": _r(inflow_m2 / parcel_area, 2),
        "proposals": [proposal_fact(pr) for pr in proposals],
        "thresholds": {k: p[k] for k in (
            "flat_slope_pct", "hill_tpi_m", "wet_tpi_m", "twi_wet", "tpi_radius_m",
            "depression_min_depth_m", "depression_min_area_m2", "buffer_strip_slope_pct",
            "buffer_strip_min_share", "outlet_min_share", "rain_mm", "runoff_coeff")},
        "method": {"flow": "D8 (kierunki, wyjścia) + D-infinity (TWI)" if p["flow_method_twi"] == "dinf"
                   else "D8", "fill": "priority-flood (Barnes 2014)", "slope": "Horn 3×3"},
        "compute_s": None,
    }

    # 11. GeoJSON (EPSG:4326)
    feats = []
    if polygons is not None:
        coords = []
        for poly in polygons:
            coords.append([geo.en_lonlat(r[:, 0], r[:, 1]) for r in poly])
        feats.append(_feature({"type": "MultiPolygon", "coordinates": coords}, layer="parcel"))
    for k, key in ZONE_KEYS.items():
        g = geo.mask_geometry((zones == k) & inside)
        if g:
            feats.append(_feature(g, layer="zone", zone=key, label=ZONE_LABELS[k],
                                  share_pct=_r(100 * zone_share[key], 1)))
    for d in deps_parcel:
        g = geo.mask_geometry(d["mask"])
        if g:
            feats.append(_feature(g, layer="depression", id=d["id"],
                                  max_depth_m=_r(d["max_depth_m"]), area_m2=_r(d["area_m2"], 0),
                                  volume_m3=_r(d["volume_m3"], 1),
                                  catchment_m2=_r(d["catchment_m2"], 0)))
    # strzałki spływu (siatka rzadsza, ~8 strzałek na bok działki)
    side = math.sqrt(parcel_area)
    kblk = max(1, int(round(max(2 * step, side / 8) / step)))
    arrows = []
    for i0 in range(0, h, kblk):
        for j0 in range(0, w, kblk):
            ic, jc = min(i0 + kblk // 2, h - 1), min(j0 + kblk // 2, w - 1)
            if not inside[ic, jc]:
                continue
            blk = (slice(i0, i0 + kblk), slice(j0, j0 + kblk))
            ge, gn = float(-dzde[blk].mean()), float(-dzdn[blk].mean())
            sp = 100 * math.hypot(ge, gn)
            if sp < 0.5:
                continue
            ue, un = ge / math.hypot(ge, gn), gn / math.hypot(ge, gn)
            L = 0.8 * kblk * step
            ec, nc = grid.cell_to_en(ic, jc)
            tail = (float(ec) - ue * L / 2, float(nc) - un * L / 2)
            head = (float(ec) + ue * L / 2, float(nc) + un * L / 2)
            az = math.degrees(math.atan2(ue, un)) % 360
            arrows.append((tail, head, az, sp, float(acc_m2[ic, jc])))
            feats.append(_feature({"type": "LineString",
                                   "coordinates": geo.en_lonlat(np.array([tail[0], head[0]]),
                                                                np.array([tail[1], head[1]]))},
                                  layer="flow_arrow", azimuth_deg=_r(az, 0), slope_pct=_r(sp, 1),
                                  upstream_m2=_r(acc_m2[ic, jc], 0)))
    # główne ścieżki spływu (D8, akumulacja >= próg)
    thr = max(8 * cell_a, 0.05 * parcel_area)
    stream = acc_m2 >= thr
    near = dilate(inside, 1)
    donors = np.bincount(recv[stream.ravel() & (recv >= 0)], minlength=h * w).reshape(h, w)
    heads = stream & (donors == 0)
    visited = np.zeros(h * w, dtype=bool)
    paths = []
    for c0 in np.flatnonzero(heads.ravel()):
        line = [int(c0)]
        c = int(c0)
        while True:
            visited[c] = True
            r = int(recv[c])
            if r < 0:
                break
            line.append(r)
            if visited[r] or not stream.ravel()[r]:
                break
            c = r
        # przytnij do okolicy działki
        cur: list[int] = []
        for c in line + [-1]:
            if c >= 0 and near.ravel()[c]:
                cur.append(c)
            else:
                if len(cur) >= 2:
                    paths.append(cur)
                cur = []
    for pth in paths:
        ii_ = np.array([c // w for c in pth])
        jj_ = np.array([c % w for c in pth])
        e_, n_ = grid.cell_to_en(ii_, jj_)
        feats.append(_feature({"type": "LineString", "coordinates": geo.en_lonlat(e_, n_)},
                              layer="flow_path", max_upstream_m2=_r(acc_m2.ravel()[pth].max(), 0)))
    for k, o in enumerate(main_outlets):
        f = outlet_fact(o)
        feats.append(_feature({"type": "Point", "coordinates": f["location_lonlat"]},
                              layer="outlet", rank=k + 1, **{kk: v for kk, v in f.items()
                                                             if kk != "location_lonlat"}))
    for il in inlets[:5]:
        feats.append(_feature({"type": "Point", "coordinates": geo.cell_lonlat(*il["cell"])},
                              layer="inlet", upstream_m2=_r(il["upstream_m2"], 0)))
    for hh_ in hills[:5]:
        feats.append(_feature({"type": "Point", "coordinates": geo.cell_lonlat(*hh_["top_cell"])},
                              layer="hill_top", area_m2=_r(hh_["area_m2"], 0),
                              top_elev_m=_r(hh_["top_elev_m"], 1)))
    for pr in proposals:
        pf = proposal_fact(pr)
        if pr["type"] == "pas_buforowy":
            geom = {"type": "LineString", "coordinates": pf.pop("line_lonlat")}
        else:
            geom = {"type": "Point", "coordinates": pf.pop("location_lonlat")}
        feats.append(_feature(geom, layer="proposal", **pf))

    facts["compute_s"] = _r(time.perf_counter() - t0, 3)
    rasters = {
        "z": z, "z_smooth": zs, "filled": filled, "slope_pct": slope, "aspect_deg": aspect,
        "tpi": tp, "twi": twi, "acc_m2": acc_m2, "acc_parcel_m2": acc_parcel_m2,
        "depth": depth, "depressions": keep_lab, "zones": zones, "inside": inside,
        "recv": recv.reshape(h, w), "arrows": arrows, "paths": paths,
        "outlets": main_outlets, "proposals": proposals, "hills": hills,
    }
    return TerrainResult(facts=facts, geojson={"type": "FeatureCollection", "features": feats},
                         rasters=rasters, grid=grid, polygons=polygons)


# --------------------------------------------------------------------------------------
# Wejście „aplikacyjne”
# --------------------------------------------------------------------------------------

def analyze_parcel(parcel: Any, params: dict | None = None) -> TerrainResult:
    """parcel: ID działki ULDK (np. '201305_2.0038.6/1') albo geometria (WKT EPSG:2180)."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    t0 = time.perf_counter()
    parcel_id = None
    if isinstance(parcel, str) and "(" not in parcel:
        parcel_id = parcel
        polys = parse_wkt(fetch_parcel_wkt(parcel_id, timeout=p["uldk_timeout_s"]))
    else:
        polys = to_polygons(parcel)
    t_uldk = time.perf_counter() - t0

    area = polygons_area(polys)
    allpts = np.vstack([r for pl in polys for r in pl])
    bw, bh = allpts.max(0) - allpts.min(0) + 2 * p["buffer_m"]
    step = choose_step(area, float(bw), float(bh), p)
    grid = make_grid(polys, p["buffer_m"], step)
    E, N = grid.centers()
    inside = points_in_polygons(E, N, polys)
    if not inside.any():  # bardzo wąska działka – zagęść siatkę
        step = max(1.0, step / 3)
        grid = make_grid(polys, p["buffer_m"], step)
        E, N = grid.centers()
        inside = points_in_polygons(E, N, polys)

    t1 = time.perf_counter()
    hvals, nmt_info = fetch_heights(E.ravel(), N.ravel(), p)
    t_nmt = time.perf_counter() - t1
    if nmt_info["missing_share"] > 0.3:
        raise RuntimeError(f"NMT: brak {nmt_info['missing_share'] * 100:.0f} % wysokości "
                           f"({nmt_info['failed_requests']}/{nmt_info['requests']} zapytań nieudanych)")
    z, n_spikes = despike(hvals.reshape(grid.nrows, grid.ncols))
    nmt_info["spikes_removed"] = n_spikes
    nmt_info["missing_share"] = float(np.isnan(z).mean())
    z = fill_nans(z)

    res = analyze_surface(z, step, inside, grid=grid, params=p, polygons=polys)
    total = time.perf_counter() - t0
    f = res.facts
    f["parcel_id"] = parcel_id
    f["parcel_area_ha"] = _r(area / 1e4, 3)  # z obrysu (dokładniej niż z komórek)
    f["nmt_points"] = int(E.size)
    f["nmt_requests"] = nmt_info["requests"]
    f["nmt_failed_requests"] = nmt_info["failed_requests"]
    f["nmt_missing_pct"] = _r(100 * nmt_info["missing_share"], 2)
    f["nmt_zero_values"] = nmt_info["zero_values"]
    f["nmt_spikes_removed"] = nmt_info["spikes_removed"]
    f["confidence"] = "wysoka" if nmt_info["missing_share"] < 0.01 else (
        "średnia" if nmt_info["missing_share"] < 0.1 else "niska")
    f["timing_s"] = {"uldk": _r(t_uldk, 2), "nmt": _r(t_nmt, 2),
                     "compute": f["compute_s"], "total": _r(total, 2)}
    f["sources"] = [
        {"name": "ULDK GUGiK", "url": ULDK_URL, "what": "obrys działki"},
        {"name": "NMT GUGiK", "url": NMT_URL,
         "what": f"wysokości (±0,1 m) w siatce {step:g} m, bufor {p['buffer_m']:.0f} m"},
    ]
    f["limitations"] = [
        f"Siatka {step:g} m – formy mniejsze niż ~{2 * step:g} m (bruzdy, koleiny, rowki) są niewidoczne.",
        "Wysokości podawane co 0,1 m – przy małych spadkach kierunek spływu jest niepewny; "
        f"stosujemy wygładzenie σ = {p['smooth_sigma_m']:g} m.",
        f"Bufor {p['buffer_m']:.0f} m: zlewnia sięgająca dalej (długie stoki) jest niedoszacowana.",
        "Model nie zna drenażu, rowów, przepustów, dróg ani orki wzdłuż/w poprzek stoku – "
        "rzeczywisty odpływ może iść inaczej.",
        "Objętości zagłębień i dopływu to szacunek rzędu wielkości, nie projekt.",
    ]
    return res


def terrain_facts(parcel_geom: Any, params: dict | None = None) -> dict:
    """Fakty o terenie działki (do reguł rekomendacji). parcel_geom: WKT EPSG:2180 / ID ULDK."""
    return analyze_parcel(parcel_geom, params).facts


def terrain_layers(parcel_geom: Any, params: dict | None = None) -> dict:
    """Warstwy na mapę: GeoJSON FeatureCollection w EPSG:4326 (właściwość 'layer')."""
    return analyze_parcel(parcel_geom, params).geojson
