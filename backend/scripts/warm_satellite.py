"""Satelita Sentinel-2 do cache dla wskazanych działek (A11): wynik na żywo (scena + rok temu) i szereg 12 mies.

    docker compose run --rm -e DEMO_OFFLINE=false backend python scripts/warm_satellite.py
    docker compose run --rm -e DEMO_OFFLINE=false backend python scripts/warm_satellite.py --no-series

Odpytuje TYLKO Earth Search (AWS) – działki bierze z indeksu znanych działek (cache / app/data/demo_parcels.json),
punkty jako obszar przybliżony 1 ha (bez ULDK). Wynik trafia do trwałego cache (`CACHE_DB`), z którego korzysta
/api/analysis, /api/satellite, warstwy mapy i raport PDF (także w DEMO_OFFLINE).
"""

import argparse
import asyncio
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis import approx_area  # noqa: E402
from app.analysis import satellite as sat_mod  # noqa: E402
from app.core.cache import store  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.sources import uldk  # noqa: E402

TARGETS = [("201305_2.0038.6/1", None), ("Puszcza Notecka (obszar przybliżony)", (16.26, 52.685))]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-series", action="store_true")
    ap.add_argument("--date", default=None)
    ap.add_argument("--live", action="store_true", help="budżet jak na żywo (15 s, 10 MB) – tylko pomiar, bez zapisu")
    a = ap.parse_args()
    on = date.fromisoformat(a.date) if a.date else date.today()
    # przygotowanie cache (nie tryb na żywo): większy budżet i limity – wynik ma mieć porównanie z rokiem temu
    if not a.live:
        settings.sentinel_budget_s, settings.sentinel_budget_mb, settings.sentinel_timeout_s = 90.0, 40.0, 20.0
    store()
    uldk.load_known()
    for name, pt in TARGETS:
        if pt is None:
            p = uldk.known_by_id(name)
            if p is None:
                print(f"{name}: brak w indeksie znanych działek – pomijam")
                continue
        else:
            p = approx_area.approximate_parcel(*pt)
        geom = p.geom_4326
        t0 = time.monotonic()
        try:
            res = await sat_mod.compute_live(geom, on)
        except Exception as exc:  # noqa: BLE001
            print(f"== {name}: BŁĄD {exc} ({time.monotonic() - t0:.1f} s)")
            continue
        sat = sat_mod.to_contract(res)
        if not a.live:
            sat_mod._store(geom, on, sat, sat_mod.layers_from(res.now) if res.now else None)
        lay = sat_mod.cached_layers(geom, on) or {}
        print(f"== {name}: {sat.status}, {time.monotonic() - t0:.1f} s, {res.stats.mb:.2f} MB, {res.stats.requests} zapytań, "
              f"scen w 60 dniach {res.searched}")
        print(f"   scena {sat.date} {sat.scene_id}: NDVI {sat.ndvi} NDMI {sat.ndmi} ważne {sat.valid_pct}% | rok temu "
              f"{sat.last_year.date if sat.last_year else None} NDVI {sat.last_year.ndvi if sat.last_year else None} | "
              f"poziom {sat.level} | warstwy: kondycja {len(lay.get('kondycja', '')) * 3 // 4} B, "
              f"wilgotność {len(lay.get('wilgotnosc', '')) * 3 // 4} B")
        print(f"   ZDANIE: {sat.sentence}")
        if sat.warning:
            print(f"   UWAGA: {sat.warning}")
        if not a.no_series and not a.live:
            t1 = time.monotonic()
            n, st = await sat_mod.warm_series(geom, on)
            print(f"   szereg: {n} punktów, {time.monotonic() - t1:.0f} s, {st.mb:.1f} MB, {st.requests} zapytań")


asyncio.run(main())
