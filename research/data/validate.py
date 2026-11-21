"""Walidacja spójności research/data/crops.csv (i odwołań w plikach GUS).

    python research/data/validate.py            # kod wyjścia 1 przy błędach
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent

REQUIRED = ["crop_id", "name_pl", "backend_id", "iung_name", "kc_ini", "kc_mid", "kc_end",
            "faza_ini_dni", "faza_dev_dni", "faza_mid_dni", "faza_late_dni",
            "typowy_siew", "typowy_zbior", "ozima", "ky_total", "ky_fazy",
            "root_depth_min_m", "root_depth_max_m", "p_depletion", "irrigation_practice",
            "min_przerwa_lat", "zle_przedplony", "dobre_przedplony",
            "gleby_odpowiednie", "gleby_nieodpowiednie", "zrodla"]
IRRIGATION = {"not_practiced", "optional", "common"}
PHASE_KEYS = {"ini", "dev", "mid", "late"}
IUNG_CATS = {"I", "II", "III", "IV"}
KOMPLEKSY = {str(i) for i in range(1, 15)} | {"1z", "2z", "3z"}
MMDD = re.compile(r"^(\d{2})-(\d{2})$")


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(row, key, errs, cid):
    try:
        return float(row[key])
    except (ValueError, TypeError, KeyError):
        errs.append(f"{cid}: {key} nie jest liczbą ({row.get(key)!r})")
        return None


def _mmdd(val, key, errs, cid):
    m = MMDD.match(val or "")
    if not m:
        errs.append(f"{cid}: {key} ma być MM-DD ({val!r})")
        return
    try:
        date(2001, int(m.group(1)), int(m.group(2)))
    except ValueError:
        errs.append(f"{cid}: {key} – nieistniejąca data ({val!r})")


def _soils(val, key, errs, cid):
    if not val:
        return
    for part in val.split(";"):
        if ":" not in part:
            errs.append(f"{cid}: {key} – oczekiwano 'iung:...;kompleksy:...' ({part!r})")
            continue
        kind, items = part.split(":", 1)
        allowed = {"iung": IUNG_CATS, "kompleksy": KOMPLEKSY}.get(kind.strip())
        if allowed is None:
            errs.append(f"{cid}: {key} – nieznany klucz {kind!r}")
            continue
        bad = [x for x in items.split(",") if x.strip() not in allowed]
        if bad:
            errs.append(f"{cid}: {key} – nieznane wartości {bad}")


def validate_crops(rows: list[dict]) -> list[str]:
    errs: list[str] = []
    if not rows:
        return ["crops.csv jest pusty"]
    missing_cols = [c for c in REQUIRED if c not in rows[0]]
    if missing_cols:
        return [f"brak kolumn: {missing_cols}"]
    ids = [r["crop_id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errs.append(f"powtórzone crop_id: {sorted(dup)}")
    known = set(ids)
    for r in rows:
        cid = r["crop_id"] or "?"
        if not re.fullmatch(r"[a-z0-9_]+", cid):
            errs.append(f"{cid}: crop_id tylko [a-z0-9_]")
        for k in ("name_pl", "iung_name"):
            if not r[k].strip():
                errs.append(f"{cid}: puste {k}")
        # Kc
        for k in ("kc_ini", "kc_mid", "kc_end"):
            v = _num(r, k, errs, cid)
            if v is not None and not 0.2 <= v <= 1.4:
                errs.append(f"{cid}: {k} = {v} poza zakresem 0,2–1,4")
        # fazy
        phases = [_num(r, k, errs, cid) for k in ("faza_ini_dni", "faza_dev_dni",
                                                    "faza_mid_dni", "faza_late_dni")]
        if all(p is not None for p in phases):
            if any(p <= 0 for p in phases):
                errs.append(f"{cid}: każda faza musi mieć > 0 dni ({phases})")
            if sum(phases) <= 0 or sum(phases) > 366:
                errs.append(f"{cid}: suma faz {sum(phases)} poza 1–366")
        _mmdd(r["typowy_siew"], "typowy_siew", errs, cid)
        _mmdd(r["typowy_zbior"], "typowy_zbior", errs, cid)
        if r.get("start_wegetacji"):
            _mmdd(r["start_wegetacji"], "start_wegetacji", errs, cid)
        if r["ozima"] not in ("tak", "nie"):
            errs.append(f"{cid}: ozima ma być tak/nie ({r['ozima']!r})")
        # Ky
        ky = _num(r, "ky_total", errs, cid)
        if ky is not None and not 0.2 <= ky <= 1.5:
            errs.append(f"{cid}: ky_total = {ky} poza zakresem 0,2–1,5")
        if r["ky_fazy"]:
            for part in r["ky_fazy"].split(";"):
                m = re.fullmatch(r"([a-z]+):([0-9.]+)", part.strip())
                if not m or m.group(1) not in PHASE_KEYS:
                    errs.append(f"{cid}: ky_fazy – zły element {part!r} (ini/dev/mid/late:liczba)")
                elif not 0.1 <= float(m.group(2)) <= 2.0:
                    errs.append(f"{cid}: ky_fazy {part!r} poza 0,1–2,0")
        # korzenie, p
        zmin = _num(r, "root_depth_min_m", errs, cid)
        zmax = _num(r, "root_depth_max_m", errs, cid)
        if zmin is not None and zmax is not None and not 0.1 <= zmin <= zmax <= 3.0:
            errs.append(f"{cid}: korzenie min {zmin} / max {zmax} – wymagane 0,1 ≤ min ≤ max ≤ 3")
        p = _num(r, "p_depletion", errs, cid)
        if p is not None and not 0.1 <= p <= 0.8:
            errs.append(f"{cid}: p_depletion = {p} poza 0,1–0,8")
        if r["irrigation_practice"] not in IRRIGATION:
            errs.append(f"{cid}: irrigation_practice ∉ {sorted(IRRIGATION)}")
        prz = _num(r, "min_przerwa_lat", errs, cid)
        if prz is not None and (prz < 0 or prz > 10 or prz != int(prz)):
            errs.append(f"{cid}: min_przerwa_lat = {prz} (liczba całkowita 0–10)")
        # przedplony
        for k in ("zle_przedplony", "dobre_przedplony"):
            vals = [x for x in r[k].split(";") if x]
            bad = [x for x in vals if x not in known]
            if bad:
                errs.append(f"{cid}: {k} wskazuje na nieistniejące crop_id {bad}")
        both = set(filter(None, r["zle_przedplony"].split(";"))) & set(filter(None, r["dobre_przedplony"].split(";")))
        if both:
            errs.append(f"{cid}: ta sama uprawa jako zły i dobry przedplon {sorted(both)}")
        if prz is not None and prz >= 1 and cid not in r["zle_przedplony"].split(";"):
            errs.append(f"{cid}: min_przerwa_lat ≥ 1, a uprawa nie jest swoim złym przedplonem")
        _soils(r["gleby_odpowiednie"], "gleby_odpowiednie", errs, cid)
        _soils(r["gleby_nieodpowiednie"], "gleby_nieodpowiednie", errs, cid)
        if len(r["zrodla"].strip()) < 10:
            errs.append(f"{cid}: brak źródła (zrodla)")
    return errs


def validate_gus(crop_ids: set[str], variables: list[dict], yields: list[dict]) -> list[str]:
    errs = []
    for r in variables:
        if r["crop_id"] not in crop_ids:
            errs.append(f"gus_variables: nieznane crop_id {r['crop_id']!r}")
        if not r["var_id"] and "BRAK DANYCH" not in r["uwagi"]:
            errs.append(f"gus_variables: {r['crop_id']} bez var_id i bez opisu braku")
    covered = {r["crop_id"] for r in variables}
    if crop_ids - covered:
        errs.append(f"gus_variables: brak wiersza dla {sorted(crop_ids - covered)}")
    for r in yields:
        if r["crop_id"] not in crop_ids:
            errs.append(f"gus_yields_woj: nieznane crop_id {r['crop_id']!r}")
            break
        if float(r["plon_dt_ha"]) <= 0:
            errs.append(f"gus_yields_woj: plon ≤ 0 ({r})")
            break
    return errs


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    crops = read_csv(HERE / "crops.csv")
    errs = validate_crops(crops)
    ids = {r["crop_id"] for r in crops}
    if (HERE / "gus_variables.csv").exists() and (HERE / "gus_yields_woj.csv").exists():
        errs += validate_gus(ids, read_csv(HERE / "gus_variables.csv"), read_csv(HERE / "gus_yields_woj.csv"))
    for e in errs:
        print("BŁĄD:", e)
    print(f"{len(crops)} upraw, błędów: {len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
