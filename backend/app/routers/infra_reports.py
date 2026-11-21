"""Zgłoszenia rolników o stanie rowów i zbiorników (SZKIELET, HTTP 501).

Kontrakt: app/schemas/reports.py (InfraReportIn, InfraReport). design/SPEC_UI.md 11.
Bez danych osobowych; nic nie jest wysyłane automatycznie – generujemy pismo do pobrania.

TODO (osoba A): zapis w SQLite, lista zgłoszeń w bbox, potwierdzenia, pismo (ciek → Wody Polskie,
rów → właściciel gruntu / spółka wodna).
"""

from fastapi import APIRouter

from app.core.http import not_implemented
from app.schemas.reports import InfraReport, InfraReportIn

router = APIRouter(prefix="/api/infra-reports", tags=["zgłoszenia"])


@router.get("", response_model=list[InfraReport], responses={501: {"description": "W budowie"}})
async def list_infra_reports(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> list[InfraReport]:
    raise not_implemented("Lista zgłoszeń")


@router.post("", response_model=InfraReport, responses={501: {"description": "W budowie"}})
async def create_infra_report(report: InfraReportIn) -> InfraReport:
    raise not_implemented("Zgłoszenie stanu rowu / zbiornika")


@router.post("/{report_id}/confirm", response_model=InfraReport, responses={501: {"description": "W budowie"}})
async def confirm_infra_report(report_id: str) -> InfraReport:
    raise not_implemented("Potwierdzenie zgłoszenia")


@router.get("/{report_id}/letter", responses={501: {"description": "W budowie"}})
async def get_infra_letter(report_id: str):
    raise not_implemented("Pismo do pobrania")
