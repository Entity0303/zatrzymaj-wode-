"""IUNG-PIB — kategorie podatności gleb na suszę (System Monitoringu Suszy Rolniczej).

Warstwa rastrowa Susza:katgl_landuse2024 na GeoServerze IUNG, odczyt przez WMS GetFeatureInfo.
Kategorie i zakresy wody ogólnie dostępnej (WOD) wg https://susza.iung.pulawy.pl/kategorie/

TODO (osoba A): więcej punktów dla dużych działek, kategoria do analysis/soil.py,
kody 11–14 = „to nie jest grunt rolny”.
"""

import asyncio
from collections import Counter
from dataclasses import dataclass

from app.core.config import settings
from app.core.geo import sample_points, to_wgs84
from app.core.http import SourceError, get_client

SOURCE = "IUNG-PIB SMSR (kategorie glebowe)"

# kod rastra -> (opis, WOD min [mm], WOD max [mm], czy grunt rolny mineralny)
CODES: dict[int, tuple[str, float | None, float | None, bool]] = {
    1: ("Kategoria I – bardzo podatna na suszę", None, 127.5, True),
    2: ("Kategoria II – podatna na suszę", 127.5, 169.9, True),
    3: ("Kategoria III – średnio podatna na suszę", 170.0, 202.5, True),
    4: ("Kategoria IV – mało podatna na suszę", 202.5, None, True),
    5: ("Gleby organiczne i pochodzenia organicznego", None, None, False),
    11: ("Lasy, zadrzewienia", None, None, False),
    12: ("Wody", None, None, False),
    13: ("Tereny zabudowane", None, None, False),
    14: ("Tereny komunikacyjne, nieużytki", None, None, False),
    19: ("Tereny niesklasyfikowane", None, None, False),
    99: ("Tereny niesklasyfikowane", None, None, False),
}

# reprezentatywna WOD dla kategorii (środek przedziału; skrajne – połowa szerokości sąsiedniej klasy)
REPRESENTATIVE_WOD_MM = {1: 106.0, 2: 148.7, 3: 186.2, 4: 220.0}


@dataclass
class SoilSample:
    lon: float
    lat: float
    code: int | None


@dataclass
class SoilResult:
    samples: list[SoilSample]

    @property
    def shares(self) -> dict[int, float]:
        codes = [s.code for s in self.samples if s.code is not None]
        if not codes:
            return {}
        cnt = Counter(codes)
        return {c: round(n / len(codes), 3) for c, n in cnt.most_common()}

    @property
    def dominant(self) -> int | None:
        return next(iter(self.shares), None)

    @property
    def agricultural_share(self) -> float:
        return round(sum(v for c, v in self.shares.items() if c in REPRESENTATIVE_WOD_MM), 3)

    @property
    def wod_mm(self) -> float | None:
        """Średnia ważona WOD dla mineralnej części działki."""
        agri = {c: v for c, v in self.shares.items() if c in REPRESENTATIVE_WOD_MM}
        total = sum(agri.values())
        if not total:
            return None
        return round(sum(REPRESENTATIVE_WOD_MM[c] * v for c, v in agri.items()) / total, 1)


async def _code_at(lon: float, lat: float) -> int | None:
    d = 0.0005
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": settings.iung_soil_layer,
        "QUERY_LAYERS": settings.iung_soil_layer,
        "CRS": "EPSG:4326",  # WMS 1.3.0 + EPSG:4326 => kolejność osi: lat, lon
        "BBOX": f"{lat - d},{lon - d},{lat + d},{lon + d}",
        "WIDTH": "101",
        "HEIGHT": "101",
        "I": "50",
        "J": "50",
        "INFO_FORMAT": "application/json",
    }
    resp = await get_client().get(settings.iung_wms_url, params=params)
    resp.raise_for_status()
    features = resp.json().get("features") or []
    if not features:
        return None
    value = features[0].get("properties", {}).get("GRAY_INDEX")
    if value is None:
        return None
    code = int(value)
    return None if code in (0, 255) else code


async def soil_for_parcel(geom_2180) -> SoilResult:
    pts = [to_wgs84(p) for p in sample_points(geom_2180, settings.soil_sample_points)]
    try:
        codes = await asyncio.gather(*(_code_at(p.x, p.y) for p in pts))
    except Exception as exc:  # noqa: BLE001
        raise SourceError(SOURCE, f"usługa niedostępna ({exc.__class__.__name__})") from exc
    return SoilResult([SoilSample(p.x, p.y, c) for p, c in zip(pts, codes)])
