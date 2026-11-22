"""GET / POST /api/drought-context (A26) – tło suszowe z Europejskiego Obserwatorium Suszy (EDO, Copernicus) dla okolicy
działki: łączny wskaźnik suszy, anomalia wilgotności gleby, ryzyko dla rolnictwa. Osobny endpoint – analiza na niego
nie czeka; awaria usługi = `unavailable: true` z notą (HTTP 200)."""

import datetime as dt

from fastapi import APIRouter, HTTPException, Query

from app.analysis import drought_context
from app.core.http import SourceError, http_error
from app.routers.satellite import resolve_any
from app.schemas.drought import DroughtContext, DroughtContextRequest

router = APIRouter(prefix="/api", tags=["tło suszowe"])


async def _context(parcel_id, lon, lat, geometry, date: dt.date | None, our_status: str | None) -> DroughtContext:
    today = dt.date.today()
    analysis_date = date or today
    if analysis_date > today:
        raise HTTPException(status_code=422, detail={"message": "Data analizy nie może być z przyszłości."})
    try:
        p = await resolve_any(parcel_id, lon, lat, geometry)
    except SourceError as exc:
        raise http_error(exc) from exc
    c = p.geom_4326.centroid
    return await drought_context.context(c.x, c.y, analysis_date, our_status, today)


@router.get("/drought-context", response_model=DroughtContext, response_model_by_alias=True)
async def get_drought_context(
    parcel_id: str | None = Query(None, description="Pełny identyfikator działki ULDK"),
    lon: float | None = Query(None), lat: float | None = Query(None),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś) – ostatnia zakończona dekada przed nią"),
    our_status: str | None = Query(None, description="Nasz stopień (ok | warn | risk | danger albo nagłówek) – do porównania"),
) -> DroughtContext:
    return await _context(parcel_id, lon, lat, None, date, our_status)


@router.post("/drought-context", response_model=DroughtContext, response_model_by_alias=True)
async def post_drought_context(req: DroughtContextRequest) -> DroughtContext:
    """Jak GET – dla pola narysowanego (`geometry`) albo działki / punktu w treści."""
    return await _context(req.parcel_id, req.lon, req.lat, req.geometry, req.date, req.our_status)
