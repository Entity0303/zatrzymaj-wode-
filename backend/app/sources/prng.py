"""PRNG GUGiK – Państwowy Rejestr Nazw Geograficznych (WFS 2.0, warstwa M1_UrzedoweNazwyMiejscowosci).

Sprawdzone na żywo 2026-11-21 (D73): GetFeature z filtrem fes:PropertyIsLike (wildCard `*`, singleChar `.`, matchCase=false)
po polu NAZWAGLOWNA, srsName=EPSG:4326 (kolejność osi: `lat lon`), odpowiedź GML 3.2 w UTF-8, ok. 2 s.
Filtr PropertyIsEqualTo z polskim znakiem nic nie zwracał, a wzorzec `tcz*w` zwracał Tczów – dlatego zawsze wzorzec
LIKE, z „.” za litery, które w nazwie mogą mieć polski znak (rolnik bez ogonków: „Tczow” → `Tcz.w*`). Usługa po serii
szybkich zapytań odrzuca połączenia (ConnectError po kilku ms) – wspólny odstęp między zapytaniami + jedna ponowna próba.
Współrzędne to punkt miejscowości (bbox wyznaczamy sami w wyszukiwaniu, PRNG go nie daje).
"""

from __future__ import annotations

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from app.core.cache import FOREVER, TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, request
from app.core.search_query import fold

SOURCE = "PRNG GUGiK"
SOURCE_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRNG/WFS/GeographicalNames"
MAX_FEATURES = 200
_NS = {"ms": "http://mapserver.gis.umn.edu/mapserver", "gml": "http://www.opengis.net/gml/3.2",
       "wfs": "http://www.opengis.net/wfs/2.0"}
_DIACRITIC_BASE = set("acelnosz")  # litery, które mogą mieć polski znak (ą ć ę ł ń ó ś ź ż)

_cache: TTLCache[list["PrngPlace"]] = TTLCache(ttl_s=None, max_items=4096, name=SOURCE)
_gate = asyncio.Lock()
_last_request = 0.0


@dataclass
class PrngPlace:
    prng_id: str
    simc: str | None
    name: str
    kind: str          # rodzaj obiektu z PRNG: miasto, wieś, osada, kolonia, przysiółek …
    gmina: str
    teryt_gminy: str | None
    powiat: str
    wojewodztwo: str
    lon: float
    lat: float


def _like_body(name: str, loose: bool) -> str:
    out = []
    for ch in re.sub(r"[*!]", "", name.strip()):
        if ch in " -–—_":
            out.append(".")
        elif ch == ".":
            continue
        elif not ch.isascii() or (loose and ch.lower() in _DIACRITIC_BASE):
            out.append(".")  # polski znak wpisany jawnie też jako „.” – literał „ó” usługa nie dopasowuje (sprawdzone na żywo)
        else:
            out.append(ch)
    return "".join(out)


def like_pattern(name: str, loose: bool = False) -> str:
    """Wzorzec LIKE do filtra: każdy znak spoza ASCII → „.” (jeden dowolny znak – literał „ó” usługa nie dopasowuje,
    sprawdzone na żywo), spacje i myślniki → „.”, na końcu `*` (podpowiedzi po początku nazwy). Wariant `loose`
    (rolnik wpisał bez ogonków) zamienia też litery a c e l n o s z na „.” – szerszy, używany tylko gdy ścisły nic nie dał.
    Znaki specjalne wzorca są usuwane."""
    return _like_body(name, loose) + "*"


def _like(field: str, pattern: str) -> str:
    lit = pattern.replace("&", "&amp;").replace("<", "&lt;")
    return ('<PropertyIsLike wildCard="*" singleChar="." escapeChar="!" matchCase="false">'
            f"<ValueReference>{field}</ValueReference><Literal>{lit}</Literal></PropertyIsLike>")


def build_filter(name: str, loose: bool = False, hints: tuple[str, ...] = ()) -> str:
    """Nazwa (początek) + opcjonalnie każdy `hint` musi pojawić się w gminie, powiecie albo województwie."""
    conds = [_like("NAZWAGLOWNA", like_pattern(name, loose))]
    for h in hints:
        body = "*" + _like_body(h, True) + "*"
        conds.append("<Or>" + "".join(_like(f, body) for f in ("GMINA", "POWIAT", "WOJEWODZTWO")) + "</Or>")
    inner = conds[0] if len(conds) == 1 else "<And>" + "".join(conds) + "</And>"
    return f'<Filter xmlns="http://www.opengis.net/fes/2.0">{inner}</Filter>'


_GMINA_SUFFIX = re.compile(r"\s*-\s*gmina\s+(wiejska|miejska|miejsko-wiejska)\s*$", re.IGNORECASE)


def clean_gmina(text: str) -> str:
    """„Tczów-gmina wiejska” → „Tczów”."""
    return _GMINA_SUFFIX.sub("", text or "").strip()


def _text(el: ET.Element, tag: str) -> str:
    node = el.find(f"ms:{tag}", _NS)
    return (node.text or "").strip() if node is not None and node.text else ""


def parse_response(xml_text: str) -> list[PrngPlace]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceError(SOURCE, "nieprawidłowa odpowiedź usługi (XML)") from exc
    if root.tag.endswith("ExceptionReport"):
        raise SourceError(SOURCE, "usługa zwróciła błąd zapytania")
    places = []
    for member in root.findall("wfs:member", _NS):
        el = member[0]
        pos = el.find(".//gml:pos", _NS)
        if pos is None or not pos.text:
            continue
        try:
            lat, lon = (float(x) for x in pos.text.split()[:2])
        except ValueError:
            continue
        places.append(PrngPlace(
            prng_id=_text(el, "IDENTYFIKATORPRNG"), simc=_text(el, "IDENTYFIKATORSIMC") or None,
            name=_text(el, "NAZWAGLOWNA"), kind=_text(el, "RODZAJOBIEKTU"), gmina=clean_gmina(_text(el, "GMINA")),
            teryt_gminy=_text(el, "IDENTYFIKATORGMINY") or None, powiat=_text(el, "POWIAT"),
            wojewodztwo=_text(el, "WOJEWODZTWO"), lon=lon, lat=lat))
    return [p for p in places if p.name]


async def _get(name: str, loose: bool = False, hints: tuple[str, ...] = ()) -> str:
    """Jedno zapytanie z odstępem między zapytaniami i jedną ponowną próbą po błędzie połączenia."""
    global _last_request
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
              "typeNames": "ms:M1_UrzedoweNazwyMiejscowosci", "count": str(MAX_FEATURES), "srsName": "EPSG:4326",
              "filter": build_filter(name, loose, hints)}
    last = "brak odpowiedzi"
    for attempt in range(2):
        resp = None
        async with _gate:
            wait = settings.prng_min_interval_s - (time.monotonic() - _last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request = time.monotonic()
            try:
                resp = await request("GET", settings.prng_url, source=SOURCE, timeout_s=settings.prng_timeout_s,
                                     params=params, max_bytes=5_000_000)
            except RedirectBlocked as exc:
                raise SourceError(SOURCE, exc.message) from exc
            except httpx.TimeoutException as exc:
                raise SourceError(SOURCE, f"usługa nie odpowiada (przekroczono {settings.prng_timeout_s:.0f} s)") from exc
            except httpx.TransportError as exc:
                last = f"brak połączenia z usługą ({exc.__class__.__name__})"
        if resp is None:
            if attempt == 0:
                await asyncio.sleep(settings.prng_retry_delay_s)
            continue
        if resp.status_code != 200:
            raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
        return resp.text
    raise SourceError(SOURCE, last)


async def _search_pattern(name: str, loose: bool, hints: tuple[str, ...]) -> list[PrngPlace]:
    key = ("name", like_pattern(name, loose), tuple(fold(h) for h in hints))

    async def download() -> list[PrngPlace]:
        return parse_response(await _get(name, loose, hints))

    return await cached_fetch(_cache, key, SOURCE, download, ttl_s=FOREVER, breaker_s=settings.prng_breaker_s)


async def search(name: str, hints: list[str] | None = None) -> tuple[list[PrngPlace], bool]:
    """Miejscowości, których nazwa zaczyna się od `name` (bez rozróżniania wielkości liter i polskich znaków) +
    flaga „lista przycięta do 200”. `hints` (gmina / powiat / województwo) zawężają listę po stronie usługi.
    Najpierw wzorzec ścisły; gdy nic i nazwa jest bez polskich znaków – szeroki („Brzezno” → Brzeźno).
    Wyniki w cache bez wygasania (nazwy urzędowe zmieniają się rzadko)."""
    hs = tuple(h for h in (hints or []) if h.strip())
    want = fold(name)
    raw = await _search_pattern(name, False, hs)
    found = [p for p in raw if fold(p.name).startswith(want)]  # usługa nie zna naszych zasad zrównywania znaków
    if not found and name.isascii():
        raw = await _search_pattern(name, True, hs)
        found = [p for p in raw if fold(p.name).startswith(want)]
    return found, len(raw) >= MAX_FEATURES


def clear_cache() -> None:
    global _last_request
    _cache.clear()
    _last_request = 0.0
