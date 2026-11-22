"""Szukanie działki po „gmina + numer” (A19): rolnik zna gminę i numer, ale nie nazwę obrębu.

1. Obręby gminy = miejscowości z PRNG (`prng.in_gmina`, cache bez wygasania) – na wsi obręb ewidencyjny nosi zwykle nazwę
   wsi. Kolejność: najpierw nazwy podobne do reszty zapytania, potem siedziba gminy, wsie / miasta przed osadami
   i koloniami, potem alfabetycznie. Części wsi, przysiółki i części miast pomijamy (nie są obrębami).
2. ULDK „obręb numer” dla najwyżej `search_gmina_max_obreby` (10) obrębów – SEKWENCYJNIE (wspólny limit zapytań GUGiK
   i bezpiecznik ULDK z `uldk._query`), w budżecie czasu wyszukiwania; tylko działki z tej gminy.
3. Wynik (także „nic”) w cache bez wygasania – gdy wszystkie zapytania się udały; awaria ULDK = wynik częściowy bez zapisu.

Ograniczenie: obręby miejskie bywają numerowane („Obręb 12”) – tych nazw PRNG nie zna; wtedy podpowiedź „dopisz obręb”.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.cache import FOREVER, TTLCache
from app.core.config import settings
from app.core.http import NotFoundError, SourceError
from app.core.search_query import fold
from app.sources import prng, uldk

SOURCE = "Wyszukiwanie gmina + numer"
# rodzaj miejscowości w PRNG → pierwszeństwo jako kandydat na obręb (brak na liście = pomijamy)
KIND_RANK = {"wieś": 0, "miasto": 0, "osada": 1, "kolonia": 2, "osada leśna": 3}
_cache: TTLCache[dict] = TTLCache(ttl_s=None, max_items=2048, name=SOURCE)


@dataclass
class GminaSearch:
    gmina: str                            # nazwa gminy (z PRNG)
    parcels: list[uldk.Parcel] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)   # obręby sprawdzone w ULDK
    skipped: int = 0                      # obręby gminy sprawdzone wcześniej zwykłym „obręb numer” (np. o nazwie gminy)
    total: int = 0                        # ile obrębów (miejscowości – kandydatów) ma gmina
    next_name: str | None = None          # pierwszy niesprawdzony obręb (do podpowiedzi „dopisz nazwę wsi”)
    complete: bool = True                 # False – ULDK przerwało / skończył się czas
    stop_reason: str | None = None        # „czas” | „uldk”


def teryt6(code: str | None) -> str:
    return "".join(ch for ch in (code or "") if ch.isdigit())[:6]


def in_commune(p: uldk.Parcel, gmina: str, teryts: set[str]) -> bool:
    """Działka z tej gminy: TERYT (6 cyfr – bez rodzaju gminy) albo nazwa gminy z ULDK („Wronki”, „Wronki - obszar
    wiejski”)."""
    if teryts and teryt6(p.teryt_commune) in teryts:
        return True
    return fold(p.commune) == fold(gmina) or fold(p.commune).startswith(fold(gmina) + " ")


def matches_area(p: uldk.Parcel, hints: list[str]) -> bool:
    """Filtr z zapytania (gmina, powiat albo województwo) – każda wskazówka musi pasować."""
    for h in hints:
        f = fold(h)
        if not f:
            continue
        if not any(fold(x) == f or fold(x).startswith(f + " ") or fold(x).endswith(" " + f)
                   for x in (p.commune, p.county, p.voivodeship)):
            return False
    return True


def _similar(name: str, rest: str) -> int:
    r, n = fold(rest), fold(name)
    if not r:
        return 1
    if n == r:
        return 0
    if n.startswith(r) or r.startswith(n):
        return 0
    return 0 if set(r.split()) & set(n.split()) else 1


def candidates(places: list[prng.PrngPlace], gmina: str, rest: str = "") -> list[str]:
    """Nazwy obrębów do sprawdzenia, w kolejności (bez powtórzeń)."""
    best: dict[str, tuple] = {}
    for p in places:
        rank = KIND_RANK.get((p.kind or "").strip().lower())
        if rank is None or not p.name:
            continue
        key = (_similar(p.name, rest), 0 if fold(p.name) == fold(gmina) else 1, rank, fold(p.name))
        if p.name not in best or key < best[p.name]:
            best[p.name] = key
    return sorted(best, key=best.get)


async def search_gmina(gmina: str, number: str, rest: str = "", skip: set[str] | None = None,
                       deadline: float | None = None) -> GminaSearch | None:
    """Działki nr `number` w obrębach gminy `gmina`. None = to nie jest nazwa gminy (PRNG nie zna takiej gminy).
    `skip` – obręby już sprawdzone przez zwykłe „obręb numer” (np. obręb o nazwie gminy)."""
    places = await prng.in_gmina(gmina)  # SourceError → wołający (notka)
    if not places:
        return None
    names = candidates(places, gmina, rest)
    done = {fold(x) for x in (skip or set())}
    todo = [n for n in names if fold(n) not in done]
    limit = settings.search_gmina_max_obreby
    key = (fold(gmina), number, fold(rest), tuple(sorted(done)))
    hit = _cache.get(key)
    if hit is not None:
        return GminaSearch(**hit)
    teryts = {teryt6(p.teryt_gminy) for p in places if p.teryt_gminy}
    out = GminaSearch(gmina=places[0].gmina or gmina, total=len(names), skipped=len(names) - len(todo))
    uldk_down = False
    for name in todo[:limit]:  # sekwencyjnie – bez zalewania GUGiK (limit zapytań i bezpiecznik w uldk._query)
        if deadline is not None and time.monotonic() > deadline:
            out.complete, out.stop_reason = False, "czas"
            break
        try:
            found = await uldk.by_id(f"{name} {number}")
        except NotFoundError:
            found = []
        except SourceError:
            out.complete, out.stop_reason, uldk_down = False, "uldk", True
            break
        out.checked.append(name)
        seen = {x.id for x in out.parcels}
        out.parcels += [p for p in found if in_commune(p, out.gmina, teryts) and p.id not in seen]
    rest_todo = [n for n in todo if n not in out.checked]
    out.next_name = rest_todo[0] if rest_todo else None
    if out.complete:
        _cache.set(key, out.__dict__.copy(), FOREVER)
    if uldk_down and not out.checked:
        raise SourceError(uldk.SOURCE, "ewidencja działek nie odpowiada – spróbuj za chwilę")
    return out


def clear_cache() -> None:
    _cache.clear()
