"""GET / POST /api/terrain – teren i spływ wody z NMT liczone osobno od analizy (A9, jak satelita).

/api/analysis nie czeka na NMT: gdy siatki wysokości działki nie ma w cache, zwraca `terrain = {status: "pending"}`
i uruchamia liczenie w tle; frontend dociąga ten endpoint (dla pola narysowanego – POST z `geometry`). Wynik trafia do
cache (siatka NMT bez wygasania), potem /api/layers/teren i /splyw oraz analiza biorą go od razu.
Gleba do oceny stref (górka na piasku / dołek na glinie) – IUNG + mapa glebowo-rolnicza z cache (jak w analizie).
"""

from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, Query

from app.core import clock
from app.analysis import soil_consistency, soil_label, terrain_interpret
from app.analysis import terrain as terrain_mod
from app.analysis.soil import assess_soil
from app.core.config import settings
from app.core.http import SourceError, http_error
from app.routers.satellite import resolve_any
from app.schemas.analysis import AnalysisRequest, Terrain
from app.sources import iung, soil_map, uldk

router = APIRouter(prefix="/api", tags=["teren"])


async def soil_for_terrain(p: uldk.Parcel) -> tuple[str | None, str | None]:
    """Grupa gleby i jej opis dla oceny stref terenu (z cache IUNG / mapy glebowo-rolniczej; błąd → „nieznana”)."""
    iung_res, sm_res = await asyncio.gather(iung.soil_for_parcel(p.geom_2180), soil_map.soil_map_for_parcel(p.geom_2180),
                                            return_exceptions=True)
    if isinstance(iung_res, BaseException) and not isinstance(iung_res, SourceError):
        iung_res = SourceError(iung.SOURCE, "błąd")
    try:
        soil_a = assess_soil(iung_res, None)
        map_sum = None if isinstance(sm_res, BaseException) else soil_consistency.summarize_map(sm_res)
        prof = soil_label.profile(soil_a, map_sum, None)
        return prof.group, prof.text
    except Exception:  # noqa: BLE001 – teren pokazujemy także bez gleby
        return None, None


async def terrain_contract(p: uldk.Parcel, analysis_date: dt.date | None = None) -> Terrain:
    """A20: `source_tag.date` nigdy po dacie analizy (dla daty historycznej – data analizy)."""
    try:
        res, (group, text) = await asyncio.gather(
            asyncio.wait_for(terrain_mod.live(p.geom_2180, p.id), settings.nmt_total_timeout_s + 5),
            soil_for_terrain(p))
    except SourceError as exc:
        raise http_error(exc) from exc
    except asyncio.TimeoutError as exc:
        raise http_error(SourceError("NMT GUGiK", "teren liczy się dłużej niż zwykle – spróbuj za chwilę")) from exc
    saved = res.facts.get("saved_note")
    today = clock.today_pl()
    return terrain_interpret.to_contract(res.facts, group, data_date=None if saved else min(today, analysis_date or today),
                                         saved_note=saved, soil_text=text)


@router.get("/terrain", response_model=Terrain)
async def get_terrain(
    parcel_id: str | None = Query(None, description="Pełny identyfikator działki ULDK"),
    lon: float | None = Query(None), lat: float | None = Query(None),
    date: dt.date | None = Query(None, description="A20: data analizy – data wyniku nie późniejsza niż ona"),
) -> Terrain:
    """Strefy terenu, spadki, odpływ i zagłębienia (NMT GUGiK) – liczone na żywo (zwykle 2–15 s), potem z cache."""
    return await terrain_contract(await resolve_any(parcel_id, lon, lat), date)


@router.post("/terrain", response_model=Terrain)
async def post_terrain(req: AnalysisRequest) -> Terrain:
    """Jak GET – dla pola narysowanego (`geometry`) albo działki / punktu w treści."""
    return await terrain_contract(await resolve_any(req.parcel_id, req.lon, req.lat, req.geometry), req.date)
