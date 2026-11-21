"""Smoke bez ULDK na żywo (A5b-1): to samo co scripts/smoke.py, ale w procesie (TestClient), a obrys działki
201305_2.0038.6/1 z zapisanej wcześniej prawdziwej odpowiedzi ULDK (tests/test_analysis.py: ULDK_ONE).
Wszystkie inne źródła (pogoda, IUNG, mapa glebowo-rolnicza, SoilGrids, KIEG, prognoza, ortofotomapa) – na żywo.
Pozostałe działki pytają ULDK normalnie (przy ograniczeniu ruchu – błąd 502 w tabeli).

Uruchomienie (z katalogu repo):
  docker compose run --rm --no-deps -e DEMO_WARMUP=false -v "$(pwd)/backend/scripts:/app/scripts" \\
      -v "$(pwd)/backend/tests:/app/tests" -v "$(pwd)/reports:/reports" backend \\
      python scripts/smoke_cached_uldk.py --out /reports/examples --json /reports/smoke.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).parents[1]), str(Path(__file__).parent), str(Path(__file__).parents[1] / "tests")]

from fastapi.testclient import TestClient  # noqa: E402

import smoke  # noqa: E402
from app.main import app  # noqa: E402
from app.sources import uldk  # noqa: E402
from test_analysis import ULDK_ONE  # noqa: E402

RECORDED = {"201305_2.0038.6/1": ULDK_ONE}
_live_get = uldk._get


async def _get(params: dict) -> str:
    if params.get("request") == "GetParcelById" and params.get("id") in RECORDED:
        return RECORDED[params["id"]]
    return await _live_get(params)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    uldk._get = _get
    out = Path(a.out) if a.out else None
    rows = []
    with TestClient(app) as c:
        for e in c.get("/api/demo/examples").json():
            params = {k: e[k] for k in ("parcel_id", "crop", "date")}
            if e.get("previous_crop"):
                params["previous_crop"] = e["previous_crop"]
            rows.append(smoke.run_case(c, e["title"], params, out, e["id"]))
        name, pid, slug = smoke.NO_CROP
        rows.append(smoke.run_case(c, name, {"parcel_id": pid, "date": smoke.TODAY}, out, slug))
        rows.append(smoke.run_case(c, "Stan działki 10.06.2018 (bez uprawy)", {"parcel_id": pid, "date": "2018-06-10"},
                                   None, None))
        for pid, crop in smoke.PARCELS:
            rows.append(smoke.run_case(c, pid, {"parcel_id": pid, "crop": crop, "date": smoke.TODAY}, None, None))
    print(smoke.table(rows))
    print()
    print(smoke.table_a5b(rows))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
