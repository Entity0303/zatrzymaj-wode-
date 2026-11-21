"""ULDK GUGiK — Usługa Lokalizacji Działek Katastralnych (https://uldk.gugik.gov.pl/).

Zapytania:
- GetParcelById      – pełny identyfikator, np. 143203_2.0027.112/11
- GetParcelByIdOrNr  – „obręb numer”, np. „Szczytno 112/11” (może zwrócić kilka działek)
- GetParcelByXY      – punkt, xy=lon,lat,4326

Odpowiedź tekstowa: pierwsza linia to kod (>= 0 OK – zwykle liczba rekordów, -1 brak wyników),
kolejne linie to rekordy z polami rozdzielonymi '|', w kolejności z parametru `result`.
WKT może mieć prefiks 'SRID=2180;'. Geometria w EPSG:2180 jako (wschód, północ).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from shapely.geometry.base import BaseGeometry

from app.core.cache import TTLCache
from app.core.config import settings
from app.core.geo import parse_wkt, to_wgs84
from app.core.http import NotFoundError, SourceError, get_client

SOURCE = "ULDK GUGiK"
SOURCE_URL = "https://uldk.gugik.gov.pl/"
_RESULT_FIELDS = ["geom_wkt", "id", "voivodeship", "county", "commune", "region", "parcel"]
# pełny identyfikator: TERYT gminy (6 cyfr) _ typ (1 cyfra) . obręb (4 cyfry) . numer
_FULL_ID = re.compile(r"^\d{6}_\d\.\d{4}\.\S+$")

_cache: TTLCache[list["Parcel"]] = TTLCache(ttl_s=24 * 3600, max_items=512)


@dataclass
class Parcel:
    id: str
    voivodeship: str
    county: str
    commune: str
    region: str
    number: str
    geom_2180: BaseGeometry
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def teryt_commune(self) -> str:
        """TERYT gminy (7 znaków, np. 1432032), z identyfikatora działki."""
        return self.id.split(".")[0].replace("_", "")

    @property
    def area_ha(self) -> float:
        """Powierzchnia z geometrii w PL-1992 (metry) – nie jest to powierzchnia ewidencyjna."""
        return round(self.geom_2180.area / 10_000, 4)

    @property
    def geom_4326(self) -> BaseGeometry:
        return to_wgs84(self.geom_2180)


def is_full_id(text: str) -> bool:
    return bool(_FULL_ID.match(text.strip()))


def normalize_query(text: str) -> str:
    """'Szczytno, 112/11' / 'Szczytno  112/11' -> 'Szczytno 112/11'."""
    return re.sub(r"[\s,;]+", " ", text).strip()


def parse_response(text: str) -> list[Parcel]:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise SourceError(SOURCE, "pusta odpowiedź usługi")
    head, _, rest = lines[0].partition(" ")
    try:
        code = int(head)
    except ValueError as exc:
        raise SourceError(SOURCE, f"nieoczekiwana odpowiedź usługi: {lines[0][:80]}") from exc
    if code < 0:
        hint = rest.strip()
        msg = "nie znaleziono działki"
        if hint and "brak wyników" not in hint:
            msg += f" ({hint})"
        raise NotFoundError(SOURCE, msg)
    parcels = []
    for line in lines[1:]:
        parts = line.split("|")
        if len(parts) < len(_RESULT_FIELDS):
            continue
        rec = dict(zip(_RESULT_FIELDS, (p.strip() for p in parts)))
        try:
            geom = parse_wkt(rec["geom_wkt"])
        except Exception as exc:  # noqa: BLE001
            raise SourceError(SOURCE, f"nieprawidłowa geometria działki {rec['id']}") from exc
        parcels.append(
            Parcel(
                id=rec["id"],
                voivodeship=rec["voivodeship"],
                county=rec["county"],
                commune=rec["commune"],
                region=rec["region"],
                number=rec["parcel"],
                geom_2180=geom,
            )
        )
    if not parcels:
        raise NotFoundError(SOURCE, "nie znaleziono działki")
    return parcels


async def _get(params: dict) -> str:
    """GET z timeoutem i jedną ponowną próbą przy błędzie połączenia."""
    timeout = httpx.Timeout(settings.uldk_timeout_s)
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            resp = await get_client().get(settings.uldk_url, params=params, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise SourceError(
                SOURCE, f"usługa nie odpowiada (przekroczono {settings.uldk_timeout_s:.0f} s)"
            ) from exc
        except httpx.TransportError as exc:
            last_exc = exc
            continue
        if resp.status_code >= 400:
            raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
        return resp.text
    raise SourceError(
        SOURCE, f"brak połączenia z usługą ({last_exc.__class__.__name__})"
    ) from last_exc


async def _query(params: dict) -> list[Parcel]:
    params = {**params, "result": ",".join(_RESULT_FIELDS), "srid": "2180"}
    key = tuple(sorted(params.items()))
    hit = _cache.get(key)
    if hit is not None:
        return hit
    parcels = parse_response(await _get(params))
    _cache.set(key, parcels)
    return parcels


def clear_cache() -> None:
    _cache.clear()


async def by_id(query: str) -> list[Parcel]:
    """Pełny identyfikator (np. 143203_2.0027.112/11) albo 'obręb numer' (np. 'Szczytno 112/11')."""
    query = normalize_query(query)
    if not query:
        raise NotFoundError(SOURCE, "pusty numer działki")
    request = "GetParcelById" if is_full_id(query) else "GetParcelByIdOrNr"
    return await _query({"request": request, "id": query})


async def by_point(lon: float, lat: float) -> Parcel:
    parcels = await _query({"request": "GetParcelByXY", "xy": f"{lon:.7f},{lat:.7f},4326"})
    return parcels[0]
