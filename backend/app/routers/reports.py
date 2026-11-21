"""POST /api/reports – raport PDF „Paszport wodny działki” (SZKIELET, HTTP 501).

Kontrakt: app/schemas/reports.py. Układ raportu: design/SPEC_UI.md 10.2. Generowanie: app/report/.
TODO (osoba A): WeasyPrint, A4 pionowo, 2–3 strony, kod QR do analizy online.
"""

from fastapi import APIRouter

from app.core.http import not_implemented
from app.schemas.reports import ReportMeta, ReportRequest

router = APIRouter(prefix="/api/reports", tags=["raporty"])


@router.post("", response_model=ReportMeta, responses={501: {"description": "W budowie"}})
async def create_report(req: ReportRequest) -> ReportMeta:
    raise not_implemented("Raport PDF")


@router.get("/{report_id}.pdf", responses={501: {"description": "W budowie"}})
async def get_report_pdf(report_id: str):
    raise not_implemented("Pobieranie raportu PDF")
