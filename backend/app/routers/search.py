"""GET /api/search?q= – jedno pole wyszukiwania (A5c): identyfikator działki, „obręb + numer” albo nazwa miejscowości.

Główna ścieżka rolnika to zawsze dokładny obrys działki z ULDK (+ trwały cache): identyfikator i „obręb numer” idą do
istniejącego kodu (`uldk.by_id`: znane działki → cache → ULDK). Sama nazwa → geokoder (słownik demo / PRNG / Nominatim).
Brak wyników to nie błąd: 200 + pusta lista + podpowiedź. Awaria źródła trafia do `notices`.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Query

from app.core import parcel_search as ps
from app.core.config import settings
from app.core.format import plural
from app.core.http import NotFoundError, SourceError
from app.core.search_query import HINT, ParsedQuery, fold, parse
from app.schemas.search import SearchResponse, SearchResult
from app.sources import nominatim, places, uldk, uug

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


def _gmina_hint(res: ps.GminaSearch, number: str, found: list[uldk.Parcel]) -> str:
    """Podpowiedź po „gmina + numer” – co sprawdziliśmy i co rolnik może dopisać. `found` – wszystkie trafienia
    (także obręb o nazwie gminy ze zwykłego „obręb numer”)."""
    k, n = len(res.checked) + res.skipped, res.total
    if found:
        txt = (f"Działki nr {number} w gminie {res.gmina} – wybierz obręb (wieś)." if len(found) > 1 else
               f"Działka nr {number} w gminie {res.gmina}, obręb {found[0].region} – sprawdź, czy to ta.")
        if res.next_name:
            txt += (f" Sprawdziłem {k} z {n} obrębów gminy – jeśli Twojej działki nie ma na liście, dopisz nazwę wsi "
                    f"(obrębu), np. {res.next_name} {number}.")
        return txt
    if res.next_name:
        return (f"Dopisz nazwę wsi (obrębu), np. {res.next_name} {number}. W gminie {res.gmina} "
                f"{plural(n, 'jest', 'są', 'jest')} {n} {plural(n, 'obręb', 'obręby', 'obrębów')} – w {k} sprawdzonych "
                f"nie ma działki nr {number}.")
    return f"Nie znaleziono działki nr {number} w gminie {res.gmina} (sprawdzone obręby: {k} z {n})."


async def _find_parcels(name: str, number: str, hints: list[str], notices: list[str],
                        deadline: float) -> tuple[list[uldk.Parcel], str | None]:
    """A19: „obręb numer” → działki; z gminą jako filtrem („Kobylin-Borzymy, Wnory-Wandy 6/1”, „Wnory-Wandy 6/1
    Kobylin-Borzymy”) – tylko z tej gminy; gdy nazwa to gmina („Kobylin-Borzymy 6/1”, „Wronki 70/4”) – szukanie w
    obrębach gminy (`parcel_search`). Zwraca (działki, podpowiedź)."""
    hits = await _parcels(name, number, notices)
    tried = {name}
    if hints:
        narrowed = [p for p in hits if ps.matches_area(p, hints)]
        if narrowed:  # obręb o tej nazwie jest w kilku gminach – zostaje ten z podanej gminy
            return narrowed, None
        for h in hints:  # odwrotna kolejność: „Wnory-Wandy, Kobylin-Borzymy 6/1”
            alt = [p for p in await _parcels(h, number, notices) if ps.matches_area(p, [name])]
            tried.add(h)
            if alt:
                return alt, None
        plan = [(h, name) for h in hints] + [(name, " ".join(hints))]
        base: list[uldk.Parcel] = []
    else:
        # obręb znaleziony i to NIE jest siedziba gminy o tej samej nazwie – zwykłe „obręb numer”
        if hits and not all(fold(p.commune) == fold(name) or fold(p.commune).startswith(fold(name) + " ") for p in hits):
            return hits, None
        plan, base = [(name, "")], hits
    if any(n.startswith(uldk.SOURCE) for n in notices):  # ULDK już nie odpowiada – nie dokładamy kolejnych zapytań
        return hits, None
    for gmina, rest in plan:
        try:
            res = await ps.search_gmina(gmina, number, rest, skip=tried, deadline=deadline)
        except SourceError as exc:
            notices.append(f"{exc.source}: {exc.message}")
            break
        if res is None:  # to nie jest nazwa gminy
            continue
        if not res.checked and not res.parcels and not res.next_name:  # gmina = jeden obręb, już sprawdzony
            break
        if res.stop_reason == "uldk":
            notices.append(f"{uldk.SOURCE}: sprawdziłem {len(res.checked)} z {res.total} obrębów gminy {res.gmina} – "
                           "ewidencja przestała odpowiadać, spróbuj za chwilę.")
        seen = {p.id for p in base}
        found = base + [p for p in res.parcels if p.id not in seen]
        return found, _gmina_hint(res, number, found)
    if hints and hits:
        return hits, (f"Nie znaleziono działki nr {number} w „{', '.join(hints)}” – pokazuję obręby „{name}” "
                      "w innych gminach.")
    return hits, None


def _sorted_parcels(parcels: list[uldk.Parcel]) -> list[uldk.Parcel]:
    return sorted(parcels, key=lambda p: (fold(p.voivodeship), fold(p.county), fold(p.commune), fold(p.region)))


def address_result(a) -> SearchResult:
    """A9: adres punktowy (PRG / OSM) – rolnik przybliża mapę do domu i klika swoje pole."""
    name = f"{a.street} {a.house_number}" if a.street else f"{a.locality} {a.house_number}"
    head = f"ul. {a.street} {a.house_number}, {a.locality}" if a.street else f"{a.locality} {a.house_number}"
    return SearchResult(kind="address", id=a.id, label=place_label(head, a.gmina or None, a.powiat or None,
                                                                   a.wojewodztwo or None),
                        name=name, lon=a.lon, lat=a.lat, gmina=a.gmina or None, powiat=_strip(a.powiat, "powiat") or None,
                        wojewodztwo=a.wojewodztwo or None, bbox=places.point_bbox(a.lon, a.lat, False), bbox_approx=True,
                        locality=a.locality, street=a.street, house_number=a.house_number, source=a.source)


async def _addresses(locality: str, number: str, street: str | None, notices: list[str]) -> tuple[list, str | None]:
    """Adres: UUG GUGiK (PRG) → rezerwa Nominatim OSM (gdy UUG zablokowane / bez wyniku). Zwraca (adresy, atrybucja)."""
    if not settings.search_addresses or ("/" in number and not street):  # „6/1” bez ulicy – to działka, nie dom
        return [], None
    try:
        found = await uug.find(locality, number, street)
        if found:
            return found, uug.ATTRIBUTION
    except SourceError as exc:
        notices.append(f"{exc.source}: {exc.message}")
    try:
        found = await nominatim.addresses(locality, number, street)
        if found:
            return found, nominatim.ATTRIBUTION
    except SourceError as exc:
        notices.append(f"{exc.source}: {exc.message}")
    return [], None


async def _search(pq: ParsedQuery) -> SearchResponse:
    deadline = time.monotonic() + settings.search_gmina_budget_s  # A19: budżet na sprawdzanie obrębów gminy
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
        # A9: „miejscowość numer” – działka (ULDK) I adres (PRG / OSM) równolegle; „miejscowość, ul. ulica numer” – adres
        p_hint: str | None = None
        if pq.street and pq.alt_parcel:  # A19: „gmina, obręb numer” bez „ul.” – adres ALBO działka
            alt_name, alt_hints = pq.alt_parcel
            (parcels, p_hint), (addrs, a_attr) = await asyncio.gather(
                _find_parcels(alt_name, pq.number or "", alt_hints, notices, deadline),
                _addresses(pq.name or "", pq.number or "", pq.street, notices))
        elif pq.street:
            parcels, (addrs, a_attr) = [], await _addresses(pq.name or "", pq.number or "", pq.street, notices)
        else:
            (parcels, p_hint), (addrs, a_attr) = await asyncio.gather(
                _find_parcels(pq.name or "", pq.number or "", pq.area_hint, notices, deadline),
                _addresses(pq.name or "", pq.number or "", None, notices))
        attribution = a_attr
        if parcels or addrs:
            results = [parcel_result(p) for p in _sorted_parcels(parcels)] + [address_result(a) for a in addrs]
            total = len(results)
            if parcels and p_hint:
                hint = p_hint
            elif len(parcels) > 1:
                hint = "Kilka obrębów o tej nazwie – wybierz właściwy (gmina i powiat są przy każdej pozycji)."
            elif addrs and not parcels and not pq.street:
                hint = (f"Nie znaleziono działki nr {pq.number} w obrębie „{pq.name}”, ale jest taki adres – przybliż mapę "
                        "do domu i kliknij swoje pole.")
            elif addrs and pq.street:
                hint = "To adres, nie działka – przybliż mapę do domu i kliknij swoje pole."
        else:  # nie ma takiej działki (albo ULDK niedostępne) – pokazujemy miejscowość, rolnik kliknie swoje pole
            res = await places.find(pq.name or "")
            notices += [n for n in res.notices if n not in notices]
            attribution = res.attribution
            results = [place_result(p) for p in res.places]
            total, truncated = len(results), res.truncated
            uldk_down = any(n.startswith(uldk.SOURCE) for n in notices)
            if p_hint:  # A19: gmina sprawdzona – mówimy, co sprawdziliśmy i co dopisać
                hint = p_hint + (" Pokazuję miejscowość – przybliż mapę i kliknij swoje pole." if results else "")
            elif results and uldk_down:
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
