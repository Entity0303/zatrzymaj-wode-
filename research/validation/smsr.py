"""C7 – walidacja z IUNG SMSR (System Monitoringu Suszy Rolniczej): nasz KBW (P − ET0) vs ocena IUNG.

    python research/validation/smsr.py

Co porównujemy:
- IUNG SMSR (susza.iung.pulawy.pl) publikuje dla każdej gminy, roku i okresu 60-dniowego (14 okresów,
  21.III–20.V … 1.VIII–30.IX) ocenę „zagrożenie suszą: + / −” dla 15 upraw i 4 kategorii gleby oraz
  progi KBW z Rozporządzenia MRiRW z 11.04.2019. Liczbowego KBW dla gminy/punktu serwis nie udostępnia
  (tylko mapy PNG; geoserver IUNG ma wyłącznie warstwy kategorii gleb).
- My liczymy KBW = Σ(P − ET0) w tym samym oknie 60 dni w punkcie działki:
    P: NASA POWER (PRECTOTCORR) albo stacje IMGW (IDW, C4),  ET0: FAO-56 Penman-Monteith z NASA POWER
    (ta sama funkcja co backend: backend/app/analysis/et0.py),
  i stosujemy TE SAME progi IUNG dla uprawy, kategorii gleby działki i okresu → nasza ocena + / −.
- Zgodność = ocena nasza == ocena IUNG dla gminy działki (kategoria gleby działki).

Ograniczenia: IUNG ocenia gminę (KBW z interpolacji stacji IMGW, ETP wg własnej metody), my – punkt;
serwis SMSR ma tylko lata 2020–2026 (2018 i 2019 niedostępne).
"""

from __future__ import annotations

import csv
import html
import importlib.util
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DATA = HERE / "data"
RAW = DATA / "smsr_raw"
OUT = HERE / "out"
sys.path.insert(0, str(HERE.parent / "precip"))
import precip as PR  # noqa: E402  (stacje IMGW offline, C4)

_spec = importlib.util.spec_from_file_location("et0", REPO / "backend" / "app" / "analysis" / "et0.py")
ET0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ET0)

SMSR = "https://susza.iung.pulawy.pl"
NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
UA = "zatrzymaj-wode-research/0.1"
YEARS_WANTED = [2018, 2019, 2023]          # z zadania C7
YEARS_SMSR = [2020, 2021, 2022, 2023, 2024, 2025]  # lata dostępne w serwisie SMSR (2026 – sezon w toku)
PERIODS = [("03-21", "05-20"), ("04-01", "05-31"), ("04-11", "06-10"), ("04-21", "06-20"), ("05-01", "06-30"),
           ("05-11", "07-10"), ("05-21", "07-20"), ("06-01", "07-31"), ("06-11", "08-10"), ("06-21", "08-20"),
           ("07-01", "08-31"), ("07-11", "09-10"), ("07-21", "09-20"), ("08-01", "09-30")]

# działki z C4 (środek z research/precip/data/parcels.json); gmina TERYT = prefiks numeru działki;
# kategoria IUNG = dominująca (.ai/test-parcels.md; 121601 – GetFeatureInfo IUNG z C1/C5)
PARCELS = {
    "201305_2.0038.6/1": {"gmina": "2013052", "kat": "III", "opis": "podlaskie, Kobylin-Borzymy"},
    "061704_2.0011.383/2": {"gmina": "0617042", "kat": "IV", "opis": "lubelskie, Rybczewice"},
    "040703_5.0020.76": {"gmina": "0407035", "kat": "III", "opis": "kujawsko-pomorskie, Gniewkowo"},
    "121601_5.0002.770": {"gmina": "1216015", "kat": "III", "opis": "małopolskie, stok"},
}
CROP_IDS = {  # nazwa SMSR → crop_id (research/data/crops.csv)
    "Zboża ozime": "zboza_ozime", "Zboża jare": "zboza_jare", "Kukurydza na ziarno": "kukurydza_ziarno",
    "Kukurydza na kiszonkę": "kukurydza_kiszonka", "Rzepak i rzepik": "rzepak", "Ziemniak": "ziemniak",
    "Burak cukrowy": "burak_cukrowy", "Chmiel": "chmiel", "Tytoń": "tyton", "Warzywa gruntowe": "warzywa",
    "Krzewy owocowe": "krzewy_owocowe", "Drzewa owocowe": "drzewa_owocowe", "Truskawki": "truskawki",
    "Rośliny strączkowe": "straczkowe",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_get(url: str, timeout: float = 60.0, max_bytes: int = 5_000_000) -> tuple[bytes, float]:
    last = None
    for a in range(3):
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Connection": "close"})
            with _OPENER.open(req, timeout=timeout) as r:
                body = r.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise RuntimeError("odpowiedź za duża")
            return body, time.monotonic() - t0
        except urllib.error.HTTPError as e:
            e.close()
            last = f"HTTP {e.code}"
            if 300 <= e.code < 500:
                break
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(1 + a)
    raise RuntimeError(f"{last}: {url}")


def cached(path: Path, url: str) -> tuple[str, float | None]:
    if path.exists():
        return path.read_text(encoding="utf-8"), None
    body, dt = http_get(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = body.decode("utf-8", "replace")
    path.write_text(text, encoding="utf-8")
    time.sleep(0.5)
    return text, dt


def _table_text(page: str) -> str:
    t = re.sub(r"<script.*?</script>", "", page, flags=re.S)
    t = re.sub(r"</t[dh]>", " | ", t)
    t = re.sub(r"</tr>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


# ---------------------------------------------------------------------------------- parsowanie SMSR

def parse_thresholds(page: str) -> dict[str, dict[str, list[float | None]]]:
    """Progi KBW: uprawa → kategoria (I–IV) → 14 wartości [mm] (None = 'x', okres nie dotyczy)."""
    t = _table_text(page)
    i = t.find("Okres sześciodekadowy")
    cells = [c.strip() for c in re.split(r"\|", t[i:])]
    cells = [c for c in cells if c]
    out: dict[str, dict] = {}
    k, crop = 0, None
    while k < len(cells):
        c = cells[k]
        if c in CROP_IDS:
            crop = c
            out[crop] = {}
            k += 1
            continue
        if crop and c in ("I", "II", "III", "IV") and k + 14 < len(cells) + 1:
            vals = []
            for v in cells[k + 1:k + 15]:
                try:
                    vals.append(float(v.replace("−", "-")))
                except ValueError:  # 'x' (okres nie dotyczy) albo '-' (brak progu)
                    vals.append(None)
            out[crop][c] = vals
            k += 15
            continue
        k += 1
    return out


def parse_gmina(page: str) -> dict[str, dict[str, list[str]]]:
    """Flagi gminy: kategoria → uprawa → 14 znaków ('+' susza, '-' brak, 'x' nie dotyczy,
    '*' kategoria nie występuje w gminie, '#' uprawa niewskazana na tej kategorii)."""
    t = _table_text(page)
    out: dict[str, dict] = {}
    for m in re.finditer(r"Kategoria gleby (IV|III|II|I)\b", t):
        cat = m.group(1)
        block = t[m.end(): t.find("Kategoria gleby", m.end()) if "Kategoria gleby" in t[m.end():] else
                  t.find("Udział powierzchni", m.end())]
        rows = {}
        for line in block.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if parts and parts[0] in CROP_IDS and len(parts) >= 15:
                rows[parts[0]] = parts[1:15]
        out[cat] = rows
    return out


# ---------------------------------------------------------------------------------- nasze KBW

def nasa_full(lon: float, lat: float, key: str, start: date, end: date) -> dict:
    q = urllib.parse.urlencode({
        "parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN", "community": "AG",
        "longitude": f"{lon:.4f}", "latitude": f"{lat:.4f}",
        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON"})
    text, _ = cached(DATA / "nasa" / f"nasa_full_{key}.json", f"{NASA_URL}?{q}")
    return json.loads(text)


def daily_et0_p(d: dict, lat: float, start: date, end: date):
    block = d["properties"]["parameter"]
    elev = d["geometry"]["coordinates"][2] if len(d["geometry"]["coordinates"]) > 2 else 0.0
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    keys = [x.strftime("%Y%m%d") for x in days]

    def s(name):
        a = np.array([block[name].get(k, -999) for k in keys], float)
        a[a <= -998] = np.nan
        return a

    doy = np.array([x.timetuple().tm_yday for x in days])
    pm = ET0.et0_penman_monteith(s("T2M_MAX"), s("T2M_MIN"), s("RH2M"), s("WS2M"), s("ALLSKY_SFC_SW_DWN"),
                                 lat, float(elev or 0), doy)
    hg = ET0.et0_hargreaves(s("T2M_MAX"), s("T2M_MIN"), lat, doy)
    et0 = np.where(np.isnan(pm), hg, pm)
    return days, s("PRECTOTCORR"), et0


def window_sum(days, arr, a: date, b: date, max_missing: float = 0.1):
    idx = [i for i, x in enumerate(days) if a <= x <= b]
    part = arr[idx]
    if np.isnan(part).mean() > max_missing:
        return float("nan")
    return float(np.nanmean(part) * len(part))


# ---------------------------------------------------------------------------------- główny przebieg

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    log = {"smsr_seconds": [], "nasa_seconds": []}
    prog_page, dt = cached(RAW / "progi.html", f"{SMSR}/progi/")
    thr = parse_thresholds(prog_page)
    (DATA / "smsr_progi.json").write_text(json.dumps(thr, ensure_ascii=False, indent=0), encoding="utf-8")

    pts = json.loads((HERE.parent / "precip" / "data" / "parcels.json").read_text(encoding="utf-8"))
    start, end = date(2016, 1, 1), date(2025, 12, 31)
    flags_all = {}
    rows, kbw_rows = [], []
    for pid, meta in PARCELS.items():
        pt = pts[pid]
        key = pid.replace("/", "-")
        nasa = nasa_full(pt["lon"], pt["lat"], key, start, end)
        days, p_nasa, et0 = daily_et0_p(nasa, pt["lat"], start, end)
        st = PR.nearest_stations(pt["lon"], pt["lat"], n=3, max_km=30, start=start, end=end) or \
            PR.nearest_stations(pt["lon"], pt["lat"], n=3, max_km=50, start=start, end=end)
        p_imgw = PR.idw(PR.imgw_daily(st, start, end), st) if st else np.full(len(days), np.nan)
        # nasze KBW we wszystkich latach (także 2018, 2019 – bez porównania z IUNG)
        for y in sorted(set(YEARS_WANTED) | set(YEARS_SMSR)):
            for k, (a, b) in enumerate(PERIODS, 1):
                da = date.fromisoformat(f"{y}-{a}")
                db = date.fromisoformat(f"{y}-{b}")
                kbw_rows.append({
                    "parcel_id": pid, "rok": y, "okres": k, "od": da.isoformat(), "do": db.isoformat(),
                    "P_nasa_mm": round(window_sum(days, p_nasa, da, db), 1),
                    "P_imgw_mm": round(window_sum(days, p_imgw, da, db), 1),
                    "ET0_mm": round(window_sum(days, et0, da, db), 1),
                })
                r = kbw_rows[-1]
                r["KBW_nasa_mm"] = round(r["P_nasa_mm"] - r["ET0_mm"], 1)
                r["KBW_imgw_mm"] = round(r["P_imgw_mm"] - r["ET0_mm"], 1) if math.isfinite(r["P_imgw_mm"]) else ""
        # flagi IUNG dla gminy
        for y in YEARS_SMSR:
            try:
                page, dt = cached(RAW / f"wykazy_{y}_{meta['gmina']}.html", f"{SMSR}/wykazy/{y},{meta['gmina']}/")
            except RuntimeError as exc:
                print(f"IUNG SMSR nie odpowiada ({pid}, {y}): {exc} – pomijam")
                continue
            if dt:
                log["smsr_seconds"].append(round(dt, 2))
            g = parse_gmina(page)
            flags_all[f"{meta['gmina']}_{y}"] = g
            for cat, cat_rows in g.items():  # wszystkie kategorie; kategoria działki oznaczona
              for crop, flags in cat_rows.items():
                for k, fl in enumerate(flags, 1):
                    if fl not in "+-":
                        continue
                    th = thr.get(crop, {}).get(cat, [None] * 14)[k - 1]
                    if th is None:
                        continue
                    kr = next(r for r in kbw_rows if r["parcel_id"] == pid and r["rok"] == y and r["okres"] == k)
                    ours_n = "+" if kr["KBW_nasa_mm"] < th else "-"
                    ours_i = ("+" if kr["KBW_imgw_mm"] < th else "-") if kr["KBW_imgw_mm"] != "" else ""
                    rows.append({"parcel_id": pid, "gmina": meta["gmina"], "kat": cat,
                                 "kat_dzialki": cat == meta["kat"], "rok": y,
                                 "okres": k, "uprawa": CROP_IDS[crop], "prog_mm": th,
                                 "KBW_nasa_mm": kr["KBW_nasa_mm"], "KBW_imgw_mm": kr["KBW_imgw_mm"],
                                 "iung": fl, "nasz_nasa": ours_n, "nasz_imgw": ours_i,
                                 "zgodne_nasa": ours_n == fl, "zgodne_imgw": (ours_i == fl) if ours_i else ""})
        print(f"{pid}: stacje {[(s.name, s.dist_km) for s in st]}", flush=True)

    (DATA / "smsr_gminy.json").write_text(json.dumps(flags_all, ensure_ascii=False), encoding="utf-8")
    for name, rr in (("smsr_porownanie.csv", rows), ("kbw_okresy.csv", kbw_rows)):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rr[0]))
            w.writeheader()
            w.writerows(rr)
    summarize(rows, kbw_rows)


def _agree(rows, src):
    rr = [r for r in rows if r[f"zgodne_{src}"] != ""]
    ok = sum(1 for r in rr if r[f"zgodne_{src}"] is True)
    tp = sum(1 for r in rr if r["iung"] == "+" and r[f"nasz_{src}"] == "+")
    fn = sum(1 for r in rr if r["iung"] == "+" and r[f"nasz_{src}"] == "-")
    fp = sum(1 for r in rr if r["iung"] == "-" and r[f"nasz_{src}"] == "+")
    return {"n": len(rr), "zgodne": ok, "pct": round(100 * ok / len(rr), 1) if rr else None,
            "susza_iung": tp + fn, "susza_obie": tp, "susza_tylko_iung": fn, "susza_tylko_nasza": fp}


def summarize(all_rows, kbw_rows):
    summ = {"wszystkie_kategorie": {s: _agree(all_rows, s) for s in ("nasa", "imgw")}}
    for cat in ("I", "II", "III", "IV"):
        summ[f"kategoria_{cat}"] = {s: _agree([r for r in all_rows if r["kat"] == cat], s) for s in ("nasa", "imgw")}
    rows = [r for r in all_rows if r["kat_dzialki"]]
    summ["wszystko"] = {s: _agree(rows, s) for s in ("nasa", "imgw")}
    for pid in PARCELS:
        summ[pid] = {s: _agree([r for r in rows if r["parcel_id"] == pid], s) for s in ("nasa", "imgw")}
    for y in YEARS_SMSR:
        summ[str(y)] = {s: _agree([r for r in rows if r["rok"] == y], s) for s in ("nasa", "imgw")}
    for crop in ("zboza_ozime", "zboza_jare", "kukurydza_ziarno", "rzepak", "ziemniak"):
        summ[crop] = {s: _agree([r for r in rows if r["uprawa"] == crop], s) for s in ("nasa", "imgw")}
    # porównanie „okresowe” niezależne od uprawy: KBW NASA vs IMGW
    diffs = [r["KBW_nasa_mm"] - r["KBW_imgw_mm"] for r in kbw_rows if r["KBW_imgw_mm"] != ""]
    summ["kbw_nasa_minus_imgw_mm"] = {"srednio": round(float(np.mean(diffs)), 1),
                                      "mediana": round(float(np.median(diffs)), 1), "n": len(diffs)}
    (OUT / "smsr_podsumowanie.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    for key in ("wszystko", "wszystkie_kategorie", "kategoria_I", "kategoria_II", "kategoria_III", "kategoria_IV",
                "2023", "zboza_ozime", "kukurydza_ziarno"):
        a = summ[key]
        print(f"{key:20s} NASA {a['nasa']['zgodne']}/{a['nasa']['n']} ({a['nasa']['pct']} %), susza IUNG "
              f"{a['nasa']['susza_iung']}, obie {a['nasa']['susza_obie']}, tylko nasza {a['nasa']['susza_tylko_nasza']} | "
              f"IMGW {a['imgw']['zgodne']}/{a['imgw']['n']} ({a['imgw']['pct']} %), obie {a['imgw']['susza_obie']}, "
              f"tylko nasza {a['imgw']['susza_tylko_nasza']}")
    print("KBW NASA − IMGW:", summ["kbw_nasa_minus_imgw_mm"])


if __name__ == "__main__":
    main()
