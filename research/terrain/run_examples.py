"""Uruchomienie prototypu terenu dla działek testowych + obrazki PNG, GeoJSON i fakty JSON.

    python research/terrain/run_examples.py            # wszystkie działki
    python research/terrain/run_examples.py <ID> ...   # wybrane

Wyniki: research/terrain/out/<id>_*.png, <id>.geojson, <id>.facts.json, summary.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap, LogNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import terrain as T  # noqa: E402

OUT = HERE / "out"

PARCELS = {
    "201305_2.0038.6/1": "podlaskie, gm. Kobylin-Borzymy (0,58 ha)",
    "061704_2.0011.383/2": "lubelskie, gm. Rybczewice (0,21 ha)",
    "040703_5.0020.76": "kujawsko-pomorskie, gm. Gniewkowo (6,82 ha)",
    # działka na wyraźnym stoku – znaleziona przez ULDK GetParcelByXY (20.94, 49.73),
    # małopolskie; IUNG: kat. III (grunt rolny); różnica wysokości ok. 34 m
    "121601_5.0002.770": "małopolskie – stok (3,6 ha)",
}

# kolory stref – paleta kategoryczna w stałej kolejności (zweryfikowana walidatorem CVD)
ZONE_COLORS = {T.ZONE_WET: "#2a78d6", T.ZONE_HILL: "#eb6834",
               T.ZONE_FLAT: "#1baf7a", T.ZONE_SLOPE: "#eda100"}
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2, "xtick.color": MUTED,
    "ytick.color": MUTED, "text.color": INK, "font.size": 9, "axes.titlesize": 11,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def hillshade(z, step, az=315.0, alt=45.0):
    dzdx = np.gradient(z, step, axis=1)
    dzdy = -np.gradient(z, step, axis=0)  # wiersz rośnie na południe
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, dzdy)
    a, b = np.radians(az), np.radians(alt)
    hs = np.sin(b) * np.cos(slope) + np.cos(b) * np.sin(slope) * np.cos(a - aspect)
    return np.clip(hs, 0, 1)


class Plotter:
    def __init__(self, res: T.TerrainResult, pid: str, desc: str):
        self.res, self.pid, self.desc = res, pid, desc
        g = res.grid
        self.g = g
        # współrzędne lokalne [m] względem lewego dolnego rogu siatki
        self.x0 = g.e0 - g.step / 2
        self.y0 = g.n0 - (g.nrows - 1) * g.step - g.step / 2
        self.extent = [0, g.ncols * g.step, 0, g.nrows * g.step]
        self.r = res.rasters
        self.hs = hillshade(self.r["z_smooth"], g.step)

    def loc(self, e, n):
        return np.asarray(e) - self.x0, np.asarray(n) - self.y0

    def cell_xy(self, i, j):
        e, n = self.g.cell_to_en(i, j)
        return self.loc(e, n)

    def outline(self, ax, color=INK, lw=1.6):
        for poly in self.res.polygons:
            for ring in poly:
                x, y = self.loc(ring[:, 0], ring[:, 1])
                ax.plot(x, y, color=SURFACE, lw=lw + 2, solid_capstyle="round")
                ax.plot(x, y, color=color, lw=lw, solid_capstyle="round")

    def zoom(self, ax, pad=40):
        pts = np.vstack([r for p in self.res.polygons for r in p])
        x, y = self.loc(pts[:, 0], pts[:, 1])
        ax.set_xlim(x.min() - pad, x.max() + pad)
        ax.set_ylim(y.min() - pad, y.max() + pad)
        ax.set_aspect("equal")
        ax.set_xlabel("m (wschód)")
        ax.set_ylabel("m (północ)")
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    def base(self, ax, alpha=1.0):
        ax.imshow(self.hs, extent=self.extent, cmap="Greys_r", vmin=0, vmax=1,
                  alpha=alpha, interpolation="bilinear")

    def outside_veil(self, ax):
        veil = np.where(self.r["inside"], np.nan, 1.0)
        ax.imshow(veil, extent=self.extent, cmap=ListedColormap([SURFACE]), alpha=0.55,
                  interpolation="nearest")

    # ------------------------------------------------------------------ panele
    def p_elevation(self, ax):
        f = self.res.facts
        self.base(ax)
        im = ax.imshow(self.r["z"], extent=self.extent, cmap="Greens", alpha=0.55,
                       interpolation="bilinear")
        X = np.linspace(self.extent[0] + self.g.step / 2, self.extent[1] - self.g.step / 2, self.g.ncols)
        Y = np.linspace(self.extent[3] - self.g.step / 2, self.extent[2] + self.g.step / 2, self.g.nrows)
        relief = max(float(np.ptp(self.r["z_smooth"])), 0.5)
        lv = [0.25, 0.5, 1, 2, 5, 10][int(np.searchsorted([2, 5, 10, 25, 60], relief))]
        zs = self.r["z_smooth"]
        levels = np.arange(np.floor(zs.min() / lv) * lv, zs.max() + lv, lv)
        cs = ax.contour(X, Y, zs, levels=levels, colors=INK2, linewidths=0.5, alpha=0.7)
        ax.clabel(cs, fontsize=6, fmt="%.1f" if lv < 1 else "%.0f")
        self.outline(ax)
        cb = plt.colorbar(im, ax=ax, shrink=0.75)
        cb.set_label("wysokość [m n.p.m.]")
        cb.outline.set_visible(False)
        ax.set_title(f"Wysokości z cieniowaniem (warstwice co {lv:g} m)\n"
                     f"działka {f['elev_min_m']}–{f['elev_max_m']} m, różnica {f['relief_m']} m")
        self.zoom(ax)

    def p_slope(self, ax):
        f = self.res.facts
        self.base(ax, 0.6)
        bounds = [0, 2, 3, 5, 8, 12, 20, 100]
        cmap = plt.get_cmap("Oranges", len(bounds) - 1)
        im = ax.imshow(self.r["slope_pct"], extent=self.extent, cmap=cmap,
                       norm=BoundaryNorm(bounds, cmap.N), alpha=0.85, interpolation="nearest")
        self.outside_veil(ax)
        self.outline(ax)
        cb = plt.colorbar(im, ax=ax, shrink=0.75, ticks=bounds[:-1])
        cb.set_label("spadek [%]")
        cb.outline.set_visible(False)
        ax.set_title(f"Spadki\nśrednio {f['slope_mean_pct']} %, maks. {f['slope_max_pct']} %, "
                     f"> 5 % na {f['steep_share_pct']} % działki")
        self.zoom(ax)

    def p_zones(self, ax):
        f = self.res.facts
        zones = self.r["zones"].astype(float)
        zones_in = np.where(self.r["inside"], zones, np.nan)
        order = [T.ZONE_WET, T.ZONE_HILL, T.ZONE_FLAT, T.ZONE_SLOPE]
        cmap = ListedColormap([ZONE_COLORS[k] for k in range(4)])
        self.base(ax, 0.5)
        ax.imshow(np.where(self.r["inside"], np.nan, zones), extent=self.extent, cmap=cmap,
                  vmin=-0.5, vmax=3.5, alpha=0.25, interpolation="nearest")
        ax.imshow(zones_in, extent=self.extent, cmap=cmap, vmin=-0.5, vmax=3.5, alpha=0.85,
                  interpolation="nearest")
        for h in self.r["hills"][:5]:
            x, y = self.cell_xy(*h["top_cell"])
            ax.plot(x, y, marker="^", ms=9, color=INK, mec=SURFACE, mew=1.5)
        self.outline(ax)
        share = f["zone_share_pct"]
        handles = [Patch(facecolor=ZONE_COLORS[k], edgecolor="none",
                         label=f"{T.ZONE_LABELS[k]} – {share[T.ZONE_KEYS[k]]:.0f} %") for k in order]
        handles.append(plt.Line2D([], [], marker="^", ls="", color=INK, label="szczyt górki"))
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
        ax.set_title(f"Strefy działki\ngórek: {f['n_hills']}, zagłębień bez odpływu: {f['n_depressions']}")
        self.zoom(ax)

    def p_flow(self, ax):
        f = self.res.facts
        acc = self.r["acc_m2"]
        self.base(ax, 0.5)
        im = ax.imshow(acc, extent=self.extent, cmap="Blues",
                       norm=LogNorm(vmin=self.g.step**2, vmax=max(acc.max(), self.g.step**2 * 10)),
                       alpha=0.85, interpolation="nearest")
        for pth in self.r["paths"]:
            ii = np.array([c // self.g.ncols for c in pth])
            jj = np.array([c % self.g.ncols for c in pth])
            x, y = self.cell_xy(ii, jj)
            ax.plot(x, y, color="#104281", lw=2, solid_capstyle="round")
        for tail, head, az, sp, _ in self.r["arrows"]:
            xt, yt = self.loc(*tail)
            xh, yh = self.loc(*head)
            ax.annotate("", xy=(xh, yh), xytext=(xt, yt),
                        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2, mutation_scale=9))
        self._outlets(ax)
        self.outline(ax)
        cb = plt.colorbar(im, ax=ax, shrink=0.75)
        cb.set_label("powierzchnia zlewni komórki [m²]")
        cb.outline.set_visible(False)
        mo = f["outlets"][0] if f["outlets"] else None
        sub = (f"główne wyjście wody: {mo['direction']} ({mo['share_of_parcel_pct']:.0f} % działki)"
               if mo else "brak wyjścia wody")
        ax.set_title(f"Akumulacja spływu, strzałki i ścieżki spływu\n{sub}")
        self.zoom(ax)

    def _outlets(self, ax):
        for k, o in enumerate(self.r["outlets"]):
            x, y = self.loc(*o["en"])
            ax.plot(x, y, marker="o", ms=11, color="#d03b3b", mec=SURFACE, mew=2, zorder=5)
            ax.annotate(f"{k + 1}: {o['share_of_parcel'] * 100:.0f} %", (x, y), xytext=(7, 7),
                        textcoords="offset points", fontsize=8, color=INK, zorder=6,
                        bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec="none", alpha=0.85))

    def p_proposals(self, ax):
        f = self.res.facts
        self.base(ax, 0.8)
        dep = np.where(self.r["depressions"] > 0, self.r["depth"], np.nan)
        if np.isfinite(dep).any():
            im = ax.imshow(dep, extent=self.extent, cmap="Blues", alpha=0.9, vmin=0,
                           interpolation="nearest")
            cb = plt.colorbar(im, ax=ax, shrink=0.6)
            cb.set_label("głębokość zagłębienia [m]")
            cb.outline.set_visible(False)
        handles = []
        for pr in self.r["proposals"]:
            if pr["type"] == "pas_buforowy":
                (e0, n0), (e1, n1) = pr["line_en"]
                x, y = self.loc([e0, e1], [n0, n1])
                ax.plot(x, y, color="#008300", lw=5, alpha=0.85, solid_capstyle="round")
            else:
                x, y = self.cell_xy(*pr["cell"])
                ax.plot(x, y, marker="*", ms=18, color="#2a78d6", mec=SURFACE, mew=1.5, zorder=6)
        if any(p["type"] == "pas_buforowy" for p in self.r["proposals"]):
            handles.append(plt.Line2D([], [], color="#008300", lw=5, label="pas buforowy (w poprzek spływu)"))
        if any(p["type"] != "pas_buforowy" for p in self.r["proposals"]):
            handles.append(plt.Line2D([], [], marker="*", ls="", ms=14, color="#2a78d6", label="proponowane oczko"))
        handles.append(plt.Line2D([], [], marker="o", ls="", ms=9, color="#d03b3b", label="wyjście wody z działki"))
        self._outlets(ax)
        self.outline(ax)
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.12), frameon=False, ncol=1)
        lines = []
        for pr in f["proposals"]:
            if pr["type"] == "pas_buforowy":
                lines.append(f"pas buforowy {pr['length_m']:.0f} m × {pr['width_m']:.0f} m (spadek {pr['mean_slope_pct']} %)")
            else:
                lines.append(f"oczko ~{pr['suggested_pond_area_m2']:.0f} m², dopływ z 20 mm: "
                             f"{pr['inflow_runoff_m3']:.0f} m³ (brutto {pr['inflow_gross_m3']:.0f} m³)")
        ax.set_title("Proponowane miejsca retencji\n" + ("\n".join(lines) if lines else "brak propozycji"))
        self.zoom(ax)

    def p_twi(self, ax):
        self.base(ax, 0.5)
        im = ax.imshow(self.r["twi"], extent=self.extent, cmap="Blues", alpha=0.85,
                       vmin=np.quantile(self.r["twi"], 0.02), vmax=np.quantile(self.r["twi"], 0.99),
                       interpolation="nearest")
        self.outside_veil(ax)
        self.outline(ax)
        cb = plt.colorbar(im, ax=ax, shrink=0.75)
        cb.set_label("TWI = ln(a / tan β)")
        cb.outline.set_visible(False)
        ax.set_title(f"Wskaźnik wilgotności topograficznej (TWI)\nśrednio {self.res.facts['twi_mean']}")
        self.zoom(ax)

    def save_all(self, prefix: str) -> list[str]:
        panels = [("1_wysokosci", self.p_elevation), ("2_spadki", self.p_slope),
                  ("3_strefy", self.p_zones), ("4_splyw", self.p_flow),
                  ("5_propozycje", self.p_proposals)]
        paths = []
        for name, fn in panels:
            fig, ax = plt.subplots(figsize=(7.5, 6.2), layout="constrained")
            fn(ax)
            fig.suptitle(f"{self.pid} · {self.desc}", x=0.01, ha="left", fontsize=9, color=INK2)
            p = OUT / f"{prefix}_{name}.png"
            fig.savefig(p, dpi=130)
            plt.close(fig)
            paths.append(str(p))
        fig, axs = plt.subplots(2, 3, figsize=(20, 12.5), layout="constrained")
        for ax, fn in zip(axs.ravel(), [self.p_elevation, self.p_slope, self.p_zones,
                                        self.p_flow, self.p_proposals, self.p_twi]):
            fn(ax)
        fig.suptitle(f"Teren i spływ wody – {self.pid} · {self.desc}", x=0.01, ha="left",
                     fontsize=13, fontweight="bold")
        p = OUT / f"{prefix}_przeglad.png"
        fig.savefig(p, dpi=110)
        plt.close(fig)
        paths.append(str(p))
        return paths


def run(pid: str, desc: str) -> dict:
    t0 = time.perf_counter()
    res = T.analyze_parcel(pid)
    t_analysis = time.perf_counter() - t0
    prefix = pid.replace("/", "-")
    (OUT / f"{prefix}.facts.json").write_text(json.dumps(res.facts, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    (OUT / f"{prefix}.geojson").write_text(json.dumps(res.geojson, ensure_ascii=False),
                                           encoding="utf-8")
    t1 = time.perf_counter()
    pngs = Plotter(res, pid, desc).save_all(prefix)
    f = res.facts
    row = {
        "parcel_id": pid, "desc": desc, "area_ha": f["parcel_area_ha"], "step_m": f["grid_step_m"],
        "nmt_points": f["nmt_points"], "slope_mean_pct": f["slope_mean_pct"],
        "slope_max_pct": f["slope_max_pct"], "relief_m": f["relief_m"],
        "n_hills": f["n_hills"], "n_depressions": f["n_depressions"],
        "largest_depression": f["largest_depression"], "outlets": f["outlets"],
        "proposals": f["proposals"], "timing_s": f["timing_s"],
        "analysis_s": round(t_analysis, 2), "plots_s": round(time.perf_counter() - t1, 2),
        "pngs": pngs,
    }
    return row


def main(argv: list[str]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # konsola Windows (cp1250)
    OUT.mkdir(exist_ok=True)
    ids = argv or list(PARCELS)
    rows = []
    for pid in ids:
        print(f"→ {pid} …", flush=True)
        try:
            row = run(pid, PARCELS.get(pid, ""))
        except Exception as exc:  # noqa: BLE001
            print(f"   BŁĄD: {exc}", flush=True)
            rows.append({"parcel_id": pid, "error": str(exc)})
            continue
        rows.append(row)
        mo = row["outlets"][0] if row["outlets"] else {}
        ld = row["largest_depression"] or {}
        print(f"   {row['area_ha']} ha, krok {row['step_m']} m, {row['nmt_points']} pkt | "
              f"spadek śr {row['slope_mean_pct']} % maks {row['slope_max_pct']} % | "
              f"Δh {row['relief_m']} m | zagłębień {row['n_depressions']} "
              f"(najw. {ld.get('volume_m3', '-')} m³) | wyjście {mo.get('direction', '-')} "
              f"{mo.get('share_of_parcel_pct', '-')} % | propozycje "
              f"{[p['type'] for p in row['proposals']]} | czas {row['timing_s']}", flush=True)
    (OUT / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
