"""GET / POST /api/satellite – Sentinel-2 dla działki na żywo (A11, D86): ostatnia czysta scena + rok wcześniej.

Liczone osobno od /api/analysis (analiza < 30 s – bierze satelitę tylko z cache, inaczej `status: pending`).
Budżet: ok. 15 s i 10 MB na działkę (`settings.sentinel_budget_*`); wynik trafia do trwałego cache (12 h dla „dziś”,
bez wygasania dla dat historycznych). Brak sceny / awaria źródła = `status: brak_danych` (HTTP 200), nie błąd.
Działka jak w analizie: `parcel_id`, punkt `lon` + `lat` (obszar przybliżony, gdy brak ULDK) albo POST z `geometry`.
"""

from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, HTTPException, Query

from app.analysis import drawn_field
from app.analysis import satellite as satellite_mod
from app.core.config import settings
from app.core.http import SourceError, http_error
from app.routers.analysis import _resolve_point
from app.routers.parcel import resolve_parcel
from app.schemas.analysis import AnalysisRequest, Satellite
from app.sources import uldk

router = APIRouter(prefix="/api", tags=["satelita"])


async def resolve_any(parcel_id: str | None, lon: float | None, lat: float | None,
                      geometry: dict | None = None) -> uldk.Parcel:
    """Ta sama działka co w analizie (ten sam kształt = ten sam klucz cache satelity)."""
    if geometry is not None:
        try:
            return await drawn_field.resolve(geometry)
        except drawn_field.DrawnError as exc:
            raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    if parcel_id:
        try:
            return await asyncio.wait_for(resolve_parcel(parcel_id, None, None), timeout=settings.uldk_timeout_s * 2 + 1)
        except SourceError as exc:
            raise http_error(exc) from exc
        except asyncio.TimeoutError as exc:
            raise http_error(SourceError("ULDK GUGiK", "usługa nie odpowiada")) from exc
    if lon is not None and lat is not None:
        p, _approx = await _resolve_point(lon, lat)
        return p
    raise HTTPException(status_code=422, detail={"message": "Podaj numer działki, punkt (lon, lat) albo obrys pola."})


def _date(d: dt.date | None) -> dt.date:
    today = dt.date.today()
    d = d or today
    if d > today:
        raise HTTPException(status_code=422, detail={"message": "Data analizy nie może być z przyszłości."})
    return d


@router.get("/satellite", response_model=Satellite)
async def get_satellite(
    parcel_id: str | None = Query(None, description="Pełny identyfikator działki ULDK"),
    lon: float | None = Query(None, description="Punkt na mapie (WGS84) – zamiast parcel_id"),
    lat: float | None = Query(None),
    date: dt.date | None = Query(None, description="Data analizy – sceny tylko sprzed tej daty (domyślnie dziś)"),
) -> Satellite:
    """Kondycja (NDVI) i wilgotność roślin (NDMI) z ostatniej czystej sceny Sentinel-2 (≤ 60 dni przed datą) +
    ta sama pora rok wcześniej, zdanie dla rolnika z datą zdjęcia. Szereg 12 mies. – tylko z cache."""
    p = await resolve_any(parcel_id, lon, lat)
    return await satellite_mod.live(p.geom_4326, _date(date))


@router.post("/satellite", response_model=Satellite)
async def post_satellite(req: AnalysisRequest) -> Satellite:
    """Jak GET, dla własnego obrysu pola (`geometry`) albo działki / punktu w treści."""
    p = await resolve_any(req.parcel_id, req.lon, req.lat, req.geometry)
    return await satellite_mod.live(p.geom_4326, _date(req.date))
