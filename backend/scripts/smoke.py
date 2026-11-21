"""Test dymny na żywo: /api/analysis i /api/report.pdf dla 4 przykładów demo i 6 działek z .ai/test-parcels.md.

Uruchomienie (backend musi działać – `docker compose up`):
  docker compose run --rm -v "$(pwd)/backend/scripts:/app/scripts" -v "$(pwd)/reports:/reports" \\
      backend python scripts/smoke.py --base http://backend:8000 --out /reports/examples
Wypisuje tabelę (OK/błąd, czasy, status, pewność, liczba rekomendacji, w tym retencyjnych) i zapisuje PDF-y
przykładów (wymagane w zgłoszeniu KOWR: „wygenerowany przez prototyp raport”).
"""

import argparse
import datetime as dt
import io
import json
import sys
import time
from pathlib import Path

import httpx

TODAY = dt.date.today().isoformat()
# działki z .ai/test-parcels.md (uprawa dobrana do działki, data = dziś)
PARCELS = [
    ("201305_2.0038.6/1", "zboza_ozime"),
    ("061704_2.0011.383/2", "kukurydza_ziarno"),
    ("040703_5.0020.76", "zboza_ozime"),
    ("302114_5.0018.445", "zboza_ozime"),
    ("160703_5.0011.945", "zboza_ozime"),
    ("143203_2.0027.112/11", "zboza_ozime"),
]


def pdf_pages(content: bytes) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(content)).pages)
    except Exception:  # noqa: BLE001
        return None


def run_case(c: httpx.Client, name: str, params: dict, out: Path | None, slug: str | None) -> dict:
    row = {"name": name, **params}
    t0 = time.perf_counter()
    try:
        r = c.get("/api/analysis", params=params)
        row["analysis_s"] = round(time.perf_counter() - t0, 2)
        row["http"] = r.status_code
        if r.status_code == 200:
            b = r.json()
            row.update(
                ok=True, level=b["status"]["level"], score=b["status"]["score"], headline=b["status"]["headline"],
                confidence=b["reliability"]["confidence"], recs=len(b["recommendations"]),
                ret=sum(x["category"] == "retencja" for x in b["recommendations"]),
                panel=sum(x["in_panel"] for x in b["recommendations"]),
                total_ms=next((s["duration_ms"] for s in b["steps"] if s["id"] == "total"), None),
                body=b,
            )
        else:
            row.update(ok=False, error=r.text[:200])
    except httpx.HTTPError as exc:
        row.update(ok=False, http=None, analysis_s=round(time.perf_counter() - t0, 2), error=str(exc))
    t1 = time.perf_counter()
    try:
        p = c.get("/api/report.pdf", params=params)
        row["pdf_s"] = round(time.perf_counter() - t1, 2)
        row["pdf_ok"] = p.status_code == 200 and p.content.startswith(b"%PDF")
        row["pdf_pages"] = pdf_pages(p.content) if row["pdf_ok"] else None
        if row["pdf_ok"] and out and slug:
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{slug}.pdf").write_bytes(p.content)
            row["pdf_file"] = f"{slug}.pdf"
    except httpx.HTTPError as exc:
        row.update(pdf_ok=False, pdf_s=round(time.perf_counter() - t1, 2), pdf_error=str(exc))
    return row


def table(rows: list[dict]) -> str:
    head = ("| Przypadek | Data | Analiza | Czas | Status (pkt) | Pewność | Rek. (retencja / panel) | PDF | Czas PDF |\n"
            "|---|---|---|---|---|---|---|---|---|")
    lines = [head]
    for r in rows:
        status = f"{r['level']} ({r['score'] if r['score'] is not None else '–'})" if r.get("ok") else "–"
        recs = f"{r['recs']} ({r['ret']} / {r['panel']})" if r.get("ok") else "–"
        pdf = f"OK, {r.get('pdf_pages')} str." if r.get("pdf_ok") else "błąd"
        lines.append(
            f"| {r['name']} | {r.get('date', TODAY)} | {'OK' if r.get('ok') else 'błąd ' + str(r.get('http'))} | "
            f"{r['analysis_s']} s | {status} | {r.get('confidence', '–')} | {recs} | {pdf} | {r.get('pdf_s', '–')} s |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--out", default=None, help="katalog na PDF-y przykładów")
    ap.add_argument("--json", default=None, help="zapis pełnych wyników (JSON)")
    a = ap.parse_args()
    out = Path(a.out) if a.out else None
    rows = []
    with httpx.Client(base_url=a.base, timeout=60) as c:
        examples = c.get("/api/demo/examples").json()
        for e in examples:
            params = {k: e[k] for k in ("parcel_id", "crop", "date")}
            if e.get("previous_crop"):
                params["previous_crop"] = e["previous_crop"]
            rows.append(run_case(c, e["title"], params, out, e["id"]))
        for pid, crop in PARCELS:
            rows.append(run_case(c, pid, {"parcel_id": pid, "crop": crop, "date": TODAY}, None, None))
    print(table(rows))
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0 if all(r.get("ok") and r.get("pdf_ok") for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
