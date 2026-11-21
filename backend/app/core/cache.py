"""Cache w pamięci z czasem ważności (TTL) – wspólny dla źródeł danych.

Źródła publiczne bywają wolne i mają limity zapytań, dlatego każde źródło trzyma ostatnie odpowiedzi
przez określony czas (TTL można ustawić osobno dla wpisu, np. dane historyczne 7 dni, bieżące 6 h).

Odporność (D44): wpis po upływie TTL nie znika od razu – zostaje do `stale_max_s` (30 dni). Gdy źródło
nie odpowiada, `cached_fetch` zwraca przeterminowany wynik i zapisuje w bieżącej analizie
„dane z cache z dnia X” (`stale_scope` / `stale_hits`) – pewność wyniku spada wtedy o jeden poziom.
TODO: trwały cache w SQLite (CLAUDE.md – Stack).
"""

import asyncio
import datetime as dt
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Generic, Hashable, TypeVar

from app.core.http import NotFoundError, SourceError

V = TypeVar("V")
STALE_MAX_S = 30 * 24 * 3600

# nazwa źródła -> cache (do /api/status: liczba wpisów i wiek najnowszego)
REGISTRY: dict[str, list["TTLCache"]] = {}


@dataclass
class _Entry(Generic[V]):
    stored_mono: float
    stored_at: dt.datetime
    ttl_s: float
    value: V


class TTLCache(Generic[V]):
    def __init__(self, ttl_s: float, max_items: int = 512, name: str | None = None, stale_max_s: float = STALE_MAX_S):
        self.ttl_s = ttl_s
        self.max_items = max_items
        self.stale_max_s = stale_max_s
        self.name = name
        self._data: OrderedDict[Hashable, _Entry[V]] = OrderedDict()
        if name:
            REGISTRY.setdefault(name, []).append(self)

    def _age(self, e: _Entry[V]) -> float:
        return time.monotonic() - e.stored_mono

    def get(self, key: Hashable) -> V | None:
        """Tylko wpis w terminie ważności."""
        e = self._data.get(key)
        if e is None:
            return None
        age = self._age(e)
        if age >= max(e.ttl_s, self.stale_max_s):
            del self._data[key]
            return None
        return e.value if age < e.ttl_s else None

    def get_stale(self, key: Hashable) -> tuple[V, dt.datetime] | None:
        """Wpis także po terminie ważności (do `stale_max_s`) – z datą zapisu."""
        e = self._data.get(key)
        if e is None or self._age(e) >= max(e.ttl_s, self.stale_max_s):
            return None
        return e.value, e.stored_at

    def set(self, key: Hashable, value: V, ttl_s: float | None = None) -> None:
        self._data[key] = _Entry(time.monotonic(), dt.datetime.now(dt.timezone.utc), ttl_s or self.ttl_s, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)  # najstarszy wpis

    def expire_all(self) -> None:
        """Testy: wszystkie wpisy przeterminowane (zostają jako „stare”)."""
        for e in self._data.values():
            e.stored_mono -= e.ttl_s + 1

    def newest_age_s(self) -> float | None:
        return min((self._age(e) for e in self._data.values()), default=None)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


def cache_stats(name: str) -> tuple[int, float | None]:
    """(liczba wpisów, wiek najnowszego w s) dla źródła o tej nazwie."""
    caches = REGISTRY.get(name, [])
    ages = [a for c in caches if (a := c.newest_age_s()) is not None]
    return sum(len(c) for c in caches), (min(ages) if ages else None)


# ── przeterminowane dane w bieżącej analizie ────────────────────────────────────────────────


@dataclass(frozen=True)
class StaleHit:
    source: str
    stored_at: dt.datetime
    reason: str


_stale: ContextVar[list[StaleHit] | None] = ContextVar("stale_hits", default=None)


@contextmanager
def stale_scope() -> Iterator[list[StaleHit]]:
    """Zbiera użycia przeterminowanego cache w obrębie jednej analizy (także w zadaniach asyncio.gather)."""
    hits: list[StaleHit] = []
    token = _stale.set(hits)
    try:
        yield hits
    finally:
        _stale.reset(token)


def note_stale(source: str, stored_at: dt.datetime, reason: str) -> None:
    hits = _stale.get()
    if hits is not None and not any(h.source == source for h in hits):
        hits.append(StaleHit(source, stored_at, reason))


async def cached_fetch(
    cache: TTLCache[V], key: Hashable, source: str, fetch: Callable[[], Awaitable[V]], ttl_s: float | None = None,
    timeout_s: float | None = None,
) -> V:
    """Świeży wpis z cache → zapytanie do źródła (z łącznym limitem `timeout_s`) → przy błędzie lub przekroczeniu
    czasu przeterminowany wpis (z adnotacją)."""
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        try:
            value = await (asyncio.wait_for(fetch(), timeout_s) if timeout_s else fetch())
        except asyncio.TimeoutError as exc:
            raise SourceError(source, f"brak odpowiedzi w {timeout_s:.0f} s") from exc
    except NotFoundError:
        raise
    except SourceError as exc:
        stale = cache.get_stale(key)
        if stale is None:
            raise
        value, stored_at = stale
        note_stale(source, stored_at, exc.message)
        return value
    cache.set(key, value, ttl_s)
    return value
