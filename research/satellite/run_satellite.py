"""C9 – uruchomienie Sentinel-2 dla działek demo: podsumowanie, szereg 12 mies. + rok wcześniej,
mapy PNG z legendą, warstwa na mapę (mały PNG + bbox EPSG:4326), wykres szeregu.

    python research/satellite/run_satellite.py               # wszystkie działki
    python research/satellite/run_satellite.py 201305        # wybrane (prefiks id)
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sentinel as S  # noqa: E402

OUT = HERE / "out"
CACHE = HERE / "data" / "stac"
TODAY = date(2026, 11, 21)
START = TODAY - timedelta(days=730)  # 12 mies. + ten sam okres rok wcześniej

# NDVI – kategorie do mapy (sekwencyjnie, jeden odcień zieleni; progi opisowe, szacunek)
NDVI_BOUNDS = [-1, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]
NDVI_COLORS = ["#ebe7dc", "#d4e6c3", "#a9d18e", "#6fb153", "#3a8a2e", "#1d5e1c"]
NDVI_LABELS = ["< 0,2 goła gleba", "0,2–0,35", "0,35–0,5", "0,5–0,65", "0,65–0,8", "> 0,8 bujna zieleń"]
INK, INK2, MUTED, SURFACE = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"


def parcels() -> dict[str, dict]:
    out = {}
    gj = json.loads((HERE.parent / "terrain" / "out" / "201305_2.0038.6-1.geojson").read_text(encoding="utf-8"))
    f = next(x for x in gj["features"] if x["properties"].get("layer") == "parcel")
    ring = max((p[0] for p in f["geometry"]["coordinates"]), key=len)
    out["201305_2.0038.6/1"] = {"ring": ring, "opis": "podlaskie – działka demo (obrys ULDK z C1)", "full": True}
    cand = json.loads((HERE.parent / "demo" / "out" / "candidates.json").read_text(encoding="utf-8"))
    for k, c in cand.items():
        if not c.get("srodek_pola_ok"):
            continue
        out[k] = {"ring": S.square_around(c["lon"], c["lat"], 150.0),
                  "opis": f"{c.get('region', '')} – kwadrat 300 × 300 m wokół punktu", "full": False}
    return out


def layer_png(arr, valid, grid, path: Path) -> dict:
    """Lekka warstwa na mapę: RGBA PNG (piksel 10 m = 1 px) + bbox w EPSG:4326."""
    cmap = ListedColormap(NDVI_COLORS)
    norm = BoundaryNorm(NDVI_BOUNDS, cmap.N)
    rgba = cmap(norm(np.nan_to_num(arr, nan=-1)))
    rgba[..., 3] = np.where(valid & grid.mask, 0.85, 0.0)
    plt.imsave(path, rgba)
    t = None
    return {"png": path.name, "px": list(arr.shape[::-1]), "bytes": path.stat().st_size}


def bounds_4326(scene: S.Scene, grid: S.ParcelGrid) -> list[list[float]]:
    t = scene.assets["red"]["transform"]
    r0, r1 = grid.rows10
    c0, c1 = grid.cols10
    xs = [t[2] + c0 * t[0], t[2] + c1 * t[0]]
    ys = [t[5] + r1 * t[4], t[5] + r0 * t[4]]
    lon, lat = S.utm_to_lonlat(np.array([xs[0], xs[1], xs[0], xs[1]]), np.array([ys[0], ys[0], ys[1], ys[1]]), scene.epsg)
    return [[round(float(lat.min()), 6), round(float(lon.min()), 6)], [round(float(lat.max()), 6), round(float(lon.max()), 6)]]


def map_png(pid, opis, p, arrays, grid, path: Path):
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 4.4), layout="constrained", facecolor=SURFACE)
    cmap = ListedColormap(NDVI_COLORS)
    norm = BoundaryNorm(NDVI_BOUNDS, cmap.N)
    for ax, key, title in ((axs[0], "ndvi", f"Zieleń (NDVI) – mediana {p['ndvi']}"),
                           (axs[1], "ndmi", f"Wilgotność roślin (NDMI) – mediana {p['ndmi']}")):
        a = np.where(arrays["valid"], arrays[key], np.nan)
        if key == "ndvi":
            im = ax.imshow(a, cmap=cmap, norm=norm, interpolation="nearest")
        else:
            im = ax.imshow(a, cmap="Blues", vmin=-0.2, vmax=0.5, interpolation="nearest")
            cb = fig.colorbar(im, ax=ax, shrink=0.8)
            cb.set_label("NDMI", color=INK2)
            cb.outline.set_visible(False)
        ax.contour(grid.mask, levels=[0.5], colors=INK, linewidths=1.2)
        cloud = np.isin(arrays["scl"], S.SCL_CLOUD + S.SCL_SNOW) & grid.mask
        if cloud.any():
            ax.contourf(cloud, levels=[0.5, 1.5], colors="none", hatches=["///"])
        ax.set_title(title, loc="left", fontsize=10, color=INK)
        ax.set_xticks([]), ax.set_yticks([])
    from matplotlib.patches import Patch
    axs[0].legend(handles=[Patch(color=c, label=l) for c, l in zip(NDVI_COLORS, NDVI_LABELS)],
                  loc="upper left", bbox_to_anchor=(0, -0.02), ncol=2, frameon=False, fontsize=7)
    fig.suptitle(f"{pid} · {opis}\nSentinel-2 {p['date']} · piksel 10 m · chmury w obrysie {p['cloud_pct']:.0f} %",
                 x=0.01, ha="left", fontsize=9, color=INK2)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def series_png(pid, pts_now, pts_prev, path: Path):
    fig, axs = plt.subplots(2, 1, figsize=(9, 5.4), sharex=True, layout="constrained", facecolor=SURFACE)
    for ax, key, lab in ((axs[0], "ndvi", "NDVI (zieleń)"), (axs[1], "ndmi", "NDMI (wilgotność roślin)")):
        for pts, col, name, shift in ((pts_prev, "#898781", "rok wcześniej", 365), (pts_now, "#2a78d6", "ostatnie 12 mies.", 0)):
            xs = [date.fromisoformat(p["date"]) + timedelta(days=shift) for p in pts if p.get(key) is not None]
            ys = [p[key] for p in pts if p.get(key) is not None]
            ax.plot(xs, ys, "-o", color=col, ms=4, lw=2, label=name)
        ax.set_ylabel(lab, color=INK2)
        ax.grid(axis="y", color="#e1e0d9")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axs[0].legend(frameon=False, loc="upper left")
    axs[0].set_title(f"{pid} – Sentinel-2, tylko sceny bez chmur nad działką (mediana obrysu)", loc="left", fontsize=10)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def run(pid: str, meta: dict) -> dict:
    t0 = time.perf_counter()
    ring = meta["ring"]
    lons, lats = [p[0] for p in ring], [p[1] for p in ring]
    bbox = [min(lons), min(lats), max(lons), max(lats)]
    key = pid.replace("/", "-")
    scenes, info = S.search_scenes(bbox, START, TODAY, 40.0, cache=CACHE / f"{key}.json")
    total = S.Stats()
    p, arrays, st = S.parcel_summary(ring, scenes, TODAY)
    total.add(st)
    res = {"parcel_id": pid, "opis": meta["opis"], "stac_seconds": info["seconds"], "scenes_matched": info["matched"],
           "scenes_unique_dates": len(scenes)}
    if p.get("ndvi") is None and arrays is None:
        res.update({"warning": p.get("warning")})
        return res
    g = p.pop("grid")
    sc = next(s for s in scenes if s.date.isoformat() == p["date"])
    ref = date.fromisoformat(p["date"])
    # ten sam okres rok wcześniej: czysta scena ±20 dni
    prev_cands = [s for s in scenes if abs((s.date - (ref - timedelta(days=365))).days) <= 20]
    prev = None
    for s in sorted(prev_cands, key=lambda s: abs((s.date - (ref - timedelta(days=365))).days)):
        gg = S.parcel_grid(ring, s)
        q = S.scene_point(s, gg, bands=False)
        total.bytes += q["bytes"]
        total.requests += q["requests"]
        if S.is_clear(q):
            q = S.scene_point(s, gg, bands=True)
            total.bytes += q["bytes"]
            total.requests += q["requests"]
            q.pop("_arrays", None)
            if q["ndvi"] is not None:
                prev = q
                break
    sentence = S.compare_sentence(p, prev, ref.month)
    res.update({k: p[k] for k in ("date", "scene", "ndvi", "ndmi", "cloud_pct", "snow_pct", "valid_pct", "warning")})
    res["last_year"] = {k: prev[k] for k in ("date", "ndvi", "ndmi", "cloud_pct")} if prev else None
    res["sentence"] = sentence
    # mapy
    map_png(pid, meta["opis"], p, arrays, g, OUT / f"{key}_mapa.png")
    lay = layer_png(arrays["ndvi"], arrays["valid"], g, OUT / f"{key}_ndvi_layer.png")
    lay["bounds_4326"] = bounds_4326(sc, g)
    lay["uwaga"] = "obraz w siatce UTM rozciągnięty na bbox EPSG:4326 (dla działek < 1 km błąd < 1 piksela)"
    n_valid = int((arrays["valid"] & g.mask).sum())
    lay["geojson_grid_bytes_szac"] = n_valid * 260  # ~260 B na kwadrat piksela w GeoJSON
    (OUT / f"{key}_ndvi_layer.json").write_text(json.dumps(lay, ensure_ascii=False), encoding="utf-8")
    res["layer"] = lay
    # szereg
    if meta["full"]:
        mid = TODAY - timedelta(days=365)
        now_pts, st1 = S.timeseries(ring, scenes, mid, TODAY)
        prev_pts, st2 = S.timeseries(ring, scenes, START, mid)
        total.add(st1)
        total.add(st2)
        series_png(pid, now_pts, prev_pts, OUT / f"{key}_szereg.png")
        (OUT / f"{key}_szereg.json").write_text(json.dumps({"ostatnie_12_mies": now_pts, "rok_wczesniej": prev_pts},
                                                           ensure_ascii=False, indent=0), encoding="utf-8")
        res["series_points"] = {"now": sum(1 for q in now_pts if q["ndvi"] is not None),
                                "prev": sum(1 for q in prev_pts if q["ndvi"] is not None),
                                "masks_only": len(now_pts) + len(prev_pts)}
    res["seconds"] = round(time.perf_counter() - t0, 1)
    res["mb"] = round(total.bytes / 1e6, 1)
    res["requests"] = total.requests
    return res


def main(args):
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    summ_path = OUT / "summary.json"
    summ = json.loads(summ_path.read_text(encoding="utf-8")) if summ_path.exists() else {}
    for pid, meta in parcels().items():
        if args and not any(pid.startswith(a) for a in args):
            continue
        print(f"→ {pid}", flush=True)
        try:
            r = run(pid, meta)
        except RuntimeError as exc:
            r = {"parcel_id": pid, "error": str(exc)}
        summ[pid] = r
        print(json.dumps({k: v for k, v in r.items() if k != "layer"}, ensure_ascii=False), flush=True)
        summ_path.write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
