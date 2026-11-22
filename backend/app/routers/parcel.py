"""GET /api/parcel – wyszukanie działki w ULDK (numer, „obręb numer”, punkt)."""

from fastapi import APIRouter, HTTPException, Query

from app.core.geo import geojson
from app.core.http import SourceError, http_error, in_poland
from app.schemas.parcel import DataSource, ErrorDetail, Parcel, ParcelCandidates
from app.sources import uldk

router = APIRouter(prefix="/api", tags=["działka"])

MAX_CANDIDATES = 30


def parcel_out(p: uldk.Parcel) -> Parcel:
    if p.source == "drawn":
        zrodlo = DataSource(
            nazwa="Pole narysowane przez rolnika", url=p.admin_url or uldk.SOURCE_URL,
            pobrano=p.fetched_at.isoformat(timespec="seconds"),
            uwagi="Obrys narysowany na mapie – to nie jest działka ewidencyjna; powierzchnia z kształtu (EPSG:2180). "
                  + (p.admin_note or ""))
    else:
        zrodlo = DataSource(
            nazwa=uldk.SOURCE,
            url=uldk.SOURCE_URL,
            pobrano=p.fetched_at.isoformat(timespec="seconds"),
            uwagi="Powierzchnia policzona z geometrii (EPSG:2180), "
            "może nieznacznie różnić się od powierzchni ewidencyjnej.",
        )
    return Parcel(
        id=p.id,
        wojewodztwo=p.voivodeship,
        powiat=p.county,
        gmina=p.commune,
        obreb=p.region,
        numer=p.number,
        teryt_gminy=p.teryt_commune,
        powierzchnia_ha=p.area_ha,
        geometria=geojson(p.geom_4326),
        zrodlo=zrodlo,
        source=p.source if p.source in ("drawn", "approximate") else "uldk",
        name=p.name,
    )


async def resolve_parcel(parcel_id: str | None, lon: float | None, lat: float | None) -> uldk.Parcel:
    """Wspólne dla endpointów, które przyjmują działkę (analiza, warstwy, raport)."""
    if parcel_id and parcel_id.strip():
        # A8: obszar przybliżony i pole narysowane nie są działkami ULDK – warstwy i raport dostają je po id
        from app.analysis import approx_area, drawn_field

        pid = parcel_id.strip()
        if approx_area.is_approximate(pid) and (ap := approx_area.from_id(pid)) is not None:
            return ap
        if pid.startswith(drawn_field.ID_PREFIX + "_"):
            if (dp := drawn_field.registered(pid)) is not None:
                return dp
            raise HTTPException(status_code=404, detail=ErrorDetail(
                source="Pole narysowane", message="Pole narysowane – wyślij obrys jeszcze raz (POST z geometry).").model_dump())
        parcels = await uldk.by_id(parcel_id)
        if len(parcels) > 1:
            raise HTTPException(
                status_code=409,
                detail=ParcelCandidates(
                    message=f"Znaleziono {len(parcels)} działek o tym numerze – wybierz właściwą.",
                    total=len(parcels),
                    candidates=[parcel_out(p) for p in parcels[:MAX_CANDIDATES]],
                ).model_dump(),
            )
        return parcels[0]
    if lon is not None and lat is not None:
        if not in_poland(lon, lat):
            raise HTTPException(
                status_code=404,
                detail=ErrorDetail(source=uldk.SOURCE, message="Wskazany punkt leży poza Polską.").model_dump(),
            )
        return await uldk.by_point(lon, lat)
    raise HTTPException(status_code=422, detail={"message": "Podaj numer działki albo współrzędne (lon, lat)."})


@router.get(
    "/parcel",
    response_model=Parcel,
    responses={404: {"model": ErrorDetail}, 409: {"model": ParcelCandidates}, 502: {"model": ErrorDetail}},
)
async def get_parcel(
    id: str | None = Query(None, description="Np. 143203_2.0027.112/11 albo 'Szczytno 112/11'"),
    lon: float | None = None,
    lat: float | None = None,
) -> Parcel:
    try:
        return parcel_out(await resolve_parcel(id, lon, lat))
    except SourceError as exc:
        raise http_error(exc) from exc
