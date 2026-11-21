"""C4 – analiza opadów z 3 źródeł dla działek demo i z research/terrain (2016–2025).

    python research/precip/analyze.py

Wymaga zbudowanego indeksu IMGW (precip.build_index – pobiera archiwum do raw/).
Wyniki: out/comparison.csv, out/big_differences.csv, out/stations.csv, out/summary.json,
out/<działka>_opady.png. Odpowiedzi ERA5-Land i NASA – w data/cache/ (nie odpytujemy drugi raz).
"""

from __future__ import annotations

import csv
import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "terrain"))
import precip as P  # noqa: E402

OUT = HERE / "out"
START, END = date(2016, 1, 1), date(2025, 12, 31)
YEARS = list(range(2016, 2026))

# działki: przykłady z backend/app/demo.py + działki z research/terrain (C1)
PARCELS = {
    "201305_2.0038.6/1": "podlaskie (demo: susza 2018 / mokry 2021)",
    "061704_2.0011.383/2": "lubelskie (demo: kukurydza)",
    "143203_2.0027.112/11": "mazowieckie (demo: Kampinos)",
    "040703_5.0020.76": "kujawsko-pomorskie (C1)",
    "121601_5.0002.770": "małopolskie – stok (C1)",
}
SRC_LABEL = {"imgw_idw": "IMGW (stacje, IDW)", "era5_land": "ERA5-Land (~9 km)", "nasa_power": "NASA POWER (~50 km)"}
SRC_COLOR = {"imgw_idw": "#2a78d6", "era5_land": "#eb6834", "nasa_power": "#1baf7a"}  # paleta zweryfikowana (C1)
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"


def parcel_points() -> dict[str, dict]:
    """Środek działki (lon, lat) z obrysu C1 (research/terrain/out) – zapisany w data/parcels.json."""
    path = P.DATA / "parcels.json"
    have = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    missing = [p for p in PARCELS if p not in have]
    if missing:
        for pid in missing:
            gj = HERE.parent / "terrain" / "out" / f"{pid.replace('/', '-')}.geojson"
            if gj.exists():  # obrys z wyników C1 (EPSG:4326) – bez pytania ULDK
                f = next(x for x in json.loads(gj.read_text(encoding="utf-8"))["features"]
                         if x["properties"].get("layer") == "parcel")
                ring = np.array(max((poly[0] for poly in f["geometry"]["coordinates"]), key=len))
                have[pid] = {"lon": round(float(ring[:-1, 0].mean()), 5), "lat": round(float(ring[:-1, 1].mean()), 5),
                             "opis": PARCELS[pid], "zrodlo": "obrys z research/terrain/out (C1)"}
                continue
            # ULDK nie odpytujemy z sieci hackathonu (limit, przekierowania 302) – działki bez obrysu
            # z C1 dociągniemy po integracji
            print(f"POMINIĘTA: {pid} – brak obrysu w research/terrain/out, ULDK nie jest odpytywany", flush=True)
        path.write_text(json.dumps(have, ensure_ascii=False, indent=1), encoding="utf-8")
    return have


NAN = float("nan")


def fmt(v):
    return round(v, 1) if v is not None and math.isfinite(v) else ""


def pct(a, b):
    return round(100 * (a - b) / b, 1) if b and math.isfinite(a) and math.isfinite(b) else None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    P.ERA5_NETWORK = False  # archiwum Open-Meteo: limit dzienny wyczerpany w sieci hackathonu
    pts = parcel_points()
    catalog = P.station_catalog()
    index = P.load_index()

    # 1) stacje dla działek + wyciągnięcie tylko ich serii z archiwum
    per_parcel = {}
    all_st = {}
    for pid, pt in pts.items():
        st = P.nearest_stations(pt["lon"], pt["lat"], n=3, max_km=30, start=START, end=END,
                                catalog=catalog, index=index) or             P.nearest_stations(pt["lon"], pt["lat"], n=3, max_km=50, start=START, end=END,
                               catalog=catalog, index=index)  # jak combine(): rezerwa do 50 km
        per_parcel[pid] = st
        for s in st:
            all_st[s.code] = s
    need = [s for s in all_st.values() if not (P.DATA / "imgw" / f"{s.code}.csv").exists()]
    if need:
        P.extract_station_series(need, YEARS)

    comp_rows, diff_rows, st_rows, summary = [], [], [], {}
    for pid, pt in pts.items():
        key = pid.replace("/", "-")
        t0 = time.perf_counter()
        res = P.combine(pt["lon"], pt["lat"], START, END, key)
        t_comb = time.perf_counter() - t0
        days = res.days
        for s in res.stations:
            st_rows.append({"parcel_id": pid, "kod": s.code, "nazwa": s.name, "rodzaj": s.kind,
                            "odleglosc_km": s.dist_km, "lon": s.lon, "lat": s.lat})
        yr = np.array([d.year for d in days])
        mo = np.array([d.month for d in days])
        stats = {"stations": [(s.name, s.kind, s.dist_km) for s in res.stations],
                 "nearest_km": res.stations[0].dist_km if res.stations else None,
                 "stations_note": res.timings_s.get("stations_note"),
                 "fetch_s": res.timings_s, "combine_s": round(t_comb, 2)}
        annual = {}
        for y in YEARS:
            for okres, mask in (("rok", yr == y), ("IV-IX", (yr == y) & (mo >= 4) & (mo <= 9))):
                vals = {}
                for k, v in res.series.items():
                    part = v[mask]
                    vals[k] = float(np.nansum(part)) if np.isnan(part).mean() <= 0.05 else float("nan")
                good = [x for x in vals.values() if math.isfinite(x)]
                spread = (max(good) - min(good)) / max(np.mean(good), P.MIN_SUM_MM) if len(good) >= 2 else float("nan")
                imgw = vals.get("imgw_idw", float("nan"))
                comp_rows.append({
                    "parcel_id": pid, "opis": pt["opis"], "rok": y, "okres": okres,
                    "imgw_idw_mm": round(imgw, 1) if math.isfinite(imgw) else "",
                    "era5_land_mm": fmt(vals.get("era5_land")), "nasa_power_mm": fmt(vals.get("nasa_power")),
                    "nasa_vs_imgw_pct": pct(vals.get("nasa_power", NAN), imgw),
                    "era5_vs_imgw_pct": pct(vals.get("era5_land", NAN), imgw),
                    "rozrzut": round(spread, 3) if math.isfinite(spread) else "",
                    "ocena": P.label_for(spread),
                    "stacje": "; ".join(f"{s.name} ({s.kind}, {s.dist_km:.1f} km)" for s in res.stations),
                })
                annual[(y, okres)] = vals
        # NASA i ERA5 względem IMGW – średnio (rok, sezon)
        for okres in ("rok", "IV-IX"):
            for src in ("nasa_power", "era5_land"):
                ds = [pct(annual[(y, okres)].get(src, NAN), annual[(y, okres)].get("imgw_idw", NAN)) for y in YEARS]
                ds = [x for x in ds if x is not None]
                stats[f"{src}_vs_imgw_{okres}_pct"] = round(float(np.mean(ds)), 1) if ds else None
        stats["2018_IV-IX"] = {k: round(v, 0) for k, v in annual[(2018, "IV-IX")].items()}
        stats["2021_IV-IX"] = {k: round(v, 0) for k, v in annual[(2021, "IV-IX")].items()}
        stats["2018_rok"] = {k: round(v, 0) for k, v in annual[(2018, "rok")].items()}
        stats["2021_rok"] = {k: round(v, 0) for k, v in annual[(2021, "rok")].items()}
        # duże różnice dobowe (lokalne burze): IMGW vs modele, sezon IV–IX
        if "imgw_idw" in res.series:
            nanv = np.full(len(days), np.nan)
            im, e5, na = res.series["imgw_idw"], res.series.get("era5_land", nanv), res.series.get("nasa_power", nanv)
            cand = []
            for i, d in enumerate(days):
                if not (4 <= d.month <= 9) or math.isnan(im[i]):
                    continue
                vv = [x for x in (im[i], e5[i], na[i]) if not math.isnan(x)]
                hi, lo = max(vv), min(vv)
                if hi - lo >= 20:
                    cand.append((hi - lo, i))
            for diff, i in sorted(cand, reverse=True)[:6]:
                diff_rows.append({"parcel_id": pid, "data": days[i].isoformat(),
                                  "imgw_idw_mm": round(float(im[i]), 1), "era5_land_mm": round(float(e5[i]), 1),
                                  "nasa_power_mm": round(float(na[i]), 1), "roznica_mm": round(float(diff), 1),
                                  "kto_wiecej": max((("imgw_idw", im[i]), ("era5_land", e5[i]), ("nasa_power", na[i])),
                                                    key=lambda t: -1 if math.isnan(t[1]) else t[1])[0]})
            stats["n_days_diff_ge_20mm"] = len(cand)
            # korelacja dobowa w sezonie
            msk = np.array([4 <= d.month <= 9 for d in days]) & ~np.isnan(im)
            stats["corr_daily_IV-IX"] = {
                f"imgw~{k}": round(float(np.corrcoef(im[msk & ~np.isnan(v)], v[msk & ~np.isnan(v)])[0, 1]), 2)
                for k, v in (("era5", e5), ("nasa", na)) if (~np.isnan(v[msk])).any()}
            # zgodność „na dziś” – przykładowe daty demo
            stats["agreement_2018-06-10"] = P.agreement(days, res.series, date(2018, 6, 10))
            stats["agreement_2021-07-15"] = P.agreement(days, res.series, date(2021, 7, 15))
            stats["sentence_2018-06-10"] = P.sentence(stats["agreement_2018-06-10"])
        summary[pid] = stats
        plot(pid, pt, annual, res)
        print(f"{pid:22s} stacje: {stats['stations']}  NASA vs IMGW rok {stats['nasa_power_vs_imgw_rok_pct']} %, "
              f"IV–IX {stats['nasa_power_vs_imgw_IV-IX_pct']} %  ERA5 vs IMGW rok {stats['era5_land_vs_imgw_rok_pct']} %",
              flush=True)

    def write(name, rows):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    write("comparison.csv", comp_rows)
    write("big_differences.csv", diff_rows)
    write("stations.csv", st_rows)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str),
                                      encoding="utf-8")


def plot(pid, pt, annual, res):
    srcs = [s for s in ("imgw_idw", "era5_land", "nasa_power") if s in res.series]
    fig, ax = plt.subplots(figsize=(10, 4.6), layout="constrained", facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    w = 0.8 / len(srcs)
    for k, s in enumerate(srcs):
        vals = [annual[(y, "rok")][s] for y in YEARS]
        x = np.arange(len(YEARS)) + (k - (len(srcs) - 1) / 2) * w
        ax.bar(x, vals, width=w - 0.03, color=SRC_COLOR[s], label=SRC_LABEL[s], edgecolor=SURFACE, linewidth=1)
    ax.set_xticks(np.arange(len(YEARS)), [str(y) for y in YEARS], color=INK2)
    ax.set_ylabel("opad roczny [mm]", color=INK2)
    ax.tick_params(colors=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#c3c2b7")
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, 1.13), labelcolor=INK)
    st = ", ".join(f"{s.name} {s.dist_km:.0f} km" for s in res.stations) or "brak stacji ≤ 30 km"
    ax.set_title(f"Opady roczne 2016–2025 · {pid} · {pt['opis']}\nstacje IMGW: {st}",
                 loc="left", fontsize=10, color=INK, pad=28)
    fig.savefig(OUT / f"{pid.replace('/', '-')}_opady.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
