"""C5 – kandydaci na działki demo BEZ ULDK: punkt (lon, lat) → kategoria IUNG, kompleks z mapy
glebowo-rolniczej, ortofotomapa (PNG), rzeźba z NMT, najbliższa stacja IMGW (indeks offline z C4).

    python research/demo/candidates.py

Numery działek dociągniemy później z hotspotu (ULDK GetParcelByXY dla zapisanych współrzędnych).
Wszystkie zapytania HTTP – bez śledzenia przekierowań (GUGiK przy limicie serwuje 302 → ~126 MB).
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "precip"))
import precip as P  # noqa: E402  (indeks stacji IMGW offline)

OUT = HERE / "out"
UA = "zatrzymaj-wode-research/0.1"

IUNG_WMS = "https://sgeo.iung.pl/geoserver/Susza/wms"
SOIL_WMS = "https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer"
ORTO_WMS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution"
NMT_URL = "https://services.gugik.gov.pl/nmt/"

IUNG_NAMES = {1: "I – bardzo podatna na suszę", 2: "II – podatna", 3: "III – średnio podatna",
              4: "IV – mało podatna", 5: "gleby organiczne", 11: "las", 12: "woda", 13: "zabudowa",
              14: "drogi/nieużytki"}
KOMPLEKSY = {"1": "pszenny bardzo dobry", "2": "pszenny dobry", "3": "pszenny wadliwy",
             "4": "żytni bardzo dobry", "5": "żytni dobry", "6": "żytni słaby", "7": "żytni bardzo słaby",
             "8": "zbożowo-pastewny mocny", "9": "zbożowo-pastewny słaby", "1z": "użytki zielone b. dobre",
             "2z": "użytki zielone średnie", "3z": "użytki zielone słabe"}

# Kandydaci: scenariusz demo → punkt na polu (sprawdzany ortofotomapą)
CANDIDATES = [
    {"id": "piasek-zyto", "scenariusz": "Piasek – „nie siej pszenicy, siej żyto”", "region": "mazowieckie, Kurpie",
     "lon": 21.4590, "lat": 53.2205},
    {"id": "czarnoziem-pszenica", "scenariusz": "Najlepsza gleba – pszenica, susza mimo dobrej gleby",
     "region": "lubelskie, Grzęda Horodelska (czarnoziemy)", "lon": 23.8650, "lat": 50.8200},
    {"id": "kujawy-susza", "scenariusz": "Dobra gleba, mało deszczu – Kujawy (najsuchszy region PL)",
     "region": "kujawsko-pomorskie, k. Inowrocławia", "lon": 18.2400, "lat": 52.7300},
    {"id": "less-erozja", "scenariusz": "Lessowy stok – erozja, pas buforowy w poprzek spływu",
     "region": "lubelskie, Płaskowyż Nałęczowski", "lon": 22.1700, "lat": 51.3155},
    {"id": "pojezierze-oczko", "scenariusz": "Zagłębienia bez odpływu – oczko wodne w dołku",
     "region": "warmińsko-mazurskie, Pojezierze Mrągowskie", "lon": 21.3870, "lat": 53.8709},
    {"id": "zulawy-mady", "scenariusz": "Żuławy – ciężkie mady, płasko, nadmiar wody / melioracja",
     "region": "pomorskie, Żuławy Wiślane", "lon": 19.0300, "lat": 54.1600},
    {"id": "pogorze-stok", "scenariusz": "Stok na Pogórzu – spływ, sucha górka, retencja",
     "region": "podkarpackie, Pogórze Dynowskie", "lon": 22.3000, "lat": 49.8400},
]

# ---------------------------------------------------------------------------------- HTTP bez przekierowań


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def get(url: str, timeout: float = 15.0, max_bytes: int = 3_000_000, retries: int = 2) -> tuple[bytes, float]:
    last = None
    for a in range(retries + 1):
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Connection": "close"})
            with _OPENER.open(req, timeout=timeout) as r:
                body = r.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise RuntimeError("odpowiedź za duża")
            return body, time.monotonic() - t0
        except urllib.error.HTTPError as e:
            e.close()  # 3xx/4xx/5xx – treści nie czytamy
            last = f"HTTP {e.code}"
            if 300 <= e.code < 400:
                break
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(1 + a)
    raise RuntimeError(f"{last}: {url[:120]}")


# ---------------------------------------------------------------------------------- PL-1992 w przód

_A, _F = 6378137.0, 1 / 298.257222101
_N = _F / (2 - _F)
_AR = _A / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64)
_ALPHA = [_N / 2 - 2 / 3 * _N**2 + 5 / 16 * _N**3 + 41 / 180 * _N**4,
          13 / 48 * _N**2 - 3 / 5 * _N**3 + 557 / 1440 * _N**4,
          61 / 240 * _N**3 - 103 / 140 * _N**4,
          49561 / 161280 * _N**4]


def wgs84_to_puwg1992(lon, lat):
    """EPSG:4326 → EPSG:2180 (wschód, północ). Wzory Krügera (n^4)."""
    lon, lat = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    c = 2 * math.sqrt(_N) / (1 + _N)
    t = np.sinh(np.arctanh(np.sin(lat)) - c * np.arctanh(c * np.sin(lat)))
    dl = lon - math.radians(19.0)
    xi = np.arctan2(t, np.cos(dl))
    eta = np.arctanh(np.sin(dl) / np.sqrt(1 + t * t))
    e = eta + sum(a * np.cos(2 * j * xi) * np.sinh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    n = xi + sum(a * np.sin(2 * j * xi) * np.cosh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    return 500000 + 0.9993 * _AR * e, -5300000 + 0.9993 * _AR * n


# ---------------------------------------------------------------------------------- źródła


def iung(lon, lat):
    d = 0.0005
    q = urllib.parse.urlencode({
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo",
        "LAYERS": "Susza:katgl_landuse2024", "QUERY_LAYERS": "Susza:katgl_landuse2024",
        "CRS": "EPSG:4326", "BBOX": f"{lat - d},{lon - d},{lat + d},{lon + d}",  # lat,lon (WMS 1.3.0)
        "WIDTH": 11, "HEIGHT": 11, "I": 5, "J": 5, "INFO_FORMAT": "application/json"})
    body, dt = get(f"{IUNG_WMS}?{q}")
    feats = json.loads(body).get("features", [])
    code = int(feats[0]["properties"]["GRAY_INDEX"]) if feats else None
    return code, dt


def soil_map(lon, lat):
    d = 0.0005
    q = urllib.parse.urlencode({
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetFeatureInfo", "LAYERS": "0", "QUERY_LAYERS": "0",
        "CRS": "EPSG:4326", "BBOX": f"{lat - d},{lon - d},{lat + d},{lon + d}", "WIDTH": 11, "HEIGHT": 11,
        "I": 5, "J": 5, "INFO_FORMAT": "text/xml", "STYLES": ""})
    body, dt = get(f"{SOIL_WMS}?{q}")
    text = body.decode("utf-8", "replace")
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', text))
    return {k: attrs.get(k) for k in ("KOMPLEKS", "TYPPODTYP", "PODLOZE1", "PODLOZE2", "AKTUALNOSC")}, dt


def ortho_png(lon, lat, path: Path, half_m: float = 300, px: int = 360):
    e, n = wgs84_to_puwg1992(lon, lat)
    q = urllib.parse.urlencode({
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": "Raster", "STYLES": "",
        "CRS": "EPSG:2180", "BBOX": f"{n - half_m},{e - half_m},{n + half_m},{e + half_m}",  # północ,wschód
        "WIDTH": px, "HEIGHT": px, "FORMAT": "image/jpeg"})
    body, dt = get(f"{ORTO_WMS}?{q}", timeout=20)
    if not body[:3] == b"\xff\xd8\xff":
        raise RuntimeError("ortofotomapa: odpowiedź nie jest obrazem")
    path.write_bytes(body)
    return dt


def nmt_relief(lon, lat, half_m: float = 150, k: int = 7):
    """Siatka k×k punktów w kwadracie 2·half_m – różnica wysokości i średni spadek (GET ≤ 400 pkt)."""
    e, n = wgs84_to_puwg1992(lon, lat)
    off = np.linspace(-half_m, half_m, k)
    E, N = np.meshgrid(e + off, n + off)
    lst = ",".join(f"{nn:.1f} {ee:.1f}" for ee, nn in zip(E.ravel(), N.ravel()))  # x = PÓŁNOC, y = WSCHÓD
    body, dt = get(NMT_URL + "?" + urllib.parse.urlencode({"request": "GetHByPointList", "list": lst}),
                   max_bytes=200_000)
    h = np.array([float(t.split()[2]) for t in body.decode().strip().split(",")]).reshape(k, k)
    h[h == 0] = np.nan  # NMT: 0,0 = brak danych (C1)
    step = 2 * half_m / (k - 1)
    gy, gx = np.gradient(h, step)
    slope = 100 * np.hypot(gx, gy)
    return {"h_min": round(float(np.nanmin(h)), 1), "h_max": round(float(np.nanmax(h)), 1),
            "relief_m": round(float(np.nanmax(h) - np.nanmin(h)), 1),
            "slope_mean_pct": round(float(np.nanmean(slope)), 1),
            "slope_max_pct": round(float(np.nanmax(slope)), 1)}, dt


def main(ids: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    res_path = OUT / "candidates.json"
    results = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
    catalog, index = P.station_catalog(), P.load_index()
    from datetime import date
    for c in CANDIDATES:
        if ids and c["id"] not in ids:
            continue
        r = dict(c)
        for name, fn in (("iung", lambda: iung(c["lon"], c["lat"])), ("gleba", lambda: soil_map(c["lon"], c["lat"])),
                         ("teren", lambda: nmt_relief(c["lon"], c["lat"]))):
            try:
                r[name], r[f"{name}_s"] = fn()
                r[f"{name}_s"] = round(r[f"{name}_s"], 2)
            except RuntimeError as exc:
                r[name] = f"błąd: {exc}"
        try:
            r["orto_s"] = round(ortho_png(c["lon"], c["lat"], OUT / f"{c['id']}_orto.jpg"), 2)
            r["orto"] = f"out/{c['id']}_orto.jpg"
        except RuntimeError as exc:
            r["orto"] = f"błąd: {exc}"
        st = P.nearest_stations(c["lon"], c["lat"], n=3, max_km=50, start=date(2016, 1, 1),
                                end=date(2025, 12, 31), catalog=catalog, index=index)
        r["imgw"] = [(s.name, s.kind, s.dist_km) for s in st]
        results[c["id"]] = r
        print(c["id"], "| IUNG", r.get("iung"), "| gleba", r.get("gleba"), "| teren", r.get("teren"),
              "| IMGW", r["imgw"][:2], flush=True)
    res_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
