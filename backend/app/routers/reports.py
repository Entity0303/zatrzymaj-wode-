"""Raport PDF „Paszport wodny działki”.

GET /api/report.pdf?parcel_id=&crop=&date=&previous_crop= – DZIAŁA (A5): normalna analiza + PDF (app/report/).
POST /api/reports i GET /api/reports/{id}.pdf – zapis raportów w systemie (SZKIELET, HTTP 501).

Kontrakt: app/schemas/reports.py. Układ raportu: design/SPEC_UI.md 10.2. Generowanie: app/report/.
TODO (osoba A): WeasyPrint, A4 pionowo, 2–3 strony, kod QR do analizy online.
"""

import datetime as dt
from time import perf_counter

from fastapi import APIRouter, Query, Response

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
) -> Response:
    """Liczy analizę (jak GET /api/analysis) i zwraca „Paszport wodny działki” w PDF (A4, do druku)."""
    t0 = perf_counter()
    a = await run_analysis(parcel_id, crop, date, previous_crop, crop_history, cultivated_area_ha, lon, lat)
    pdf = await build_pdf(a)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename(a)}"',
        "X-Generation-Ms": str(int((perf_counter() - t0) * 1000)),
    })


@pdf_router.post("/report.pdf", response_class=Response,
                 responses={200: {"content": {"application/pdf": {}}, "description": "Raport PDF (A4)"},
                            422: {"description": "Brak uprawy / zła data / zły obrys pola"},
                            502: {"description": "Brak działki lub pogody"}})
async def post_report_pdf_now(req: AnalysisRequest) -> Response:
    """Raport PDF dla własnego obrysu pola (`geometry`) albo działki – parametry w treści (jak POST /api/analysis)."""
    t0 = perf_counter()
    a = await run_analysis(req.parcel_id, req.crop, req.date, req.previous_crop, req.crop_history,
                           req.cultivated_area_ha, req.lon, req.lat, req.geometry)
    pdf = await build_pdf(a)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename(a)}"',
        "X-Generation-Ms": str(int((perf_counter() - t0) * 1000)),
    })
