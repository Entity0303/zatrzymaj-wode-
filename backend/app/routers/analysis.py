"""GET /api/analysis?parcel_id=&crop=&date= – analiza wodna działki (SZKIELET, HTTP 501).

Kontrakt odpowiedzi: app/schemas/analysis.py (AnalysisResponse).

TODO (osoba A), kolejność z CLAUDE.md (P0):
1. działka: routers.parcel.resolve_parcel
2. równolegle (asyncio.gather, timeout, cache): pogoda 10 lat (sources.weather_power),
   prognoza (sources.weather_openmeteo), gleba (sources.iung) – tylko dane sprzed `date`
3. ET0 / bilans (analysis.et0, analysis.water_balance), model wody w glebie FAO-56
4. ocena, pewność, przyczyny (analysis.scoring), rekomendacje z reguł YAML (analysis.recommendations)
5. awaria jednego źródła obniża pewność (reliability), nie wywraca analizy
"""

import datetime as dt

from fastapi import APIRouter, Query

from app.core.http import not_implemented
from app.schemas.analysis import AnalysisResponse, CropId
from app.schemas.parcel import ErrorDetail

router = APIRouter(prefix="/api", tags=["analiza"])


@router.get(
    "/analysis",
    response_model=AnalysisResponse,
    responses={404: {"model": ErrorDetail}, 501: {"description": "W budowie"}, 502: {"model": ErrorDetail}},
)
async def get_analysis(
    parcel_id: str = Query(description="Pełny identyfikator działki ULDK"),
    crop: CropId = Query(description="Uprawa (15 upraw IUNG SMSR)"),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś, maks. 10 lat wstecz)"),
) -> AnalysisResponse:
    raise not_implemented("Analiza wodna działki")
