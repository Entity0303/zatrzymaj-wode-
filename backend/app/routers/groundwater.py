"""GET / POST /api/groundwater (A27) – „Wody gruntowe i wsiąkanie”: wsiąkanie liczone z naszych danych (opad i
parowanie z 30 i 60 dni przed datą analizy, kategoria gleby IUNG, spadek terenu – wszystko z pamięci po analizie) oraz
obszary zagrożone podtopieniami PIG-PIB. Osobny endpoint – analiza na niego nie czeka; limit 8 s; awaria = HTTP 200
z `unavailable: true` albo z `source_pig.unavailable` (wtedy samo wsiąkanie)."""

import asyncio
import datetime as dt

from fastapi import APIRouter, HTTPException, Query

from app.analysis import groundwater as gw
from app.core.http import SourceError, http_error, log_source_error
from app.routers.satellite import resolve_any
from app.schemas.groundwater import GroundwaterContext, GroundwaterRequest
from app.sources import pig

router = APIRouter(prefix="/api", tags=["wody gruntowe"])
TOTAL_TIMEOUT_S = 8.0


async def context_for_parcel(p, analysis_date: dt.date) -> GroundwaterContext:
    """Wynik dla działki (`uldk.Parcel`) i daty. Pogoda, gleba i teren – te same funkcje co analiza (z pamięci);
    teren tylko gdy już policzony (nie uruchamiamy liczenia). Każda część może zawieść osobno."""
    from app.analysis import terrain as terrain_mod
    from app.routers.analysis import load_weather_history
    from app.sources import iung

    c = p.geom_4326.centroid

    async def work():
        return await asyncio.gather(
            load_weather_history(c.x, c.y, analysis_date), iung.soil_for_parcel(p.geom_2180),
            terrain_mod.cached_terrain(p.geom_2180, p.id), pig.flood_zone(c.x, c.y), return_exceptions=True)

    try:
        load, soil, terr, zone = await asyncio.wait_for(work(), TOTAL_TIMEOUT_S)
    except asyncio.TimeoutError:
        log_source_error("wody gruntowe", SourceError(pig.SOURCE, f"brak odpowiedzi w {TOTAL_TIMEOUT_S:.0f} s"), "A27")
        return GroundwaterContext(unavailable=True, note_pl=gw.UNAVAILABLE_NOTE, analysis_date=analysis_date)

    inf = None
    if not isinstance(load, BaseException):
        w = load.weather
        soil_code = None if isinstance(soil, BaseException) else gw.dominant_soil(soil.shares)
        facts = None if isinstance(terr, BaseException) or terr is None else terr.facts
        slope = facts.get("slope_mean_pct") if facts else None
        try:
            inf = gw.infiltration(w.dates, w.precip, w.et0, analysis_date, soil_code, slope)
        except Exception:  # noqa: BLE001 – brak wsiąkania nie może zabrać części PIG
            inf = None
    pig_failed = isinstance(zone, BaseException)
    if pig_failed and isinstance(zone, SourceError):
        log_source_error("wody gruntowe", zone, "PIG")
    hollow = None
    if not isinstance(terr, BaseException) and terr is not None:
        hollow = (terr.facts.get("zone_share_pct") or {}).get("mokry_dolek")
    return gw.combine(inf, None if pig_failed else zone, pig_failed, hollow, analysis_date, pig.DEPTH_NOTE,
                      pig.UNAVAILABLE_NOTE)


async def _context(parcel_id, lon, lat, geometry, date: dt.date | None) -> GroundwaterContext:
    today = dt.date.today()
    analysis_date = date or today
    if analysis_date > today:
        raise HTTPException(status_code=422, detail={"message": "Data analizy nie może być z przyszłości."})
    try:
        p = await resolve_any(parcel_id, lon, lat, geometry)
    except SourceError as exc:
        raise http_error(exc) from exc
    return await context_for_parcel(p, analysis_date)


@router.get("/groundwater", response_model=GroundwaterContext)
async def get_groundwater(
    parcel_id: str | None = Query(None, description="Pełny identyfikator działki ULDK"),
    lon: float | None = Query(None), lat: float | None = Query(None),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś) – opad i parowanie z 30 i 60 dni przed nią"),
) -> GroundwaterContext:
    return await _context(parcel_id, lon, lat, None, date)


@router.post("/groundwater", response_model=GroundwaterContext)
async def post_groundwater(req: GroundwaterRequest) -> GroundwaterContext:
    """Jak GET – dla pola narysowanego (`geometry`) albo działki / punktu w treści."""
    return await _context(req.parcel_id, req.lon, req.lat, req.geometry, req.date)
