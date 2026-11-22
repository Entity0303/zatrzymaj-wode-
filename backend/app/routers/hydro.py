"""GET / POST /api/hydro – woda w okolicy działki (A9): cieki, rowy, kanały, zbiorniki w promieniu 500 m (OSM Overpass)
i najbliższy wodowskaz IMGW. /api/analysis bierze to tylko z cache (inaczej `hydro = {status: "pending"}` i pobranie
w tle); ten endpoint czeka na wynik (Overpass bywa wolny – do ok. 40 s). Kierunek odpływu – z terenu (cache NMT).
"""

from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, Query

from app.core import clock
from app.analysis import hydro as hydro_mod
from app.analysis import terrain as terrain_mod
from app.analysis import terrain_interpret
from app.core.config import settings
from app.core.http import SourceError, http_error
from app.routers.satellite import resolve_any
from app.schemas.analysis import AnalysisRequest, Hydro
from app.sources import uldk

router = APIRouter(prefix="/api", tags=["woda"])


async def outlets_for(p: uldk.Parcel) -> list:
    """Miejsca odpływu z terenu – z cache albo liczone (krótko); bez terenu kierunek odpływu = nieznany."""
    try:
        res = await asyncio.wait_for(terrain_mod.live(p.geom_2180, p.id), settings.nmt_total_timeout_s + 5)
    except (SourceError, asyncio.TimeoutError):
        return []
    return terrain_interpret.to_contract(res.facts, None).outlets


async def hydro_for(p: uldk.Parcel, on: dt.date) -> tuple[Hydro, list]:
    outs = await outlets_for(p)
    try:
        return await asyncio.wait_for(hydro_mod.live(p.geom_4326, outs, on), settings.overpass_timeout_s + 10)
    except SourceError as exc:
        raise http_error(exc) from exc
    except asyncio.TimeoutError as exc:
        raise http_error(SourceError("OpenStreetMap Overpass", "usługa odpowiada zbyt wolno – spróbuj za chwilę")) from exc


@router.get("/hydro", response_model=Hydro)
async def get_hydro(
    parcel_id: str | None = Query(None, description="Pełny identyfikator działki ULDK"),
    lon: float | None = Query(None), lat: float | None = Query(None),
    date: dt.date | None = Query(None, description="Data analizy (wodowskaz – tylko dla dziś)"),
) -> Hydro:
    """Cieki, rowy, kanały, zbiorniki ≤ 500 m (odległość, czy w kierunku odpływu) + najbliższy wodowskaz i zdanie."""
    p = await resolve_any(parcel_id, lon, lat)
    return (await hydro_for(p, date or clock.today_pl()))[0]


@router.post("/hydro", response_model=Hydro)
async def post_hydro(req: AnalysisRequest) -> Hydro:
    """Jak GET – dla pola narysowanego (`geometry`)."""
    p = await resolve_any(req.parcel_id, req.lon, req.lat, req.geometry)
    return (await hydro_for(p, req.date or clock.today_pl()))[0]
