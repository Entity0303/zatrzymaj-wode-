"""ULDK GUGiK — Usługa Lokalizacji Działek Katastralnych (https://uldk.gugik.gov.pl/).

Zapytania:
- GetParcelById      – pełny identyfikator, np. 143203_2.0027.112/11
- GetParcelByIdOrNr  – „obręb numer”, np. „Szczytno 112/11” (może zwrócić kilka działek)
- GetParcelByXY      – punkt, xy=lon,lat,4326

Odpowiedź tekstowa: pierwsza linia to kod (>= 0 OK – zwykle liczba rekordów, -1 brak wyników),
kolejne linie to rekordy z polami rozdzielonymi '|', w kolejności z parametru `result`.
WKT może mieć prefiks 'SRID=2180;'. Geometria w EPSG:2180 jako (wschód, północ).
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from app.core.cache import FOREVER, TTLCache, cached_fetch
from app.core.config import settings
from app.core.geo import parse_wkt, to_wgs84
from app.core.http import NotFoundError, RedirectBlocked, SourceError, request

SOURCE = "ULDK GUGiK"
SOURCE_URL = "https://uldk.gugik.gov.pl/"
_RESULT_FIELDS = ["geom_wkt", "id", "voivodeship", "county", "commune", "region", "parcel"]
# pełny identyfikator: TERYT gminy (6 cyfr) _ typ (1 cyfra) . obręb (4 cyfry) . numer
_FULL_ID = re.compile(r"^\d{6}_\d\.\d{4}\.\S+$")

# działki – bez wygasania (D53); klucz = parametry zapytania albo ("id", <id>) dla każdej pobranej działki
_cache: TTLCache[list["Parcel"]] = TTLCache(ttl_s=None, max_items=2048, name="ULDK GUGiK")


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
    # A5c: działka z ULDK (domyślnie) albo obszar bez granic z ULDK: „approximate” (D69) / „drawn” (obrys rolnika, D75)
    source: str = "uldk"
    name: str | None = None            # np. „Pole narysowane przez rolnika”
    teryt: str | None = None           # TERYT gminy dla pól bez identyfikatora ULDK
    admin_note: str | None = None      # skąd gmina / powiat / województwo (pola narysowane)
    admin_url: str | None = None

    @property
    def teryt_commune(self) -> str:
        """TERYT gminy (7 znaków, np. 1432032), z identyfikatora działki (pola narysowane: z działki w środku pola
        albo pusty)."""
        if self.source != "uldk":
            return self.teryt or ""
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


def _blocked(resp: httpx.Response) -> str | None:
    """Objawy blokady / ograniczania ruchu przez ULDK (D54): 429, przekierowanie (302 → resp/uldk.php), HTML zamiast
    odpowiedzi tekstowej. None = zwykła odpowiedź."""
    if resp.status_code == 429:
        return "usługa ogranicza liczbę zapytań (HTTP 429) – spróbuj za chwilę"
    if 300 <= resp.status_code < 400:
        return "usługa chwilowo ogranicza ruch (przekierowanie) – spróbuj za chwilę"
    head = resp.text[:300].lstrip().lower()
    if head.startswith("<!doctype") or head.startswith("<html") or "<html" in head:
        return "usługa zwróciła stronę HTML zamiast danych (ograniczenie ruchu) – spróbuj za chwilę"
    return None


async def _get(params: dict) -> str:
    """GET z timeoutem. Blokada (429 / przekierowanie / HTML) → ponowienie po 1 s i 3 s (maks. 2 razy), każde na nowym
    połączeniu, potem SourceError – a `cached_fetch` otwiera bezpiecznik na 60 s (D54). Przekierowania nie śledzimy:
    resp/uldk.php zwraca pozorne „0” ze śmieciową geometrią (D45)."""
    delays = [0.0, *settings.uldk_retry_delays_s]
    last = "brak odpowiedzi"
    for attempt, delay in enumerate(delays):
        if delay:
            await asyncio.sleep(delay)
        try:
            headers = {"Connection": "close"} if attempt else None
            # bez przekierowań i bez czytania treści 3xx; limit 5 MB (odpowiedź ULDK to kilka kB) – D56
            resp = await request("GET", settings.uldk_url, source=SOURCE, timeout_s=settings.uldk_timeout_s,
                                 params=params, headers=headers, max_bytes=5_000_000)
        except RedirectBlocked as exc:
            last = exc.message
            continue
        except httpx.TimeoutException as exc:
            raise SourceError(SOURCE, f"usługa nie odpowiada (przekroczono {settings.uldk_timeout_s:.0f} s)") from exc
        except httpx.TransportError as exc:
            last = f"brak połączenia z usługą ({exc.__class__.__name__})"
            continue
        if (why := _blocked(resp)) is not None:
            last = why
            continue
        if resp.status_code >= 400:
            raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
        return resp.text
    raise SourceError(SOURCE, last)


# ── znane działki: cache bez wygasania + działki demo z repo (D54) ──────────────────────────
# Każda pobrana działka trafia pod klucz ("id", <id>). Zapytanie po id albo po punkcie najpierw sprawdza znane
# działki (shapely: punkt w obrysie) – ULDK tylko wtedy, gdy działki nie znamy.

DEMO_FILE = Path(__file__).parents[1] / "data" / "demo_parcels.json"
_known: dict[str, Parcel] = {}
_known_loaded = False


def remember(parcels: list[Parcel]) -> None:
    for p in parcels:
        _known[p.id] = p
        if _cache.get(("id", p.id)) is None:
            _cache.set(("id", p.id), [p])


def demo_parcels() -> list[dict]:
    """Wpisy z app/data/demo_parcels.json (także te z flagą `needs_fetch` – bez geometrii)."""
    try:
        return json.loads(DEMO_FILE.read_text(encoding="utf-8"))["parcels"]
    except FileNotFoundError:
        return []


def parcel_from_demo(d: dict) -> Parcel | None:
    if not d.get("geom_wkt_2180"):
        return None
    return Parcel(id=d["id"], voivodeship=d["wojewodztwo"], county=d["powiat"], commune=d["gmina"],
                  region=d["obreb"], number=d["numer"], geom_2180=parse_wkt(d["geom_wkt_2180"]),
                  fetched_at=datetime.fromisoformat(d["fetched_at"]) if d.get("fetched_at") else datetime.now(timezone.utc))


def load_known(force: bool = False) -> int:
    """Indeks znanych działek: wszystkie wpisy ULDK z cache (pamięć + plik) i działki demo z repo."""
    global _known_loaded
    if _known_loaded and not force:
        return len(_known)
    _known_loaded = True
    for value in _cache.values():
        for p in value or []:
            if isinstance(p, Parcel):
                _known.setdefault(p.id, p)
    if settings.demo_parcels_preload:
        for d in demo_parcels():
            p = parcel_from_demo(d)
            if p is not None and p.id not in _known:
                remember([p])
    return len(_known)


def known_by_id(parcel_id: str) -> Parcel | None:
    load_known()
    return _known.get(parcel_id.strip())


def known_at(lon: float, lat: float) -> Parcel | None:
    load_known()
    pt = Point(lon, lat)
    return next((p for p in _known.values() if p.geom_4326.covers(pt)), None)


def known_by_region_number(query: str) -> list[Parcel]:
    """„Obręb numer” wśród znanych działek (zapas, gdy ULDK jest zablokowane)."""
    load_known()
    region, _, number = query.rpartition(" ")
    return [p for p in _known.values() if p.number == number and p.region.lower() == region.lower()]


async def _query(params: dict) -> list[Parcel]:
    params = {**params, "result": ",".join(_RESULT_FIELDS), "srid": "2180"}
    key = tuple(sorted(params.items()))

    async def download() -> list[Parcel]:
        return parse_response(await _get(params))

    parcels = await cached_fetch(_cache, key, SOURCE, download, ttl_s=FOREVER, breaker_s=settings.uldk_breaker_s)
    remember(parcels)
    return parcels


def clear_cache() -> None:
    global _known_loaded
    _cache.clear()
    _known.clear()
    _known_loaded = False


async def by_id(query: str) -> list[Parcel]:
    """Pełny identyfikator (np. 143203_2.0027.112/11) albo 'obręb numer' (np. 'Szczytno 112/11')."""
    query = normalize_query(query)
    if not query:
        raise NotFoundError(SOURCE, "pusty numer działki")
    if is_full_id(query):
        if (p := known_by_id(query)) is not None:
            return [p]
        return await _query({"request": "GetParcelById", "id": query})
    try:
        return await _query({"request": "GetParcelByIdOrNr", "id": query})
    except NotFoundError:
        raise
    except SourceError:
        local = known_by_region_number(query)
        if local:  # ULDK zablokowane – działka znana z cache / demo
            return local
        raise


async def by_point(lon: float, lat: float) -> Parcel:
    if (p := known_at(lon, lat)) is not None:
        return p
    parcels = await _query({"request": "GetParcelByXY", "xy": f"{lon:.7f},{lat:.7f},4326"})
    return parcels[0]
