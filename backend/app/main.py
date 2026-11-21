from contextlib import asynccontextmanager
from datetime import date, timedelta

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.geo import geojson
from app.http import NotFoundError, SourceError, close_client
from app.sources import iung, nasa_power, uldk


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_client()


app = FastAPI(
    title="Zatrzymaj wodę – API",
    description="Ocena sytuacji wodnej działki rolnej na podstawie danych publicznych.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _source_error(exc: SourceError) -> HTTPException:
    status = 404 if isinstance(exc, NotFoundError) else 502
    return HTTPException(status_code=status, detail={"source": exc.source, "message": exc.message})


MAX_CANDIDATES = 30


def _parcel_out(p: uldk.Parcel) -> dict:
    return {
        "id": p.id,
        "wojewodztwo": p.voivodeship,
        "powiat": p.county,
        "gmina": p.commune,
        "obreb": p.region,
        "numer": p.number,
        "teryt_gminy": p.teryt_commune,
        "powierzchnia_ha": p.area_ha,
        "geometria": geojson(p.geom_4326),
        "zrodlo": {
            "nazwa": uldk.SOURCE,
            "url": uldk.SOURCE_URL,
            "pobrano": p.fetched_at.isoformat(timespec="seconds"),
            "uwagi": "Powierzchnia policzona z geometrii (EPSG:2180), "
            "może nieznacznie różnić się od powierzchni ewidencyjnej.",
        },
    }


async def _resolve_parcel(parcel_id: str | None, lon: float | None, lat: float | None) -> uldk.Parcel:
    if parcel_id and parcel_id.strip():
        parcels = await uldk.by_id(parcel_id)
        if len(parcels) > 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"Znaleziono {len(parcels)} działek o tym numerze – wybierz właściwą.",
                    "total": len(parcels),
                    "candidates": [_parcel_out(p) for p in parcels[:MAX_CANDIDATES]],
                },
            )
        return parcels[0]
    if lon is not None and lat is not None:
        if not (14.0 <= lon <= 24.2 and 49.0 <= lat <= 55.0):
            raise HTTPException(status_code=404, detail={
                "source": uldk.SOURCE, "message": "Wskazany punkt leży poza Polską."})
        return await uldk.by_point(lon, lat)
    raise HTTPException(
        status_code=422, detail={"message": "Podaj numer działki albo współrzędne (lon, lat)."}
    )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/parcel")
async def parcel(
    id: str | None = Query(None, description="Np. 143203_2.0027.112/11 albo 'Szczytno 112/11'"),
    lon: float | None = None,
    lat: float | None = None,
) -> dict:
    try:
        return _parcel_out(await _resolve_parcel(id, lon, lat))
    except SourceError as exc:
        raise _source_error(exc) from exc


@app.get("/api/soil")
async def soil(id: str) -> dict:
    try:
        p = await _resolve_parcel(id, None, None)
        res = await iung.soil_for_parcel(p.geom_2180)
    except SourceError as exc:
        raise _source_error(exc) from exc
    return {
        "parcel_id": p.id,
        "dominant_code": res.dominant,
        "dominant_label": iung.CODES.get(res.dominant, ("brak danych",))[0] if res.dominant else None,
        "shares": [
            {"code": c, "label": iung.CODES.get(c, ("nieznany kod",))[0], "share": s}
            for c, s in res.shares.items()
        ],
        "agricultural_share": res.agricultural_share,
        "wod_mm": res.wod_mm,
        "samples": [{"lon": s.lon, "lat": s.lat, "code": s.code} for s in res.samples],
        "source": iung.SOURCE,
    }


@app.get("/api/weather")
async def weather(
    lon: float,
    lat: float,
    as_of: date | None = Query(None, description="Data analizy; domyślnie dziś"),
) -> dict:
    end = as_of or date.today()
    start = date(end.year - settings.history_years, 1, 1)
    try:
        w = await nasa_power.fetch(lon, lat, start, end)
    except SourceError as exc:
        raise _source_error(exc) from exc
    valid = ~np.isnan(w.precip)
    last_valid = max((d for d, ok in zip(w.dates, valid) if ok), default=None)
    season_start = date(end.year, 3, 1)
    in_season = np.array([season_start <= d <= end for d in w.dates])
    kbw_season = float(np.nansum(w.climatic_water_balance[in_season])) if in_season.any() else 0.0
    return {
        "lat": w.lat,
        "lon": w.lon,
        "elevation_m": w.elevation_m,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "last_valid_date": last_valid.isoformat() if last_valid else None,
        "days": len(w.dates),
        "kbw_season_mm": round(kbw_season, 1),
        "et0_methods": {m: int((w.et0_method == m).sum()) for m in ("PM", "HG", "")},
        "daily": [
            {
                "date": d.isoformat(),
                "precip": None if p != p else round(float(p), 2),
                "et0": None if e != e else round(float(e), 2),
            }
            for d, p, e in zip(w.dates[-60:], w.precip[-60:], w.et0[-60:])
        ],
        "source": nasa_power.SOURCE,
    }


@app.get("/api/meta/today")
async def today() -> dict:
    t = date.today()
    return {"today": t.isoformat(), "min_analysis_date": (t - timedelta(days=365 * 10)).isoformat()}
