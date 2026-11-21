"""C5 – przesunięcie punktów kandydatów do środka pola (na ortofotomapie), żeby ULDK GetParcelByXY
trafił w działkę rolną, a nie w drogę / miedzę / granicę.

    python research/demo/field_center.py

Metoda (offline, na zapisanych ortofotomapach 600 × 600 m, 360 px → 1,67 m/px):
1. wygładzenie obrazu (średnia 5 × 5 px),
2. rozrost obszaru od punktu: sąsiednie piksele o kolorze bliskim średniej obszaru (próg ΔRGB),
   to przybliżenie jednego pola uprawnego (jednolita uprawa / jedna faza),
3. odległość każdego piksela obszaru od jego krawędzi (iteracyjna erozja) → nowy punkt = piksel
   najdalej od krawędzi (biegun niedostępności), w promieniu 150 m od punktu startowego,
4. zapis do out/candidates.json: lon, lat (nowe), lon_start/lat_start, odleglosc_od_krawedzi_m,
   powierzchnia_pola_ha (szac.), uwagi.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import candidates as C  # noqa: E402

OUT = HERE / "out"
HALF_M, PX = 300.0, 360
M_PER_PX = 2 * HALF_M / PX
TOL = 22.0           # próg różnicy koloru (RGB 0–255) przy rozroście
# progi dobrane po obejrzeniu obrysów: wąskie pasy pól (Pogórze) i pas obok dużego pola (Kurpie)
TOL_BY_ID = {"piasek-zyto": 18.0, "pogorze-stok": 14.0}
MAX_SHIFT_M = 150.0  # nowy punkt nie dalej niż 150 m od startowego (to samo pole)
MIN_EDGE_M = 25.0    # wymagany zapas od krawędzi pola


def box_blur(img: np.ndarray, r: int = 2) -> np.ndarray:
    p = np.pad(img, ((r, r), (r, r), (0, 0)), mode="edge")
    s = np.zeros_like(img, dtype=float)
    for di in range(2 * r + 1):
        for dj in range(2 * r + 1):
            s += p[di:di + img.shape[0], dj:dj + img.shape[1]]
    return s / (2 * r + 1) ** 2


def grow(img: np.ndarray, seed: tuple[int, int], tol: float) -> np.ndarray:
    h, w, _ = img.shape
    mask = np.zeros((h, w), bool)
    mask[seed] = True
    mean = img[seed].astype(float)
    frontier = [seed]
    n = 1
    while frontier:
        nxt = []
        for i, j in frontier:
            for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if 0 <= a < h and 0 <= b < w and not mask[a, b] and np.abs(img[a, b] - mean).max() <= tol:
                    mask[a, b] = True
                    nxt.append((a, b))
                    mean = (mean * n + img[a, b]) / (n + 1)
                    n += 1
        frontier = nxt
    return mask


def edge_distance(mask: np.ndarray) -> np.ndarray:
    """Odległość (w px, metryka szachownicowa) do najbliższego piksela spoza maski / brzegu obrazu."""
    d = np.zeros(mask.shape, int)
    cur = mask.copy()
    k = 0
    while cur.any():
        k += 1
        d[cur] = k
        p = np.pad(cur, 1, constant_values=False)
        cur = cur & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return d


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    path = OUT / "candidates.json"
    res = json.loads(path.read_text(encoding="utf-8"))
    for cid, r in res.items():
        img = mpimg.imread(OUT / f"{cid}_orto.jpg").astype(float)[..., :3]
        if img.max() <= 1.0:
            img *= 255
        sm = box_blur(img)
        c = PX // 2
        mask = grow(sm, (c, c), TOL_BY_ID.get(cid, TOL))
        dist = edge_distance(mask)
        ii, jj = np.mgrid[0:PX, 0:PX]
        within = np.hypot(ii - c, jj - c) * M_PER_PX <= MAX_SHIFT_M
        cand = np.where(mask & within, dist, 0)
        bi, bj = np.unravel_index(int(cand.argmax()), cand.shape)
        edge_m = float(cand[bi, bj] * M_PER_PX)
        start_edge_m = float(dist[c, c] * M_PER_PX)
        # przesunięcie w metrach → stopnie (wiersz rośnie na południe)
        de, dn = (bj - c) * M_PER_PX, -(bi - c) * M_PER_PX
        lon0, lat0 = r.get("lon_start", r["lon"]), r.get("lat_start", r["lat"])
        new_lon = lon0 + de / (111320 * math.cos(math.radians(lat0)))
        new_lat = lat0 + dn / 110574
        r.update({
            "lon_start": lon0, "lat_start": lat0,
            "lon": round(new_lon, 5), "lat": round(new_lat, 5),
            "przesuniecie_m": round(math.hypot(de, dn), 0),
            "odleglosc_od_krawedzi_m": round(edge_m, 0),
            "odleglosc_od_krawedzi_start_m": round(start_edge_m, 0),
            "powierzchnia_pola_ha_szac": round(float(mask.sum()) * M_PER_PX**2 / 1e4, 1),
            "srodek_pola_ok": edge_m >= MIN_EDGE_M,
            "prog_koloru": TOL_BY_ID.get(cid, TOL),
            "uldk_zapytanie": "GetParcelByXY, xy=lon,lat,4326 (z hotspotu, bez śledzenia przekierowań)",
        })
        print(f"{cid:22s} krawędź start {start_edge_m:5.0f} m → {edge_m:5.0f} m, przesunięcie "
              f"{r['przesuniecie_m']:4.0f} m, pole ~{r['powierzchnia_pola_ha_szac']} ha, ok={r['srodek_pola_ok']}")
    path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
