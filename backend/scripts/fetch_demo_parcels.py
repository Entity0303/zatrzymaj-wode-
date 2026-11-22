"""Działki demo z ULDK (A8): punkty kandydatów osoby C (research/demo/out/candidates.json) i brakujące działki A5d.

    docker compose exec -e DEMO_OFFLINE=false backend python scripts/fetch_demo_parcels.py > wynik.json

Spokojnie: przerwa ≥ 1,2 s po każdym zapytaniu, które nie było z cache; ULDK przez `sources/uldk.py` (bez
przekierowań, cache bez wygasania). Dla każdego punktu: działka, powierzchnia, szerokość (najmniejszy prostokąt
obejmujący), odległość punktu od granicy – wąska działka / punkt przy granicy = sygnał, że trzeba wziąć sąsiednią.
Wynik (JSON) na stdout – zapis do app/data/demo_parcels.json robi `--write`.
"""

import argparse
import asyncio
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shapely.geometry import Point  # noqa: E402

from app.core.cache import store  # noqa: E402
from app.core.geo import to_2180  # noqa: E402
from app.core.http import SourceError  # noqa: E402
from app.sources import uldk  # noqa: E402

PAUSE_S = 1.2

# (klucz, lon, lat) – punkty z research/demo/out/candidates.json (środek pola wg ortofotomapy, osoba C)
POINTS = [
    ("notecka-slaba", 16.26185, 52.68508),
    ("piasek-zyto", 21.45847, 53.21966),
    ("czarnoziem-pszenica", 23.86583, 50.82115),
    ("kujawy-susza", 18.23933, 52.73062),
    ("less-erozja", 22.17122, 51.31662),
    ("pojezierze-oczko", 21.38672, 53.87180),
    ("zulawy-mady", 19.02959, 54.16038),
    ("pogorze-stok", 22.29981, 49.84002),
]
# brakujące działki A5d: (zapytanie, gmina do wyboru przy kilku wynikach)
QUERIES = [
    ("061704_2.0011.383/2", None),
    ("143203_2.0027.112/11", None),
    ("Szczytno 126/3", "Kampinos"),
    ("Lasotka 118", "Iłów"),
    # działki testowe terenu osoby C (zapisane wyniki NMT w app/data/terrain – D57)
    ("040703_5.0020.76", None),
    ("121601_5.0002.770", None),
]


def describe(p: uldk.Parcel, lon: float | None = None, lat: float | None = None) -> dict:
    g = p.geom_2180
    rect = g.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    sides = sorted(math.dist((xs[i], ys[i]), (xs[i + 1], ys[i + 1])) for i in range(2))
    out = {"id": p.id, "obreb": p.region, "numer": p.number, "gmina": p.commune, "powiat": p.county,
           "wojewodztwo": p.voivodeship, "area_ha": round(g.area / 1e4, 2), "width_m": round(sides[0], 1),
           "length_m": round(sides[1], 1), "geom_wkt_2180": g.wkt,
           "fetched_at": p.fetched_at.isoformat() if p.fetched_at else datetime.now(timezone.utc).isoformat()}
    if lon is not None:
        pt = to_2180(Point(lon, lat))
        out["point_to_edge_m"] = round(g.exterior.distance(pt), 1)
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="tylko te klucze / zapytania")
    a = ap.parse_args()
    store()
    res: dict[str, dict] = {}
    for key, lon, lat in POINTS:
        if a.only and key not in a.only:
            continue
        t = time.monotonic()
        try:
            p = await uldk.by_point(lon, lat)
            res[key] = {"point": [lon, lat], **describe(p, lon, lat)}
        except SourceError as exc:
            res[key] = {"point": [lon, lat], "error": f"{type(exc).__name__}: {exc.message}"}
        print(f"{key}: {res[key].get('id') or res[key].get('error')} ({time.monotonic() - t:.2f} s)", file=sys.stderr)
        if time.monotonic() - t > 0.05:
            await asyncio.sleep(PAUSE_S)
    for q, gmina in QUERIES:
        if a.only and q not in a.only:
            continue
        t = time.monotonic()
        try:
            found = await uldk.by_id(q)
            cands = [describe(p) for p in found]
            pick = [c for c in cands if gmina is None or c["gmina"] == gmina]
            res[q] = {"query": q, "candidates": [{k: c[k] for k in ("id", "gmina", "powiat", "area_ha")} for c in cands],
                      **(pick[0] if pick else {"error": f"brak działki w gminie {gmina}"})}
        except SourceError as exc:
            res[q] = {"query": q, "error": f"{type(exc).__name__}: {exc.message}"}
        print(f"{q}: {res[q].get('id') or res[q].get('error')} ({time.monotonic() - t:.2f} s)", file=sys.stderr)
        if time.monotonic() - t > 0.05:
            await asyncio.sleep(PAUSE_S)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=1)


asyncio.run(main())
