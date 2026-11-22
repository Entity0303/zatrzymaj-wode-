"""Zgłoszenia rolników o stanie rowów, cieków i zbiorników (A9, SPEC 11) – zapis w SQLite, bez danych osobowych.

Kontrakt: app/schemas/reports.py (InfraReportIn, InfraReport). Zapisujemy tylko: rodzaj obiektu, punkt, problem, stan
wody, krótki opis (maks. 500 znaków), datę i liczbę potwierdzeń – bez imienia, telefonu, adresu, IP. Nic nie jest
wysyłane automatycznie: adresat wynika z rodzaju obiektu (ciek → Wody Polskie, rów → właściciel gruntu / spółka wodna,
zbiornik → właściciel / zarządca), pismo do pobrania – GET /api/infra-reports/{id}/letter (tekst do wydruku).
Baza: plik obok cache (`CACHE_DB` → infra.sqlite w tym samym katalogu); bez CACHE_DB – tylko pamięć procesu.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.core.http import in_poland
from app.schemas.reports import InfraReport, InfraReportIn

router = APIRouter(prefix="/api/infra-reports", tags=["zgłoszenia"])

ADDRESSEE = {"row": "Właściciel gruntu lub spółka wodna", "ciek": "Wody Polskie – Nadzór Wodny",
             "zbiornik": "Właściciel lub zarządca zbiornika"}
OBJECT_LABEL = {"row": "rów melioracyjny", "ciek": "rzeka lub strumień", "zbiornik": "staw lub zbiornik"}
PROBLEM_LABEL = {"drozny": "drożny, w porządku", "zarosniety": "zarośnięty", "zamulony": "zamulony",
                 "zatkany_przepust": "zatkany przepust", "uszkodzona_zastawka": "uszkodzona zastawka",
                 "uszkodzona_skarpa": "uszkodzona skarpa", "zanieczyszczony": "zanieczyszczony"}
MAX_LIST = 500
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_conn_path: str | None = None


def _db_path() -> str:
    if settings.cache_db:
        return str(Path(settings.cache_db).with_name("infra.sqlite"))
    return ":memory:"


def db() -> sqlite3.Connection:
    global _conn, _conn_path
    path = _db_path()
    if _conn is None or _conn_path != path:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn_path = path
        _conn.execute("""CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY, object_type TEXT NOT NULL, object_id TEXT, lon REAL NOT NULL, lat REAL NOT NULL,
            problem TEXT NOT NULL, water_level TEXT, description TEXT, created_at TEXT NOT NULL,
            confirmations INTEGER NOT NULL DEFAULT 0)""")
        _conn.execute("CREATE INDEX IF NOT EXISTS reports_xy ON reports (lon, lat)")
        _conn.commit()
    return _conn


def reset() -> None:
    """Testy: nowa baza (np. po zmianie CACHE_DB)."""
    global _conn, _conn_path
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn, _conn_path = None, None


def _row(r: tuple) -> InfraReport:
    rid, otype, oid, lon, lat, problem, level, desc, created, conf = r
    return InfraReport(id=rid, object_type=otype, object_id=oid, lon=lon, lat=lat, problem=problem, water_level=level,
                       description=desc, created_at=dt.datetime.fromisoformat(created), confirmations=conf,
                       addressee=ADDRESSEE[otype])


def _get(report_id: str) -> InfraReport:
    with _lock:
        r = db().execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail={"message": "Nie ma takiego zgłoszenia."})
    return _row(r)


@router.get("", response_model=list[InfraReport])
async def list_infra_reports(lon_min: float = Query(), lat_min: float = Query(), lon_max: float = Query(),
                             lat_max: float = Query()) -> list[InfraReport]:
    """Zgłoszenia w prostokącie (EPSG:4326), najnowsze najpierw, maks. 500."""
    if lon_min > lon_max or lat_min > lat_max:
        raise HTTPException(status_code=422, detail={"message": "Zły prostokąt (min > max)."})
    with _lock:
        rows = db().execute("SELECT * FROM reports WHERE lon BETWEEN ? AND ? AND lat BETWEEN ? AND ? "
                            "ORDER BY created_at DESC LIMIT ?", (lon_min, lon_max, lat_min, lat_max, MAX_LIST)).fetchall()
    return [_row(r) for r in rows]


@router.post("", response_model=InfraReport, status_code=201)
async def create_infra_report(report: InfraReportIn) -> InfraReport:
    """Nowe zgłoszenie (bez danych osobowych). Punkt musi leżeć w Polsce."""
    if not in_poland(report.lon, report.lat):
        raise HTTPException(status_code=422, detail={"message": "Punkt leży poza Polską."})
    rid = uuid.uuid4().hex[:12]
    created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    desc = (report.description or "").strip()[:500] or None
    with _lock:
        c = db()
        c.execute("INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?,0)",
                  (rid, report.object_type, report.object_id, round(report.lon, 6), round(report.lat, 6), report.problem,
                   report.water_level, desc, created.isoformat()))
        c.commit()
    return _get(rid)


@router.post("/{report_id}/confirm", response_model=InfraReport)
async def confirm_infra_report(report_id: str) -> InfraReport:
    """„Potwierdzam” – kolejny rolnik widzi ten sam problem."""
    with _lock:
        c = db()
        n = c.execute("UPDATE reports SET confirmations = confirmations + 1 WHERE id = ?", (report_id,)).rowcount
        c.commit()
    if not n:
        raise HTTPException(status_code=404, detail={"message": "Nie ma takiego zgłoszenia."})
    return _get(report_id)


@router.get("/{report_id}/letter", response_class=PlainTextResponse)
async def get_infra_letter(report_id: str) -> str:
    """Pismo do pobrania / wydruku (tekst). Nic nie jest wysyłane automatycznie – rolnik dopisuje swoje dane sam."""
    r = _get(report_id)
    lvl = f"\nStan wody: {r.water_level}." if r.water_level else ""
    desc = f"\nOpis: {r.description}" if r.description else ""
    return (f"Do: {r.addressee}\n\nZgłoszenie stanu obiektu wodnego\n\n"
            f"Obiekt: {OBJECT_LABEL[r.object_type]}\nMiejsce: {r.lat:.5f} N, {r.lon:.5f} E (WGS84)\n"
            f"Problem: {PROBLEM_LABEL[r.problem]}.{lvl}{desc}\n"
            f"Data zgłoszenia: {r.created_at:%d.%m.%Y}. Potwierdzenia innych rolników: {r.confirmations}.\n\n"
            "Proszę o sprawdzenie i przywrócenie drożności / sprawności obiektu.\n\n"
            "Imię i nazwisko, adres do korespondencji: ............................................\n"
            "Podpis: ....................\n\n"
            "Pismo przygotowane w aplikacji Wodoskop – nic nie zostało wysłane automatycznie.\n")
