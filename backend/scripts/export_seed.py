"""Seed cache do obrazu (A13): z trwałego cache (`CACHE_DB`, w Dockerze /data/cache.sqlite) do
app/data/seed/cache_seed.sqlite.gz – backend wczytuje go przy starcie, gdy cache jest pusty (Render Free bez dysku).

    docker compose exec backend python scripts/export_seed.py            # wszystko poza prognozą / stanami wód
    docker compose exec backend python scripts/export_seed.py --max-mb 20 --no-series

Bez: prognozy Open-Meteo i bieżących stanów wód IMGW (wygasają w godzinę). `--no-series` – bez szeregów Sentinel-2
z 12 miesięcy (największe wpisy satelity). Tylko dane publiczne (działki, gleba, pogoda, teren, satelita, woda,
ortofotomapa) – bez danych osobowych; zgłoszenia rolników (infra.sqlite) NIE trafiają do seeda.
"""

import argparse
import gzip
import pickle
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.cache import SEED_EXCLUDE, SEED_FILE  # noqa: E402
from app.core.config import settings  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=settings.cache_db or "/data/cache.sqlite")
    ap.add_argument("--out", default=str(SEED_FILE))
    ap.add_argument("--max-mb", type=float, default=20.0, help="limit rozmiaru pliku .gz")
    ap.add_argument("--no-series", action="store_true", help="bez szeregów Sentinel-2 (12 miesięcy)")
    a = ap.parse_args()
    src = sqlite3.connect(a.src)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "seed.sqlite"
        dst = sqlite3.connect(db)
        dst.execute("CREATE TABLE cache (ns TEXT NOT NULL, k TEXT NOT NULL, stored_at REAL NOT NULL, ttl_s REAL, "
                    "value BLOB NOT NULL, PRIMARY KEY (ns, k))")
        by_ns: dict[str, list[int]] = {}
        for ns, k, stored_at, ttl_s, value in src.execute("SELECT ns, k, stored_at, ttl_s, value FROM cache"):
            if ns in SEED_EXCLUDE:
                continue
            if a.no_series and ns.startswith("Sentinel-2") and ("'series'" in k or '"series"' in k):
                continue
            try:
                pickle.loads(value)  # tylko poprawne wpisy
            except Exception:  # noqa: BLE001
                continue
            dst.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?)", (ns, k, stored_at, ttl_s, value))
            by_ns.setdefault(ns, []).append(len(value))
        dst.commit()
        dst.execute("VACUUM")
        dst.close()
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(db, "rb") as f, gzip.open(out, "wb", compresslevel=9) as g:
            shutil.copyfileobj(f, g)
    mb = out.stat().st_size / 1e6
    for ns, sizes in sorted(by_ns.items(), key=lambda x: -sum(x[1])):
        print(f"  {ns:42s} {len(sizes):5d} wpisów  {sum(sizes) / 1e6:6.2f} MB")
    print(f"seed: {out} – {sum(len(v) for v in by_ns.values())} wpisów, {mb:.1f} MB (gzip)")
    if mb > a.max_mb:
        print(f"UWAGA: seed > {a.max_mb} MB – uruchom z --no-series albo ogranicz przestrzenie")
        sys.exit(1)


if __name__ == "__main__":
    main()
