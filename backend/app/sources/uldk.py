"""ULDK GUGiK — Usługa Lokalizacji Działek Katastralnych.

Odpowiedź tekstowa: pierwsza linia to kod (>=0 OK, -1 brak wyników),
kolejne linie to rekordy z polami rozdzielonymi '|', w kolejności z parametru `result`.
"""

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry

from app.config import settings
from app.geo import parse_wkt, to_wgs84
from app.http import SourceError, get_client

SOURCE = "ULDK GUGiK"
_RESULT_FIELDS = ["geom_wkt", "id", "voivodeship", "county", "commune", "region", "parcel"]


@dataclass
class Parcel:
    id: str
    voivodeship: str
    county: str
    commune: str
    region: str
    number: str
    geom_2180: BaseGeometry

    @property
    def teryt_commune(self) -> str:
        """TERYT gminy (7 znaków, np. 1432032), z identyfikatora działki."""
        return self.id.split(".")[0].replace("_", "")

    @property
    def area_ha(self) -> float:
        return round(self.geom_2180.area / 10_000, 4)

    @property
    def geom_4326(self) -> BaseGeometry:
        return to_wgs84(self.geom_2180)


def parse_response(text: str) -> list[Parcel]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise SourceError(SOURCE, "pusta odpowiedź")
    head = lines[0].split()[0]
    try:
        code = int(head)
    except ValueError as exc:
        raise SourceError(SOURCE, f"nieoczekiwana odpowiedź: {lines[0][:80]}") from exc
    if code < 0:
        raise SourceError(SOURCE, "nie znaleziono działki")
    parcels = []
    for line in lines[1:]:
        parts = line.split("|")
        if len(parts) < len(_RESULT_FIELDS):
            continue
        rec = dict(zip(_RESULT_FIELDS, parts))
        parcels.append(
            Parcel(
                id=rec["id"],
                voivodeship=rec["voivodeship"],
                county=rec["county"],
                commune=rec["commune"],
                region=rec["region"],
                number=rec["parcel"],
                geom_2180=parse_wkt(rec["geom_wkt"]),
            )
        )
    if not parcels:
        raise SourceError(SOURCE, "nie znaleziono działki")
    return parcels


async def _query(params: dict) -> list[Parcel]:
    params = {**params, "result": ",".join(_RESULT_FIELDS), "srid": "2180"}
    try:
        resp = await get_client().get(settings.uldk_url, params=params)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise SourceError(SOURCE, f"usługa niedostępna ({exc.__class__.__name__})") from exc
    return parse_response(resp.text)


async def by_id(parcel_id: str) -> list[Parcel]:
    """Pełny identyfikator (np. 143203_2.0027.112/11) albo 'obręb numer' (np. 'Szczytno 112/11')."""
    parcel_id = parcel_id.strip()
    request = "GetParcelById" if "." in parcel_id and "_" in parcel_id else "GetParcelByIdOrNr"
    return await _query({"request": request, "id": parcel_id})


async def by_point(lon: float, lat: float) -> Parcel:
    parcels = await _query({"request": "GetParcelByXY", "xy": f"{lon},{lat},4326"})
    return parcels[0]
