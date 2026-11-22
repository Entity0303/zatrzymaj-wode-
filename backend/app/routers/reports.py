"""Raport PDF „Paszport wodny działki”.

GET /api/report.pdf?parcel_id=&crop=&date=&previous_crop= – DZIAŁA (A5): normalna analiza + PDF (app/report/).
POST /api/reports i GET /api/reports/{id}.pdf – zapis raportów w systemie (SZKIELET, HTTP 501).

Kontrakt: app/schemas/reports.py. Układ raportu: design/SPEC_UI.md 10.2. Generowanie: app/report/.
TODO (osoba A): WeasyPrint, A4 pionowo, 2–3 strony, kod QR do analizy online.
"""

import asyncio
import datetime as dt
from typing import Literal
from time import perf_counter

from fastapi import APIRouter, Query, Response

from app.core.config import settings
from app.core.http import not_implemented
from app.report.builder import build_pdf, filename
from app.routers.analysis import run_analysis
from app.schemas.analysis import AnalysisRequest
from app.schemas.reports import ReportMeta, ReportRequest

router = APIRouter(prefix="/api/reports", tags=["raporty"])


@router.post("", response_model=ReportMeta, responses={501: {"description": "W budowie"}})
async def create_report(req: ReportRequest) -> ReportMeta:
    raise not_implemented("Raport PDF")


@router.get("/{report_id}.pdf", responses={501: {"description": "W budowie"}})
async def get_report_pdf(report_id: str):
    raise not_implemented("Pobieranie raportu PDF")


# ── GET /api/report.pdf – raport PDF z normalnej analizy (A5/B5) ─────────────────────────────

pdf_router = APIRouter(prefix="/api", tags=["raporty"])


def _no_pending(a):
    """Teren / woda „w tle” w raporcie PDF = brak (raport najpierw liczy teren, więc to rzadkie)."""
    from app.schemas.analysis import TerrainPending

    upd = {}
    if isinstance(a.terrain, TerrainPending):
        upd["terrain"] = None
    if a.hydro is not None and a.hydro.status == "pending":
        upd["hydro"] = None
    return a.model_copy(update=upd) if upd else a


async def _satellite_first(parcel_id, lon, lat, geometry, date) -> None:
    """A11: raport to nie analiza na żywo – najpierw zdjęcie satelitarne (budżet ok. 15 s, potem cache), żeby PDF miał
    sekcję „Z satelity”, a analiza wzięła je z cache. Błąd satelity nie blokuje raportu."""
    from app.analysis import satellite as satellite_mod
    from app.routers.satellite import resolve_any

    from app.analysis import terrain as terrain_mod

    try:
        p = await resolve_any(parcel_id, lon, lat, geometry)
    except Exception:  # noqa: BLE001 – brak działki itp. zgłosi run_analysis z właściwym kodem HTTP
        return
    from app.analysis import hydro as hydro_mod

    # A9: teren i zdjęcie równolegle (raport może poczekać – analiza nie); błąd któregoś nie blokuje raportu.
    # P1: obiekty wodne (Overpass) i wodowskazy też od razu, równolegle – nie zależą od terenu (dawniej po nim:
    # 20–30 s terenu + do 55 s Overpass po kolei); niżej hydro_for składa wynik z cache (kierunek odpływu z terenu)
    *_rest, hydro_res = await asyncio.gather(
        asyncio.wait_for(terrain_mod.live(p.geom_2180, p.id), 30),
        satellite_mod.live(p.geom_4326, date or dt.date.today()),
        asyncio.wait_for(hydro_mod.fetch(p.geom_4326), settings.overpass_timeout_s + 10),
        return_exceptions=True)
    if isinstance(hydro_res, BaseException):  # P1: Overpass nie odpowiedział – bez drugiej próby po kolei
        return
    try:  # A9: woda w okolicy (po terenie – kierunek odpływu); dane Overpass już w cache – tylko złożenie wyniku
        from app.routers.hydro import hydro_for

        await asyncio.wait_for(hydro_for(p, date or dt.date.today()), settings.overpass_timeout_s + 15)
    except Exception:  # noqa: BLE001 – raport bez sekcji wody
        pass


@pdf_router.get("/report.pdf", response_class=Response,
                responses={200: {"content": {"application/pdf": {}}, "description": "Paszport wodny działki (PDF, A4)"},
                           404: {"description": "Nie znaleziono działki"}, 422: {"description": "Brak uprawy / zła data"},
                           502: {"description": "Brak działki lub pogody"}})
async def get_report_pdf_now(
    parcel_id: str | None = Query(None, description="Pełny identyfikator działki ULDK"),
    lon: float | None = Query(None, description="Punkt na mapie – zamiast parcel_id (obszar przybliżony, gdy brak działki)"),
    lat: float | None = Query(None, description="Punkt na mapie – zamiast parcel_id"),
    crop: str | None = Query(None, description="Uprawa (15 upraw IUNG SMSR)"),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś)"),
    previous_crop: str | None = Query(None, description="Uprawa w poprzednim roku albo 'nie_wiem'"),
    crop_history: str | None = Query(None, description="Historia pola: 1–3 uprawy po przecinku (pierwsza = rok temu)"),
    cultivated_area_ha: float | None = Query(None, description="Powierzchnia uprawy, ha"),
    planned_crops: str | None = Query(None, description="Co planujesz posiać: 1–3 uprawy z rankingu po przecinku"),
    period: Literal["30d", "since_sowing", "season"] | None = Query(None, description="A9b: podsumowanie okresu"),
    date_from: dt.date | None = Query(None, description="A9b: własny zakres – początek"),
    date_to: dt.date | None = Query(None, description="A9b: własny zakres – koniec (≤ data analizy)"),
    report_type: Literal["short", "full"] = Query("short", description="short – 4–5 stron (domyślnie) | full – z pełną tabelą upraw i szczegółami"),
) -> Response:
    """Liczy analizę (jak GET /api/analysis) i zwraca „Paszport wodny działki” w PDF (A4, do druku)."""
    t0 = perf_counter()
    await _satellite_first(parcel_id, lon, lat, None, date)
    a = _no_pending(await run_analysis(parcel_id, crop, date, previous_crop, crop_history, cultivated_area_ha, lon,
                                       lat, planned_crops=planned_crops, period=period, date_from=date_from,
                                       date_to=date_to))
    pdf = await build_pdf(a, report_type)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename(a, report_type)}"',
        "X-Generation-Ms": str(int((perf_counter() - t0) * 1000)),
    })


@pdf_router.post("/report.pdf", response_class=Response,
                 responses={200: {"content": {"application/pdf": {}}, "description": "Raport PDF (A4)"},
                            422: {"description": "Brak uprawy / zła data / zły obrys pola"},
                            502: {"description": "Brak działki lub pogody"}})
async def post_report_pdf_now(req: AnalysisRequest) -> Response:
    """Raport PDF dla własnego obrysu pola (`geometry`) albo działki – parametry w treści (jak POST /api/analysis)."""
    t0 = perf_counter()
    await _satellite_first(req.parcel_id, req.lon, req.lat, req.geometry, req.date)
    a = _no_pending(await run_analysis(req.parcel_id, req.crop, req.date, req.previous_crop, req.crop_history,
                                       req.cultivated_area_ha, req.lon, req.lat, req.geometry, req.planned_crops,
                                       req.period, req.date_from, req.date_to))
    rt = req.report_type or "short"
    pdf = await build_pdf(a, rt)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename(a, rt)}"',
        "X-Generation-Ms": str(int((perf_counter() - t0) * 1000)),
    })
