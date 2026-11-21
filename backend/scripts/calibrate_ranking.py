"""Kalibracja rankingu z GUS (A5b-2a, powtórzona w A7 na opadzie IMGW): średni plon symulowany na przeciętnej glebie
(WOD 167,5 mm, gleba „neutralna”) vs średni plon GUS w województwie, 2016–2025.

    docker compose run --rm -e DEMO_OFFLINE=false backend python scripts/calibrate_ranking.py

Pogoda: NASA POWER (ET0) + opad ze stacji IMGW (magazyn w repo); kolumna „NASA” – ten sam model na opadzie NASA.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis import precip as precip_mod  # noqa: E402
from app.analysis import suggestions as S  # noqa: E402
from app.analysis.crops import RANKING_CROPS  # noqa: E402
from app.analysis.water_balance import history_range, last_usable_day  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.sources import weather_power  # noqa: E402

POINTS = {"podlaskie": (22.6009, 53.0500), "lubelskie": (22.8528, 51.0362), "wielkopolskie": (16.26, 52.685),
          "kujawsko-pomorskie": (18.3351, 52.8455)}
WOD = 167.5


def deviations(w, voiv: str, last: date) -> dict[str, float | None]:
    out = {}
    for crop in RANKING_CROPS:
        raw = S.simulate(w, crop, WOD, last, 10)
        pot = S.potential(crop.id, voiv)
        if len(raw) < 5 or pot.ym_t_ha is None or not pot.mean_t_ha:
            out[crop.id] = None
            continue
        ref = S.reference_level(w, crop, last, 10)
        mean_rel = float(np.mean([min(1.0, r / ref) for _y, r, _d in raw]))
        out[crop.id] = round(100.0 * (pot.ym_t_ha * mean_rel / pot.mean_t_ha - 1.0), 1)
    return out


async def main() -> None:
    on = date.today()
    start, end = history_range(on, None, settings.history_years)
    last = last_usable_day(on)
    rows = {}
    for voiv, (lon, lat) in POINTS.items():
        w = await weather_power.fetch(lon, lat, start, end)
        S._sim_memo.clear()
        nasa = deviations(w, voiv, last)
        w2, info = precip_mod.apply(w, lon, lat, on)
        S._sim_memo.clear()
        rows[voiv] = (nasa, deviations(w2, voiv, last), info)
        print(f"# {voiv}: {info.main}, stacje {[(p.name, p.dist_km) for p, _ in info.stations]}, NASA vs IMGW {info.nasa_vs_imgw_pct}%")
    print("\n| Uprawa | " + " | ".join(f"{v} NASA → IMGW" for v in rows) + " |")
    print("|---|" + "---|" * len(rows))
    for crop in RANKING_CROPS:
        cells = []
        for v in rows:
            a, b = rows[v][0][crop.id], rows[v][1][crop.id]
            cells.append("–" if a is None or b is None else f"{a:+.0f}% → {b:+.0f}%")
        print(f"| {crop.label} | " + " | ".join(cells) + " |")
    worst = max(abs(x) for v in rows for x in rows[v][1].values() if x is not None)
    print(f"\nnajwiększe odchylenie na IMGW: {worst:.0f}%")


asyncio.run(main())
