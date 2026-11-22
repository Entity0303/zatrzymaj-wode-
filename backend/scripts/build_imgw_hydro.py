"""Percentyle stanów wody na wodowskazach IMGW z 10 lat (A9) → app/data/imgw/hydro_levels.json.

    docker compose run --rm -e DEMO_OFFLINE=false backend python scripts/build_imgw_hydro.py [--years 2016-2025]

Źródło: archiwum dobowe IMGW-PIB (danepubliczne.imgw.pl, dane_hydrologiczne/dobowe/<rok>/codz_<rok>.zip – rok
hydrologiczny, ok. 1,8 MB; starsze lata mogą być w plikach miesięcznych codz_<rok>_<mm>.zip). Wiersz CSV (cp1250):
kod stacji, nazwa, rzeka, rok hydrologiczny, miesiąc hydrologiczny, dzień, stan wody [cm], przepływ, temperatura,
miesiąc kalendarzowy. Stan 9999 / pusty = brak. Wynik: dla każdej stacji i miesiąca kalendarzowego percentyle
P10, P33, P66, P90 stanu (cm) – „niski” ≤ P33, „wysoki” ≥ P66 (D92). Licencja danych IMGW: wykorzystanie z podaniem
źródła („Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy”).
"""

import argparse
import asyncio
import csv
import io
import json
import re
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.http import request  # noqa: E402

BASE = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe/"
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "imgw" / "hydro_levels.json"
SRC = "IMGW-PIB (hydro archiwum)"


async def get(url: str) -> bytes | None:
    r = await request("GET", url, source=SRC, timeout_s=60, max_bytes=60_000_000)
    return r.content if r.status_code == 200 else None


async def year_files(year: int) -> list[bytes]:
    data = await get(f"{BASE}{year}/codz_{year}.zip")
    if data:
        return [data]
    listing = await get(f"{BASE}{year}/")
    names = re.findall(rb'href="(codz_\d{4}_\d{2}\.zip)"', listing or b"")
    out = []
    for n in names:
        await asyncio.sleep(0.3)
        d = await get(f"{BASE}{year}/{n.decode()}")
        if d:
            out.append(d)
    return out


def rows(blob: bytes):
    z = zipfile.ZipFile(io.BytesIO(blob))
    for name in z.namelist():
        if not name.lower().endswith(".csv"):
            continue
        text = z.read(name).decode("cp1250", "replace")
        for raw in text.splitlines():
            line = raw.strip().strip('"').replace('""', '"')
            try:
                rec = next(csv.reader([line]))
            except StopIteration:
                continue
            if len(rec) < 10:
                continue
            yield rec


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2016-2025")
    a = ap.parse_args()
    y0, y1 = (int(x) for x in a.years.split("-"))
    levels: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    meta: dict[str, tuple[str, str]] = {}
    t0, total_mb = time.monotonic(), 0.0
    for year in range(y0, y1 + 1):
        blobs = await year_files(year)
        total_mb += sum(len(b) for b in blobs) / 1e6
        n = 0
        for blob in blobs:
            for rec in rows(blob):
                code, name, river = (x.strip().strip('"').strip() for x in rec[:3])
                try:
                    lvl, month = float(rec[6]), int(rec[9])
                except ValueError:
                    continue
                if lvl >= 9999 or not 1 <= month <= 12:
                    continue
                levels[code][month].append(lvl)
                meta[code] = (name, re.sub(r"\s*\(\d+\)$", "", river))
                n += 1
        print(f"{year}: {len(blobs)} plik(ów), {n} pomiarów")
        await asyncio.sleep(0.5)
    out = {"_opis": "Percentyle stanu wody [cm] P10, P33, P66, P90 wg miesiąca kalendarzowego, archiwum dobowe IMGW-PIB "
                    f"{y0}–{y1} (scripts/build_imgw_hydro.py). Źródło: IMGW-PIB.",
           "stations": {}}
    for code, by_m in levels.items():
        p = {str(m): [round(float(v)) for v in np.percentile(vals, [10, 33, 66, 90])]
             for m, vals in sorted(by_m.items()) if len(vals) >= 60}
        if p:
            out["stations"][code] = {"name": meta[code][0], "river": meta[code][1], "p": p}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"zapisano {OUT.name}: {len(out['stations'])} stacji, {OUT.stat().st_size / 1e3:.0f} kB; pobrano {total_mb:.1f} MB "
          f"w {time.monotonic() - t0:.0f} s")


asyncio.run(main())
