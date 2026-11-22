"""Ceny skupu z GUS BDL (A12) → app/data/prices/gus_prices.csv + gus_price_variables.csv.

    docker compose run --rm -e DEMO_OFFLINE=false backend python scripts/build_prices.py [--years 2021-2025]
    … --years 2013-2020 --append   (A16b: dopisuje lata do istniejących plików, zmienne z gus_price_variables.csv,
                                     pierwszy błąd / limit API → przerwanie bez zapisu i bez ponawiania)

Temat P2967 „Przeciętne ceny skupu ważniejszych produktów rolnych (dane miesięczne)” – dla każdego produktu zmienna
z wymiarem „rok” (średnia roczna, zł/dt), poziom województw (unit-level=2) i Polska (unit-level=0).
API BDL (bdl.stat.gov.pl/api/v1): `/variables/search` (nazwa + temat) i `/data/by-variable/{id}`; przerwa 1,5 s
między zapytaniami (limity API – `/variables` bywa zablokowane na IP sieci: 1000 żądań / 12 h). Wynik w repo –
analiza nie pyta GUS w czasie działania. Licencja: dane GUS – wykorzystanie z podaniem źródła.
"""

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.http import request  # noqa: E402

B = "https://bdl.stat.gov.pl/api/v1"
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "prices"
SUBJECT = "P2967"
# produkt (fraza wyszukiwania, fragment nazwy zmiennej) → uprawy z crops.csv
PRODUCTS = {
    "pszenica": ("pszenica", ["pszenica_ozima", "zboza_ozime"]),
    "żyto": ("żyto", ["zyto"]),
    "jęczmień": ("jęczmień", ["jeczmien_ozimy", "jeczmien_jary", "zboza_jare"]),
    "owies": ("owies", ["owies"]),
    "pszenżyto": ("pszenżyto", ["pszenzyto_ozime"]),
    "kukurydza": ("kukurydza", ["kukurydza_ziarno"]),
    "rzepak": ("rzepak", ["rzepak", "rzepak_jesien"]),
    "ziemniaki": ("ziemniaki", ["ziemniak"]),
    "buraki": ("buraki", ["burak_cukrowy"]),
}
PAUSE = 1.5
FIELDS = ["produkt", "var_id", "poziom", "jednostka_id", "nazwa", "rok", "zl_dt"]
STRICT = False  # --append: pierwszy błąd → przerwanie (bez ponawiania)


class Abort(Exception):
    pass


async def get(path: str, params: dict) -> dict | None:
    r = await request("GET", B + path, source="GUS BDL", timeout_s=30, max_bytes=5_000_000,
                      params={**params, "format": "json", "lang": "pl"})
    await asyncio.sleep(PAUSE)
    if r.status_code != 200:
        print(f"  {path}: HTTP {r.status_code} {r.text[:120]}")
        if STRICT:
            raise Abort(f"HTTP {r.status_code}")
        return None
    return json.loads(r.text)


def known_variables() -> dict[str, dict]:
    with open(OUT / "gus_price_variables.csv", encoding="utf-8") as f:
        return {r["produkt"]: r for r in csv.DictReader(f) if r["var_id"]}


async def append(years: list[int]) -> None:
    """Dopisuje lata `years` do gus_prices.csv – zmienne już znane (bez /variables/search), wiersze z istniejących
    lat zostają; jakikolwiek błąd → nic nie jest zapisywane."""
    global STRICT
    STRICT = True
    path = OUT / "gus_prices.csv"
    with open(path, encoding="utf-8") as f:
        old = list(csv.DictReader(f))
    have = {(r["produkt"], r["poziom"], r["jednostka_id"], int(r["rok"])) for r in old}
    new = []
    try:
        for key, v in known_variables().items():
            for level in (2, 0):
                d = await get(f"/data/by-variable/{v['var_id']}", {"unit-level": level, "year": years, "page-size": 100})
                n = 0
                for unit in (d or {}).get("results", []):
                    for val in unit.get("values", []):
                        k = (key, "woj" if level == 2 else "polska", unit["id"], int(val["year"]))
                        if val.get("val") is None or k in have:
                            continue
                        new.append({"produkt": key, "var_id": v["var_id"], "poziom": k[1], "jednostka_id": unit["id"],
                                    "nazwa": unit["name"].lower(), "rok": val["year"], "zl_dt": val["val"]})
                        n += 1
                print(f"{key} (poziom {level}): {n} wartości")
    except Exception as exc:  # noqa: BLE001 – limit / błąd: przerwij, nie zapisuj
        print(f"PRZERWANE: {exc} – plik bez zmian")
        raise SystemExit(1) from exc
    rows = sorted(old + new, key=lambda r: (r["produkt"], r["poziom"], r["jednostka_id"], int(r["rok"])))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"dopisano {len(new)} cen (lata {years[0]}–{years[-1]}) → {path}")


async def annual_variable(phrase: str, fragment: str) -> dict | None:
    d = await get("/variables/search", {"name": phrase, "subject-id": SUBJECT, "page-size": 100})
    for x in (d or {}).get("results", []):
        if (x.get("n1") or "").strip() == "rok" and fragment in (x.get("n2") or "").lower():
            return x
    return None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2021-2025")
    ap.add_argument("--append", action="store_true", help="dopisz lata do istniejącego pliku (A16b)")
    a = ap.parse_args()
    y0, y1 = (int(v) for v in a.years.split("-"))
    years = list(range(y0, y1 + 1))
    if a.append:
        await append(years)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    rows, vars_out = [], []
    t0 = time.monotonic()
    for key, (phrase, crops) in PRODUCTS.items():
        v = await annual_variable(phrase, phrase)
        if v is None:
            print(f"{key}: brak zmiennej rocznej w {SUBJECT}")
            vars_out.append({"produkt": key, "var_id": "", "nazwa": "", "jednostka": "", "uprawy": ";".join(crops),
                             "uwagi": f"brak zmiennej rocznej w temacie {SUBJECT}"})
            continue
        vid = v["id"]
        n = 0
        for level in (2, 0):
            d = await get(f"/data/by-variable/{vid}", {"unit-level": level, "year": years, "page-size": 100})
            for unit in (d or {}).get("results", []):
                for val in unit.get("values", []):
                    if val.get("val") is None:
                        continue
                    rows.append({"produkt": key, "var_id": vid, "poziom": "woj" if level == 2 else "polska",
                                 "jednostka_id": unit["id"], "nazwa": unit["name"].lower(), "rok": val["year"],
                                 "zl_dt": val["val"]})
                    n += 1
        vars_out.append({"produkt": key, "var_id": vid, "nazwa": v.get("n2"), "jednostka": v.get("measureUnitName"),
                         "uprawy": ";".join(crops), "uwagi": f"temat {SUBJECT}, wymiar „rok” – średnia roczna"})
        print(f"{key}: zmienna {vid} „{v.get('n2')}”, {n} wartości")
    with open(OUT / "gus_prices.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(OUT / "gus_price_variables.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["produkt", "var_id", "nazwa", "jednostka", "uprawy", "uwagi"])
        w.writeheader()
        w.writerows(vars_out)
    print(f"zapisano {len(rows)} cen ({time.monotonic() - t0:.0f} s) → {OUT}")


asyncio.run(main())
