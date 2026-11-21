"""Buduje magazyn opadów dobowych IMGW dla WSZYSTKICH stacji ze współrzędnymi (A7, D82):

    docker compose run --rm -e DEMO_OFFLINE=false backend python scripts/build_imgw.py [--from 2016] [--to 2026]

Pobiera archiwum dobowe IMGW (OPAD i KLIMAT – pliki miesięczne całej Polski, SYNOP – plik roczny na stację) przez
`core/http.request` (bez przekierowań, z limitem rozmiaru), z przerwą między zapytaniami; surowe ZIP-y zostają w
katalogu roboczym (domyślnie /data/imgw_raw – wolumen cache), więc kolejne uruchomienie dociąga tylko brakujące
pliki (miesiące bieżącego roku pobiera zawsze od nowa). Wynik: app/data/imgw/opady.npz (int16, 0,1 mm, −1 = brak)
+ app/data/imgw/index.json (stacje, pokrycie). To NIE jest GUGiK – danepubliczne.imgw.pl.
"""

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.http import SourceError, request  # noqa: E402
from app.sources import imgw  # noqa: E402

PAUSE_S = 0.15


async def get(url: str) -> bytes | None:
    """Jedno zapytanie; 404 = pliku nie ma (None). Błąd sieci – 2 ponowienia."""
    last = None
    for attempt in range(3):
        try:
            r = await request("GET", url, source=imgw.SOURCE, timeout_s=30, max_bytes=20_000_000)
        except SourceError as exc:
            raise SystemExit(f"IMGW: {exc.message} ({url})") from exc
        except Exception as exc:  # noqa: BLE001 – timeout / brak połączenia
            last = exc
            await asyncio.sleep(2 + 2 * attempt)
            continue
        if r.status_code == 404:
            return None
        if r.status_code == 200:
            return r.content
        last = f"HTTP {r.status_code}"
        await asyncio.sleep(2 + 2 * attempt)
    raise SystemExit(f"IMGW: nie udało się pobrać {url} ({last})")


async def fetch(raw: Path, url: str, refresh: bool, stats: dict) -> bytes | None:
    kind_dir = raw / url.split("/dobowe/")[1].split("/")[0]
    p = kind_dir / url.rsplit("/", 1)[-1]
    miss = p.with_suffix(".404")
    if p.exists() and not refresh:
        stats["cache"] += 1
        return p.read_bytes()
    if miss.exists() and not refresh:
        return None
    body = await get(url)
    stats["pobrane"] += 1
    await asyncio.sleep(PAUSE_S)
    p.parent.mkdir(parents=True, exist_ok=True)
    if body is None:
        miss.write_text("")
        return None
    p.write_bytes(body)
    return body


async def synop_ids(raw: Path, year: int, refresh: bool) -> list[str]:
    cache = raw / "synop" / f"listing_{year}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text())
    body = await get(f"{imgw.ARCHIVE_URL}synop/{year}/")
    await asyncio.sleep(PAUSE_S)
    ids = sorted(set(re.findall(rf'href="{year}_(\d+)_s\.zip"', (body or b"").decode("utf-8", "replace"))))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(ids))
    return ids


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y0", type=int, default=2016)
    ap.add_argument("--to", dest="y1", type=int, default=date.today().year)
    ap.add_argument("--raw", default="/data/imgw_raw")
    ap.add_argument("--out", default=str(imgw.STORE_FILE))
    a = ap.parse_args()
    raw = Path(a.raw)
    t0 = time.time()
    catalog = imgw.station_catalog()
    start, end = date(a.y0, 1, 1), min(date(a.y1, 12, 31), date.today())
    n_days = (end - start).days + 1
    this_year = date.today().year
    stats = {"pobrane": 0, "cache": 0}

    builder = imgw.StoreBuilder(start, end, catalog)
    add, st = builder.add, builder.st

    for kind in ("synop", "klimat", "opad"):  # kolejność = priorytet rodzaju stacji
        for y in range(a.y0, a.y1 + 1):
            refresh = y == this_year
            if kind == "synop":
                urls = [imgw.archive_url(kind, y, synop_id=i) for i in await synop_ids(raw, y, refresh)]
            else:
                urls = [imgw.archive_url(kind, y, m) for m in range(1, 13) if date(y, m, 1) <= end]
            for url in urls:
                body = await fetch(raw, url, refresh, stats)
                if body:
                    add(kind, imgw.zip_rows(body, kind))
            print(f"{kind} {y}: stacji {len(st)}, pobrane {stats['pobrane']}, z dysku {stats['cache']}", flush=True)

    codes, data, index = builder.finish()
    last_day = data.shape[0] - 1
    built = date.today().isoformat()
    out = Path(a.out)
    imgw.save_store(out, codes, [st[c]["name"] for c in codes], [st[c]["kind"] for c in codes],
                    [catalog[c]["lon"] for c in codes], [catalog[c]["lat"] for c in codes], start, data, built)
    (out.parent / "index.json").write_text(json.dumps({
        "_opis": "Indeks magazynu opadów IMGW (scripts/build_imgw.py): stacje ze współrzędnymi i danymi dobowymi.",
        "_built": built, "_start": start.isoformat(), "_end": (start + timedelta(days=last_day)).isoformat(),
        "_stations": len(codes), "index": index}, ensure_ascii=False, indent=0), encoding="utf-8")
    kinds = {k: sum(1 for c in codes if st[c]["kind"] == k) for k in imgw.KINDS}
    print(f"GOTOWE: {len(codes)} stacji {kinds}, dni {last_day + 1} ({start} – {start + timedelta(days=last_day)}), "
          f"plik {out.stat().st_size / 1e6:.2f} MB, pobrane {stats['pobrane']}, z dysku {stats['cache']}, "
          f"czas {time.time() - t0:.0f} s")


asyncio.run(main())
