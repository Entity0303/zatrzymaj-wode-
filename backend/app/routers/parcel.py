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


# ── F30: działki ewidencyjne pod polem narysowanym ───────────────────────────────────────────

AREA_POINTS = 12  # najwyżej tyle punktów w obrysie (środek + siatka)
AREA_LIMIT_S = 15.0
AREA_NOTE = "Nie udało się sprawdzić działek ewidencyjnych – spróbuj za chwilę."
_area_cache: dict[str, dict] = {}


def area_points(geom) -> list[tuple[float, float]]:
    """Punkty [lon, lat] wewnątrz obrysu: punkt wewnętrzny (środek) + równomierna siatka, razem najwyżej AREA_POINTS."""
    from shapely.geometry import Point

    c = geom.representative_point()
    pts = [(c.x, c.y)]
    x0, y0, x1, y1 = geom.bounds
    for n in (4, 5, 6, 8):  # gęstsza siatka, gdy kształt jest wąski i mało punktów trafia do środka
        grid = [(x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (j + 0.5) / n) for j in range(n) for i in range(n)]
        inside = [p for p in grid if geom.contains(Point(p))]
        if len(inside) >= AREA_POINTS - 1 or n == 8:
            step = max(1, len(inside) // (AREA_POINTS - 1))
            pts += inside[::step][: AREA_POINTS - 1]
            break
    return pts


@router.post("/parcels-in-area")
async def parcels_in_area(body: dict) -> dict:
    """F30: które działki ewidencyjne obejmuje narysowane pole – próbkowanie punktami (ULDK GetParcelByXY, z cache
    i limitem klienta). `share` = udział punktów, %. Błąd / ponad 15 s bez wyniku → pusta lista i `note`."""
    import asyncio
    import json

    from shapely.geometry import shape

    try:
        geom = shape(body.get("geometry") or {})
        if geom.is_empty or geom.geom_type != "Polygon" or not geom.is_valid:
            raise ValueError("obrys")
    except Exception as exc:  # noqa: BLE001 – każdy błędny obrys = 422
        raise HTTPException(status_code=422, detail={"message": "Podaj obrys pola (GeoJSON Polygon)."}) from exc
    key = json.dumps([[round(x, 5), round(y, 5)] for x, y in geom.exterior.coords])
    if key in _area_cache:
        return _area_cache[key]
    pts = area_points(geom)
    found: list[uldk.Parcel] = []
    failed = 0

    async def sample() -> None:
        nonlocal failed
        for lon, lat in pts:  # po kolei – klient ULDK pilnuje limitu GUGiK
            try:
                found.append(await uldk.by_point(lon, lat))
            except SourceError as exc:
                from app.core.http import NotFoundError

                if not isinstance(exc, NotFoundError):
                    failed += 1

    try:
        await asyncio.wait_for(sample(), AREA_LIMIT_S)
    except asyncio.TimeoutError:
        failed += 1
    if not found:
        return {"parcels": [], "note": AREA_NOTE if failed else None}
    counts: dict[str, list] = {}
    for p in found:
        counts.setdefault(p.id, [p, 0])[1] += 1
    parcels = [{"id": p.id, "obreb": p.region, "gmina": p.commune, "numer": p.number, "share": round(100 * n / len(found))}
               for p, n in sorted(counts.values(), key=lambda x: -x[1])]
    out = {"parcels": parcels, "note": None}
    if not failed:
        _area_cache[key] = out
    return out
