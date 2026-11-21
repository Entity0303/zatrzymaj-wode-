"""GET /api/search?q= – jedno pole wyszukiwania (A5c): identyfikator działki, „obręb + numer” albo nazwa miejscowości.

Główna ścieżka rolnika to zawsze dokładny obrys działki z ULDK (+ trwały cache): identyfikator i „obręb numer” idą do
istniejącego kodu (`uldk.by_id`: znane działki → cache → ULDK). Sama nazwa → geokoder (słownik demo / PRNG / Nominatim).
Brak wyników to nie błąd: 200 + pusta lista + podpowiedź. Awaria źródła trafia do `notices`.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from app.core.config import settings
from app.core.http import NotFoundError, SourceError
from app.core.search_query import HINT, ParsedQuery, fold, parse
from app.schemas.search import SearchResponse, SearchResult
from app.sources import nominatim, places, uldk

router = APIRouter(prefix="/api", tags=["wyszukiwanie"])
MAX_RESULTS = 10


def _strip(value: str, prefix: str) -> str:
    return nominatim.strip_prefix(value, prefix)


def place_label(name: str, gmina: str | None, powiat: str | None, woj: str | None) -> str:
    parts = [name]
    if gmina:
        parts.append(f"gm. {gmina}")
    if powiat:
        parts.append(f"pow. {_strip(powiat, 'powiat')}")
    if woj:
        parts.append(woj)
    return ", ".join(parts)


def parcel_result(p: uldk.Parcel) -> SearchResult:
    rp = p.geom_4326.representative_point()
    minx, miny, maxx, maxy = p.geom_4326.bounds
    name = f"{p.region} {p.number}".strip()
    powiat = _strip(p.county, "powiat")
    return SearchResult(
        kind="parcel", id=p.id, parcel_id=p.id, name=name, label=place_label(name, p.commune, powiat, p.voivodeship),
        lon=round(rp.x, 6), lat=round(rp.y, 6), gmina=p.commune, powiat=powiat, wojewodztwo=p.voivodeship,
        bbox=(round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)), bbox_approx=False, area_ha=p.area_ha,
        source=uldk.SOURCE)


def place_result(p: places.Place) -> SearchResult:
    powiat = _strip(p.powiat, "powiat")
    return SearchResult(
        kind="place", id=p.id, name=p.name, label=place_label(p.name, p.gmina, powiat, p.wojewodztwo),
        lon=round(p.lon, 6), lat=round(p.lat, 6), type=p.type, type_label=p.type_label, gmina=p.gmina or None,
        powiat=powiat or None, wojewodztwo=p.wojewodztwo or None, bbox=p.bbox, bbox_approx=p.bbox_approx, source=p.source)


async def _parcels(name: str, number: str, notices: list[str]) -> list[uldk.Parcel]:
    """„Obręb numer” → działki (znane → ULDK). Gdy ULDK nie zna nazwy w takim zapisie, próbuje kanonicznych nazw z
    geokodera (z polskimi znakami, wielkością liter) i wariantu z myślnikiem. Kilka obrębów o tej nazwie = kilka działek."""
    tried: set[str] = set()

    async def attempt(obreb: str) -> list[uldk.Parcel]:
        q = f"{obreb} {number}"
        if q in tried:  # dokładny zapis (wielkość liter, ogonki, myślnik) – „Tczow” i „Tczów” to różne zapytania do ULDK
            return []
        tried.add(q)
        try:
            return await uldk.by_id(q)
        except NotFoundError:
            return []

    try:
        found = await attempt(name)
        if not found and " " in name.strip():
            found = await attempt(name.strip().replace(" ", "-"))
        if not found:
            res = await places.find(name)
            canon = []
            for p in res.places:
                if fold(p.name) == fold(name) and p.name not in canon and p.name != name:
                    canon.append(p.name)
            for obreb in canon[:3]:
                found += await attempt(obreb)
                if found:
                    break
        return found
    except SourceError as exc:
        notices.append(f"{exc.source}: {exc.message}")
        return []


def _sorted_parcels(parcels: list[uldk.Parcel]) -> list[uldk.Parcel]:
    return sorted(parcels, key=lambda p: (fold(p.voivodeship), fold(p.county), fold(p.commune), fold(p.region)))


async def _search(pq: ParsedQuery) -> SearchResponse:
    notices: list[str] = []
    attribution = None
    hint: str | None = None
    results: list[SearchResult] = []
    total = 0
    truncated = False

    if pq.kind in ("empty", "unrecognized"):
        return SearchResponse(query=pq.text, interpreted_as=pq.kind, results=[], total=0, truncated=False, hint=HINT)

    if pq.kind == "parcel_id":
        try:
            parcels = await uldk.by_id(pq.parcel_id or "")
        except NotFoundError:
            parcels = []
            hint = f"Nie znaleziono działki o identyfikatorze {pq.parcel_id}. {HINT}"
        except SourceError as exc:
            parcels = []
            notices.append(f"{exc.source}: {exc.message}")
        results = [parcel_result(p) for p in _sorted_parcels(parcels)]
        total = len(results)

    elif pq.kind == "obreb_numer":
        parcels = await _parcels(pq.name or "", pq.number or "", notices)
        if parcels:
            results = [parcel_result(p) for p in _sorted_parcels(parcels)]
            total = len(results)
            if total > 1:
                hint = "Kilka obrębów o tej nazwie – wybierz właściwy (gmina i powiat są przy każdej pozycji)."
        else:  # nie ma takiej działki (albo ULDK niedostępne) – pokazujemy miejscowość, rolnik kliknie swoje pole
            res = await places.find(pq.name or "")
            notices += [n for n in res.notices if n not in notices]
            attribution = res.attribution
            results = [place_result(p) for p in res.places]
            total, truncated = len(results), res.truncated
            uldk_down = any(n.startswith(uldk.SOURCE) for n in notices)
            if results and uldk_down:
                hint = (f"Nie udało się teraz sprawdzić numeru {pq.number} (ewidencja działek nie odpowiada). Pokazuję "
                        "miejscowość – przybliż mapę i kliknij swoje pole.")
            elif results:
                hint = (f"Nie znaleziono działki nr {pq.number} w obrębie „{pq.name}”. Pokazuję miejscowość – przybliż "
                        "mapę i kliknij swoje pole.")
            elif uldk_down:
                hint = f"Nie udało się teraz sprawdzić numeru działki (ewidencja nie odpowiada). {HINT}"
            else:
                hint = f"Nie znaleziono działki nr {pq.number} w obrębie „{pq.name}”. {HINT}"

    else:  # name
        res = await places.find(pq.name or "", pq.area_hint)
        notices += res.notices
        attribution = res.attribution
        results = [place_result(p) for p in res.places]
        total, truncated = len(results), res.truncated

    if total > MAX_RESULTS:
        truncated = True
        hint = hint or f"Dużo wyników – dopisz gminę, np. {pq.name}, {results[0].gmina or 'gmina'}."
    if not results and hint is None:
        hint = HINT
    return SearchResponse(query=pq.text, interpreted_as=pq.kind, results=results[:MAX_RESULTS], total=total,
                          truncated=truncated, hint=hint, notices=notices, attribution=attribution)


@router.get("/search", response_model=SearchResponse)
async def search(q: str = Query("", max_length=200, description="Identyfikator działki, „obręb numer” albo nazwa miejscowości")
                 ) -> SearchResponse:
    """Podpowiedzi do jednego pola wyszukiwania (max 10). Rozpoznaje: `201305_2.0038.6/1` (działka),
    `Wnory-Wandy 6/1` (obręb + numer; kilka obrębów o tej nazwie = lista do wyboru), `Tczów` (miejscowość –
    `lon`, `lat`, `bbox` do przybliżenia mapy). Brak wyników = 200 + pusta lista + `hint`."""
    pq = parse(q)
    try:
        return await asyncio.wait_for(_search(pq), timeout=settings.search_timeout_s)
    except asyncio.TimeoutError:
        return SearchResponse(query=pq.text, interpreted_as=pq.kind, results=[], total=0, truncated=False, hint=HINT,
                              notices=["Wyszukiwanie trwa zbyt długo – spróbuj ponownie za chwilę."])
