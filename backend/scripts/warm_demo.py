"""Przygotowanie demo przed prezentacją (A5d, D55): wszystkie dane działek demo do trwałego cache + PDF-y.

Uruchamiać na DOBREJ sieci (backend działa w `docker compose up`):
  docker compose exec backend python scripts/warm_demo.py --out /reports/examples

Co robi (spokojnie – przerwy między zapytaniami, pomija to, co już jest w cache):
1. Działki z app/data/demo_parcels.json z flagą `needs_fetch` – pobiera z ULDK (po id albo „obręb numer”,
   wybiera działkę z właściwej gminy) i ZAPISUJE w tym pliku (geometria, gmina, obręb…). Przy blokadzie ULDK
   (bezpiecznik) – pomija resztę działek, zostawia flagę.
2. Dla każdej znanej działki demo: analiza bez uprawy (dziś) + analizy z przykładów /api/demo/examples
   (te same działki, uprawy, daty) – to wypełnia cache pogody 10 lat (NASA POWER), prognozy, IUNG, mapy
   glebowo-rolniczej, SoilGrids, KIEG, NMT (teren, A6) i ortofotomapy; potem raport PDF każdego przypadku.
3. A11: zdjęcie satelitarne Sentinel-2 (GET /api/satellite – scena + rok temu) przed analizą każdego przypadku, a na
   końcu szereg 12 mies. (1 punkt / 15 dni) dla każdej działki demo – długo (ok. 3–4 min i 70–110 MB na działkę),
   `--no-satellite-series` pomija szereg. Analiza i raport biorą satelitę z cache (także w DEMO_OFFLINE).
4. Tabela: przypadek, wynik, czas, ile źródeł z cache; liczba wpisów w cache na źródło.
BDOT10k i GUS nie mają jeszcze klientów – nie ma czego pobierać; cache jest na nie gotowy. Gdy NMT nie odpowiada,
teren działek demo pochodzi z zapisanego wyniku (app/data/terrain, prawdziwe NMT z 21.11 – D57).
Wynik jest w pliku cache (CACHE_DB, w Dockerze wolumen /data) – potem można włączyć DEMO_OFFLINE=true.
"""

import argparse
import asyncio
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.core.config import settings  # noqa: E402

settings.demo_warmup = False  # rozgrzewka w tle niepotrzebna – robimy ją tu, po kolei
if settings.demo_offline:
    print("Uwaga: DEMO_OFFLINE=true w środowisku – na czas warm_demo wyłączone (skrypt musi pobierać dane).")
    settings.demo_offline = False

from fastapi.testclient import TestClient  # noqa: E402

from app.core.cache import REGISTRY, breaker, cache_stats  # noqa: E402
from app.core.http import NotFoundError, SourceError  # noqa: E402
from app.demo import EXAMPLES  # noqa: E402
from app.main import app  # noqa: E402
from app.sources import uldk  # noqa: E402


def fill_missing_parcels(pause: float) -> list[str]:
    """ULDK dla działek demo bez geometrii; zapis do app/data/demo_parcels.json."""
    data = json.loads(uldk.DEMO_FILE.read_text(encoding="utf-8"))
    notes = []
    changed = False
    for d in data["parcels"]:
        if not d.get("needs_fetch"):
            continue
        name = d.get("id") or d.get("query")
        if breaker(uldk.SOURCE).open:
            notes.append(f"{name}: pominięta – ULDK ogranicza ruch ({breaker(uldk.SOURCE).reason})")
            continue
        try:
            found = asyncio.run(uldk.by_id(d["id"] or d["query"]))
        except NotFoundError as exc:
            notes.append(f"{name}: nie znaleziono w ULDK ({exc.message})")
            continue
        except SourceError as exc:
            notes.append(f"{name}: ULDK – {exc.message}")
            continue
        finally:
            time.sleep(pause)
        if d.get("gmina"):
            found = [p for p in found if p.commune.lower() == d["gmina"].lower()] or found
        if d.get("numer"):
            found = [p for p in found if p.number == d["numer"]] or found
        if len(found) != 1:
            notes.append(f"{name}: ULDK zwrócił {len(found)} działek – wybierz ręcznie (uzupełnij 'id')")
            continue
        p = found[0]
        d.update(id=p.id, wojewodztwo=p.voivodeship, powiat=p.county, gmina=p.commune, obreb=p.region,
                 numer=p.number, geom_wkt_2180=p.geom_2180.wkt, fetched_at=p.fetched_at.isoformat(timespec="seconds"),
                 source="ULDK GUGiK (warm_demo.py)", needs_fetch=False)
        changed = True
        notes.append(f"{name}: pobrana → {p.id}")
    if changed:
        uldk.DEMO_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        uldk.load_known(force=True)
    return notes


def cases() -> list[tuple[str, dict, str]]:
    """(nazwa, parametry, nazwa pliku PDF) – bez uprawy dla każdej znanej działki demo + przykłady demo."""
    today = dt.date.today().isoformat()
    out = []
    for d in uldk.demo_parcels():
        if d.get("id") and not d.get("needs_fetch"):
            slug = "stan-dzialki-" + d["id"].replace("/", "-").replace(".", "-")
            out.append((f"{d['label']} – bez uprawy", {"parcel_id": d["id"], "date": today}, slug))
    for e in EXAMPLES:
        q = {"parcel_id": e.parcel_id, "crop": e.crop, "date": (e.date or dt.date.today()).isoformat()}
        if e.previous_crop:
            q["previous_crop"] = e.previous_crop
        out.append((e.title, q, e.id))
    return out


async def warm_satellite_series() -> None:
    """Szereg Sentinel-2 z 12 miesięcy (A11) dla działek demo – tylko Earth Search; działka już w cache."""
    from app.analysis import satellite as sat_mod

    settings.sentinel_timeout_s = 20.0
    for pid in dict.fromkeys(e.parcel_id for e in EXAMPLES):  # A13: szereg tylko dla przykładów ze startu
        d = {"id": pid}
        p = uldk.known_by_id(pid)
        if p is None:
            continue
        today = dt.date.today().isoformat()
        if sat_mod._lookup(("series", sat_mod.geom_key(p.geom_4326), today)) is not None:
            print(f"Sentinel-2 szereg {pid}: już w cache (dziś) – pomijam")
            continue
        t0 = time.perf_counter()
        try:
            n, st = await sat_mod.warm_series(p.geom_4326, dt.date.today())
            print(f"Sentinel-2 szereg {d['id']}: {n} punktów, {time.perf_counter() - t0:.0f} s, {st.mb:.1f} MB")
        except SourceError as exc:
            print(f"Sentinel-2 szereg {d['id']}: błąd – {exc.message}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="katalog na PDF-y (np. /reports/examples)")
    ap.add_argument("--pause", type=float, default=2.0, help="przerwa po zapytaniu, które nie było z cache, s")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-satellite-series", action="store_true", help="bez szeregu Sentinel-2 z 12 miesięcy")
    ap.add_argument("--no-satellite", action="store_true",
                    help="bez Sentinel-2 w ogóle (np. przez VPN z limitem danych) – analiza i PDF bez zdjęcia")
    ap.add_argument("--no-hydro", action="store_true", help="bez wody w okolicy (Overpass, IMGW)")
    a = ap.parse_args()
    # GUGiK spokojnie: NMT po kolei z przerwą ≥ 1 s, więcej czasu na całą siatkę (A8)
    settings.nmt_parallel, settings.nmt_chunk_pause_s, settings.nmt_total_timeout_s = 1, 1.0, 120.0
    if a.no_satellite:
        settings.sentinel_enabled = False
        a.no_satellite_series = True
    else:  # przygotowanie cache: więcej czasu na scenę i rok temu niż na żywo
        settings.sentinel_budget_s, settings.sentinel_budget_mb, settings.sentinel_timeout_s = 60.0, 30.0, 20.0
    # Overpass bywa przeciążony: krótki bezpiecznik (jedna porażka nie blokuje reszty działek), przerwa między działkami
    settings.overpass_breaker_s = 20.0
    out = Path(a.out) if a.out else None
    print(f"Cache: {settings.cache_db or '(tylko pamięć – ustaw CACHE_DB, inaczej nic nie zostanie!)'}")
    for line in fill_missing_parcels(a.pause):
        print("ULDK:", line)
    rows = []
    done: dict[str, str] = {}  # działka → opis teren / satelita / woda (każda działka liczona raz)
    with TestClient(app) as c:
        for name, q, slug in cases():
            pid = q["parcel_id"]
            if pid not in done:  # A13: po kolei, jedno zapytanie naraz – teren, satelita, woda; potem analiza z cache
                parts, slow = [], False
                ts = time.perf_counter()
                t = c.get("/api/terrain", params={"parcel_id": pid})
                parts.append(f"teren {t.status_code} {time.perf_counter() - ts:.0f}s")
                slow |= time.perf_counter() - ts > 0.5
                if not a.no_satellite:
                    ts = time.perf_counter()
                    s = c.get("/api/satellite", params={"parcel_id": pid, "date": q["date"]})
                    parts.append(f"satelita {s.json()['status']} {s.json().get('date') or ''} {time.perf_counter() - ts:.0f}s"
                                 if s.status_code == 200 else f"satelita błąd {s.status_code}")
                    slow |= time.perf_counter() - ts > 0.5
                if not a.no_hydro:
                    ts = time.perf_counter()
                    h = c.get("/api/hydro", params={"parcel_id": pid})
                    parts.append(f"woda {h.json()['status']} ({len(h.json().get('features') or [])} ob., wodowskaz "
                                 f"{'tak' if h.json().get('gauge') else 'nie'}) {time.perf_counter() - ts:.0f}s"
                                 if h.status_code == 200 else f"woda błąd {h.status_code}")
                    slow |= time.perf_counter() - ts > 0.5
                done[pid] = "; ".join(parts)
                if slow:
                    time.sleep(a.pause + (5 if not a.no_hydro else 0))
            sat_txt = done[pid]
            t0 = time.perf_counter()
            r = c.get("/api/analysis", params=q)
            t_a = time.perf_counter() - t0
            row = [name, q.get("crop") or "— (bez uprawy)", q["date"]]
            if r.status_code != 200:
                msg = (r.json().get("detail") or {}).get("message", r.text[:80]) if r.headers.get("content-type", "").startswith("application/json") else r.text[:80]
                rows.append(row + [f"błąd {r.status_code}: {msg}", f"{t_a:.2f} s", "–"])
                continue
            b = r.json()
            pdf = "–"
            if not a.no_pdf:
                t1 = time.perf_counter()
                p = c.get("/api/report.pdf", params=q)
                pdf = f"OK {time.perf_counter() - t1:.2f} s" if p.status_code == 200 else f"błąd {p.status_code}"
                if p.status_code == 200 and out:
                    out.mkdir(parents=True, exist_ok=True)
                    (out / f"{slug}.pdf").write_bytes(p.content)
            t = b.get("terrain")
            terr = ("teren: " + ", ".join(f"{z['label'].split(' –')[0]} {round(z['share_pct'])}%" for z in t["zones"]
                                          if z["share_pct"] >= 1)) if t and "zones" in t else "teren: brak"
            rows.append(row + [f"{b['status']['level']} ({b['status']['score']}); {terr}; {sat_txt}", f"{t_a:.2f} s", pdf])
            if t_a > 0.5:  # były zapytania do źródeł – spokojnie
                time.sleep(a.pause)
    if not a.no_satellite_series:
        asyncio.run(warm_satellite_series())
    print("\n| Przypadek | Uprawa | Data | Wynik | Analiza | PDF |\n|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(r) + " |")
    print("\n| Źródło | Wpisy w cache |\n|---|---|")
    for name in sorted(REGISTRY):
        if not name.startswith("cache-"):
            print(f"| {name} | {cache_stats(name)[0]} |")
    ready = [d for d in uldk.demo_parcels() if not d.get("needs_fetch")]
    print(f"\nDziałki demo gotowe (geometria w repo / cache): {len(ready)} z {len(uldk.demo_parcels())}")
    missing = [d.get("id") or d.get("query") for d in uldk.demo_parcels() if d.get("needs_fetch")]
    if missing:
        print("Do uzupełnienia (ULDK):", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
