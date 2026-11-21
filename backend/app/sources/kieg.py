"""EGiB / KIEG GUGiK – klasy bonitacyjne gleb (CLAUDE.md, źródło 6). TYLKO INFORMACYJNIE (D4).

https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow
WMS 1.3.0 GetFeatureInfo, warstwy `kontury,uzytki`, CRS EPSG:2180 (BBOX: północ,wschód),
INFO_FORMAT=text/html. Odpowiedź: tabela wierszy <td>Etykieta</td><td>Wartość</td> dla działki
w punkcie, m.in. „Identyfikator działki”, „Oznaczenie użytku”, „Oznaczenie konturu”
(np. „RIIIb,RIVa,RIVb”). Wiele powiatów nie udostępnia klas – puste pola to NORMALNA sytuacja,
nie błąd. Nie odczytujemy „Grupy rejestrowej” ani innych pól o właścicielach.
"""

import asyncio
import html
import re
from dataclasses import dataclass, field
from datetime import date

from shapely.geometry.base import BaseGeometry

from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.geo import sample_points
from app.core.http import SourceError, get_with_retry

SOURCE = "KIEG / EGiB GUGiK"
SOURCE_URL = "https://integracja.gugik.gov.pl/"
NO_CLASSES_NOTE = "Powiat nie udostępnia klas bonitacyjnych w usłudze KIEG."

_ROW = re.compile(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", re.S | re.I)
_cache: TTLCache["KiegResult"] = TTLCache(ttl_s=7 * 24 * 3600, max_items=512, name="KIEG / EGiB")


@dataclass
class KiegResult:
    parcel_id: str
    classes: list[str] | None  # np. ["RIIIb", "RIVa"]; None = powiat nie udostępnia
    land_use: list[str] | None  # „Oznaczenie użytku”, np. ["R", "Ls"]
    published: date | None = None
    note: str | None = None
    points_checked: int = 0
    points_matched: int = 0
    raw_fields: dict[str, str] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return bool(self.classes)


def parse_html(text: str) -> dict[str, str]:
    """Tabela KIEG -> {etykieta: wartość}; pomija znaczniki i encje."""
    out = {}
    for k, v in _ROW.findall(text):
        key = html.unescape(re.sub(r"<[^>]+>", "", k)).strip()
        val = html.unescape(re.sub(r"<[^>]+>", "", v)).strip()
        out[key] = val
    return out


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in re.split(r"[,;]\s*", value) if p.strip()]


async def _info_at(e: float, n: float) -> dict[str, str]:
    d = 10.0
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": "kontury,uzytki",
        "QUERY_LAYERS": "kontury,uzytki",
        "STYLES": "",
        "CRS": "EPSG:2180",  # WMS 1.3.0 + EPSG:2180 => BBOX: północ, wschód
        "BBOX": f"{n - d},{e - d},{n + d},{e + d}",
        "WIDTH": "101",
        "HEIGHT": "101",
        "I": "50",
        "J": "50",
        "INFO_FORMAT": "text/html",
        "FORMAT": "image/png",
    }
    resp = await get_with_retry(settings.kieg_url, params, source=SOURCE, timeout_s=settings.kieg_timeout_s, retries=1)
    return parse_html(resp.text)


def merge(parcel_id: str, infos: list[dict[str, str]]) -> KiegResult:
    """Łączy odpowiedzi z kilku punktów; bierze tylko te, które dotyczą NASZEJ działki."""
    ours = [i for i in infos if i.get("Identyfikator działki") == parcel_id]
    classes: list[str] = []
    uses: list[str] = []
    published = None
    for i in ours:
        for c in _split(i.get("Oznaczenie konturu")):
            if c not in classes:
                classes.append(c)
        for u in _split(i.get("Oznaczenie użytku")):
            if u not in uses:
                uses.append(u)
        try:
            published = published or date.fromisoformat(i.get("Data publikacji danych", "")[:10])
        except ValueError:
            pass
    note = None
    if not ours:
        note = "Usługa KIEG nie zwróciła danych tej działki."
    elif not classes:
        note = NO_CLASSES_NOTE
    keep = {k: v for k, v in (ours[0] if ours else {}).items() if k in ("Oznaczenie użytku", "Oznaczenie konturu", "Data publikacji danych")}
    return KiegResult(
        parcel_id=parcel_id,
        classes=classes or None,
        land_use=uses or None,
        published=published,
        note=note,
        points_checked=len(infos),
        points_matched=len(ours),
        raw_fields=keep,
    )


async def classes_for_parcel(parcel_id: str, geom_2180: BaseGeometry, extra_points: int = 3) -> KiegResult:
    """Środek działki + do `extra_points` punktów w obrysie, równolegle. SourceError, gdy usługa nie odpowie."""
    return await cached_fetch(_cache, parcel_id, "EGiB (KIEG)", lambda: _download(parcel_id, geom_2180, extra_points))


async def _download(parcel_id: str, geom_2180: BaseGeometry, extra_points: int) -> KiegResult:
    pts = [geom_2180.representative_point()] + sample_points(geom_2180, extra_points)
    results = await asyncio.gather(*(_info_at(p.x, p.y) for p in pts), return_exceptions=True)
    infos = [r for r in results if isinstance(r, dict)]
    if not infos:
        err = next(r for r in results if isinstance(r, BaseException))
        raise err if isinstance(err, SourceError) else SourceError(SOURCE, f"błąd usługi ({err.__class__.__name__})")
    return merge(parcel_id, infos)


def clear_cache() -> None:
    _cache.clear()
