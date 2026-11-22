"""Sprawdzenie ścieżki demo przed prezentacją (A5d): wyszukanie → analiza bez uprawy → analiza z uprawą → PDF
dla każdej działki demo z app/data/demo_parcels.json (bez flagi needs_fetch), z czasami odpowiedzi.

  docker compose exec backend python scripts/demo_check.py               # serwer z docker compose
  python scripts/demo_check.py --base http://localhost:8000              # z dowolnego miejsca
Kod wyjścia 0 = wszystko 200. Przy DEMO_OFFLINE=true potwierdza, że demo działa bez sieci (z samego cache).
"""

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import httpx

DEMO_FILE = Path(__file__).parents[1] / "app" / "data" / "demo_parcels.json"


def timed(c: httpx.Client, path: str, params: dict) -> tuple[int, float, httpx.Response]:
    t0 = time.perf_counter()
    r = c.get(path, params=params)
    return r.status_code, time.perf_counter() - t0, r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    a = ap.parse_args()
    parcels = [d for d in json.loads(DEMO_FILE.read_text(encoding="utf-8"))["parcels"] if not d.get("needs_fetch")]
    rows, ok = [], True
    with httpx.Client(base_url=a.base, timeout=60) as c:
        examples = c.get("/api/demo/examples").json()
        for d in parcels:
            pid = d["id"]
            steps = [("Wyszukanie (id)", "/api/parcel", {"id": pid})]
            if d.get("query"):
                steps.append(("Wyszukanie (obręb numer)", "/api/parcel", {"id": d["query"]}))
            code, s, r = timed(c, "/api/parcel", {"id": pid})
            if code == 200:
                xs = [p[0] for p in r.json()["geometria"]["coordinates"][0]]
                ys = [p[1] for p in r.json()["geometria"]["coordinates"][0]]
                steps.append(("Wyszukanie (punkt na mapie)", "/api/parcel", {"lon": sum(xs) / len(xs), "lat": sum(ys) / len(ys)}))
            today = dt.date.today().isoformat()
            steps += [("Analiza bez uprawy", "/api/analysis", {"parcel_id": pid, "date": today}),
                      ("PDF bez uprawy", "/api/report.pdf", {"parcel_id": pid, "date": today}),
                      ("Warstwa Teren", "/api/layers/teren", {"parcel_id": pid, "date": today}),
                      ("Warstwa Spływ wody", "/api/layers/splyw", {"parcel_id": pid, "date": today})]
            for e in (x for x in examples if x["parcel_id"] == pid):
                q = {"parcel_id": pid, "crop": e["crop"], "date": e["date"]}
                if e.get("previous_crop"):
                    q["previous_crop"] = e["previous_crop"]
                steps += [(f"Analiza: {e['title']}", "/api/analysis", q), (f"PDF: {e['title']}", "/api/report.pdf", q)]
            for name, path, params in steps:
                code, s, r = timed(c, path, params)
                note = ""
                if code == 200 and path == "/api/analysis":
                    b = r.json()
                    note = f"{b['status']['level']} ({b['status']['score']}), pewność {b['reliability']['confidence']}"
                    t = b.get("terrain")
                    note += (f"; teren: " + ", ".join(f"{z['label'].split(' –')[0]} {round(z['share_pct'])}%"
                                                      for z in t["zones"] if z["share_pct"] >= 1)) if t else \
                        f"; teren: brak ({b.get('terrain_note')})"
                elif code == 200 and path.startswith("/api/layers/"):
                    note = f"{len(r.json()['features']['features'])} obiektów, {len(r.content) // 1000} kB"
                elif code == 409 and path == "/api/parcel" and any(
                        c.get("id") == d.get("id") for c in r.json()["detail"].get("candidates", [])):
                    note = (f"{r.json()['detail']['total']} działki o tym numerze w Polsce – ta jest na liście do wyboru "
                            "(poprawnie)")
                elif code != 200:
                    ok = False
                    try:
                        note = r.json()["detail"]["message"]
                    except Exception:  # noqa: BLE001
                        note = r.text[:100]
                rows.append((d.get("label") or pid, name, code, f"{s:.2f} s", note))
        status = c.get("/api/status").json()
    print("| Działka | Krok | HTTP | Czas | Wynik |\n|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print("\n/api/status:")
    for s in status["services"]:
        print(f"  {s['name']}: {'ok' if s['ok'] else 'NIE'}{' – ' + s['error'] if s['error'] else ''} (cache: {s['cache_entries']})")
    print("\nWYNIK:", "OK – ścieżka demo działa" if ok else "BŁĘDY – zobacz tabelę")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
