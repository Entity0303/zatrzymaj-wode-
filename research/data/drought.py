"""C3b – kalibracja wrażliwości na suszę z plonów GUS (lata suche vs średnia 10 lat).

    python research/data/drought.py

Wejście: gus_yields_woj.csv (2016–2025) + rok 2015 z GUS BDL (cache w gus_raw/).
Wyjście: drought_sensitivity.csv, drought_summary.csv; ranking na stdout.
crops.csv NIE jest zmieniany – propozycja Ky trafia tylko do drought_summary.csv.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_gus as G  # noqa: E402

DRY_YEARS = [2015, 2018, 2019]
BASE_YEARS = list(range(2016, 2026))  # średnia 10 lat
FAO33_VERIFIED = {"pszenica_ozima", "kukurydza_ziarno", "ziemniak", "burak_cukrowy", "straczkowe"}
EXCLUDED = {"drzewa_owocowe": "nie do kalibracji: spadki 2019 głównie od przymrozków wiosennych, "
                              "nie od suszy; brak 2016 w serii"}


def series_year(var_id: int, year: int) -> dict[str, float]:
    d = G.get(f"data/by-variable/{var_id}", [("unit-level", 2), ("page-size", 100), ("year", year)])
    out = {}
    for unit in d.get("results", []):
        for v in unit["values"]:
            if v.get("attrId") == 1 and v.get("val") is not None and int(v["year"]) == year:
                out[unit["id"][2:4]] = float(v["val"])
    return out


def yields_2015(crop: str) -> dict[str, float]:
    num, den, _ = G.MAPPING[crop]
    nums = [series_year(v, 2015) for v in num]
    if den is None:
        return nums[0]
    dens = [series_year(v, 2015) for v in den]
    out = {}
    for woj in G.WOJ:
        pairs = [(n.get(woj), a.get(woj)) for n, a in zip(nums, dens)]
        pairs = [(x, z) for x, z in pairs if x is not None and z]
        if pairs:
            out[woj] = sum(x for x, _ in pairs) / sum(z for _, z in pairs)
    return out


def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return my - b * mx, b


def spearman(a: list[float], b: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else float("nan")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    crops = {r["crop_id"]: r for r in csv.DictReader(open(HERE / "crops.csv", encoding="utf-8"))}
    data: dict[str, dict[tuple[str, int], float]] = defaultdict(dict)
    for r in csv.DictReader(open(HERE / "gus_yields_woj.csv", encoding="utf-8")):
        data[r["crop_id"]][(r["woj_kod"], int(r["rok"]))] = float(r["plon_dt_ha"])
    # tylko uprawy w rankingu (gatunki zamiast grup) – grupy byłyby duplikatami serii
    ranked = [c for c in data if crops[c]["in_ranking"] == "tak"]

    rows, summary = [], []
    for crop in ranked:
        d = data[crop]
        for woj, val in yields_2015(crop).items():
            d[(woj, 2015)] = val
        drops, drops_tr = [], []
        for woj in G.WOJ:
            base = [(y, d[(woj, y)]) for y in BASE_YEARS if (woj, y) in d]
            if len(base) < 8:  # za krótka seria (np. truskawki od 2021)
                continue
            mean10 = sum(v for _, v in base) / len(base)
            a, b = linfit([y for y, _ in base], [v for _, v in base])
            for y in DRY_YEARS:
                if (woj, y) not in d:
                    continue
                val = d[(woj, y)]
                trend = a + b * y
                sp = 100 * (mean10 - val) / mean10
                sp_tr = 100 * (trend - val) / trend
                drops.append(sp)
                drops_tr.append(sp_tr)
                rows.append({"crop_id": crop, "woj": woj, "woj_nazwa": G.WOJ[woj], "rok": y,
                             "plon": round(val, 1), "srednia_10l": round(mean10, 1),
                             "spadek_pct": round(sp, 1), "spadek_wzgl_trendu_pct": round(sp_tr, 1)})
        if not drops:
            summary.append({"crop_id": crop, "n": 0, "uwagi": "brak lat suchych w serii GUS"})
            continue
        by_year = {y: [r["spadek_pct"] for r in rows if r["crop_id"] == crop and r["rok"] == y]
                   for y in DRY_YEARS}
        summary.append({
            "crop_id": crop, "n": len(drops),
            "spadek_sredni_pct": round(sum(drops) / len(drops), 1),
            "spadek_trend_pct": round(sum(drops_tr) / len(drops_tr), 1),
            **{f"spadek_{y}_pct": (round(sum(v) / len(v), 1) if v else "") for y, v in by_year.items()},
            "spadek_max_pct": round(max(drops), 1),
            "ky_crops": float(crops[crop]["ky_total"]),
            "uwagi": "",
        })

    # Propozycja Ky: prosta Ky = a + b·spadek dopasowana TYLKO na uprawach z Ky zweryfikowanym
    # w FAO-33 (tab. 1 Moutonnet, FAO/IAEA). Skalowanie do jednej kotwicy (pszenica) przesadza,
    # bo pszenica ma bardzo mały spadek względem trendu.
    calib = [s for s in summary if s.get("n") and s["crop_id"] in FAO33_VERIFIED]
    a, b = linfit([s["spadek_trend_pct"] for s in calib], [s["ky_crops"] for s in calib])
    for s in summary:
        if not s.get("n"):
            continue
        if s["crop_id"] in EXCLUDED:
            s["ky_proponowane"] = ""
            s["uwagi"] = EXCLUDED[s["crop_id"]]
            continue
        s["ky_proponowane"] = round(min(1.4, max(0.6, a + b * s["spadek_trend_pct"])), 2)
        if s["crop_id"] in FAO33_VERIFIED:
            s["uwagi"] = "Ky zweryfikowane w FAO-33 – zostaje; punkt kalibracji"
    print(f"Kalibracja: Ky = {a:.3f} + {b:.4f}·spadek_trend_pct "
          f"(na {len(calib)} uprawach z FAO-33: {', '.join(s['crop_id'] for s in calib)})")

    with open(HERE / "drought_sensitivity.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    fields = ["crop_id", "n", "spadek_sredni_pct", "spadek_trend_pct", "spadek_2015_pct",
              "spadek_2018_pct", "spadek_2019_pct", "spadek_max_pct", "ky_crops", "ky_proponowane", "uwagi"]
    good = sorted([s for s in summary if s.get("n")], key=lambda s: -s["spadek_trend_pct"])
    with open(HERE / "drought_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(good + [s for s in summary if not s.get("n")])

    print(f"{'uprawa':20s} {'n':>3s} {'śr.%':>6s} {'trend%':>7s} {'2015':>6s} {'2018':>6s} {'2019':>6s} {'Ky':>5s} {'Ky prop':>7s}")
    for s in good:
        print(f"{s['crop_id']:20s} {s['n']:3d} {s['spadek_sredni_pct']:6.1f} {s['spadek_trend_pct']:7.1f} "
              f"{s['spadek_2015_pct']!s:>6s} {s['spadek_2018_pct']!s:>6s} {s['spadek_2019_pct']!s:>6s} "
              f"{s['ky_crops']:5.2f} {s['ky_proponowane']!s:>7s}")
    for s in summary:
        if not s.get("n"):
            print(f"{s['crop_id']:20s} – {s['uwagi']}")
    rho = spearman([s["spadek_trend_pct"] for s in good], [s["ky_crops"] for s in good])
    print(f"Spearman (spadek względem trendu vs Ky z crops.csv): {rho:.2f}")


if __name__ == "__main__":
    main()
