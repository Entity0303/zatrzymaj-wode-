"""Wspólna warstwa cache dla wszystkich źródeł zewnętrznych (A5d, D53): pamięć procesu + trwały plik SQLite.

- `TTLCache` – jeden obiekt na źródło (przestrzeń nazw = `name`), klucz = znormalizowane parametry zapytania.
  Wpis trafia do pamięci i do SQLite (`settings.cache_db`; w Dockerze plik w wolumenie – przeżywa restart
  kontenera i reload uvicorna). Brak w pamięci → odczyt z pliku. `ttl_s=None` = bez wygasania.
- Czas zapisu = czas ścienny (UTC), więc wiek wpisu jest poprawny także po restarcie.
- Odporność (D44): wpis po TTL zostaje jeszcze `stale_max_s` (30 dni) – gdy źródło nie odpowiada, `cached_fetch`
  zwraca stary wynik z adnotacją w analizie („dane z cache z dnia X”, pewność −1 poziom).
- Bezpiecznik (D45, D54): wspólny dla źródła – po awarii (albo blokadzie ULDK) przez `breaker_s` nie odpytujemy
  źródła wcale; stan (do kiedy, dlaczego) widać w /api/status.
- DEMO_OFFLINE (D55): żadnych zapytań zewnętrznych – tylko cache (także przeterminowany); brak wpisu =
  SourceError z czytelnym komunikatem (HTTP 502 z nazwą źródła, nigdy 500).
Wartości zapisywane przez pickle – plik tworzy i czyta wyłącznie ta aplikacja.
"""

import asyncio
import datetime as dt
import logging
import math
import pickle
import sqlite3
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, Hashable, TypeVar

from app.core.config import settings
from app.core.http import NotFoundError, SourceError

log = logging.getLogger("uvicorn.error")
V = TypeVar("V")
STALE_MAX_S = 30 * 24 * 3600
FOREVER = math.inf
OFFLINE_MESSAGE = ("brak zapisanych danych dla tego miejsca (tryb pokazowy bez internetu) – wybierz jeden z przykładów "
                   "albo spróbuj później")

# nazwa źródła -> cache (do /api/status: liczba wpisów i wiek najnowszego)
REGISTRY: dict[str, list["TTLCache"]] = {}


# ── trwały magazyn (SQLite) ─────────────────────────────────────────────────────────────────


class Store:
    """Jeden plik SQLite dla wszystkich źródeł. Bezpieczny dla wątków (blokada) i kilku procesów (WAL)."""

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._con = sqlite3.connect(path, check_same_thread=False, timeout=10)
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.execute("PRAGMA synchronous=NORMAL")
            self._con.execute(
                "CREATE TABLE IF NOT EXISTS cache (ns TEXT NOT NULL, k TEXT NOT NULL, stored_at REAL NOT NULL, "
                "ttl_s REAL, value BLOB NOT NULL, PRIMARY KEY (ns, k))"
            )
            self._con.commit()

    def get(self, ns: str, k: str) -> tuple[float, float, bytes] | None:
        with self._lock:
            row = self._con.execute("SELECT stored_at, ttl_s, value FROM cache WHERE ns=? AND k=?", (ns, k)).fetchone()
        if row is None:
            return None
        return row[0], FOREVER if row[1] is None else row[1], row[2]

    def put(self, ns: str, k: str, stored_at: float, ttl_s: float, value: bytes) -> None:
        with self._lock:
            self._con.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?)",
                              (ns, k, stored_at, None if math.isinf(ttl_s) else ttl_s, value))
            self._con.commit()

    def delete(self, ns: str, k: str | None = None) -> None:
        with self._lock:
            if k is None:
                self._con.execute("DELETE FROM cache WHERE ns=?", (ns,))
            else:
                self._con.execute("DELETE FROM cache WHERE ns=? AND k=?", (ns, k))
            self._con.commit()

    def shift(self, ns: str, seconds: float) -> None:
        with self._lock:
            self._con.execute("UPDATE cache SET stored_at = stored_at - ? WHERE ns=?", (seconds, ns))
            self._con.commit()

    def rows(self, ns: str) -> list[tuple[str, float, float, bytes]]:
        with self._lock:
            out = self._con.execute("SELECT k, stored_at, ttl_s, value FROM cache WHERE ns=?", (ns,)).fetchall()
        return [(k, s, FOREVER if t is None else t, v) for k, s, t, v in out]

    def keys(self, ns: str) -> list[str]:
        """P1: same klucze (bez wczytywania wartości) – np. szukanie zapisanej serii pogody obejmującej zakres."""
        with self._lock:
            return [r[0] for r in self._con.execute("SELECT k FROM cache WHERE ns=?", (ns,)).fetchall()]

    def stats(self, ns: str) -> tuple[int, float | None]:
        with self._lock:
            n, newest = self._con.execute("SELECT COUNT(*), MAX(stored_at) FROM cache WHERE ns=?", (ns,)).fetchone()
        return n, newest

    def close(self) -> None:
        with self._lock:
            self._con.close()


_store: Store | None = None
_store_path: str | None = None


def store() -> Store | None:
    """Magazyn z `settings.cache_db` (pusty = tylko pamięć, np. w testach). Zmiana ustawienia = nowy plik."""
    global _store, _store_path
    path = settings.cache_db or None
    if path != _store_path:
        if _store is not None:
            _store.close()
        try:
            _store = Store(path) if path else None
        except (sqlite3.Error, OSError) as exc:  # plik niedostępny – aplikacja działa dalej na samej pamięci
            log.warning("Trwały cache %s niedostępny (%s) – cache tylko w pamięci procesu", path, exc)
            _store = None
        _store_path = path
        for caches in REGISTRY.values():  # pamięć odpowiada innemu plikowi – czyścimy
            for c in caches:
                c._data.clear()
    return _store


# ── seed: gotowy cache w obrazie (A13, hosting bez trwałego dysku) ──────────────────────────

SEED_FILE = Path(__file__).parents[1] / "data" / "seed" / "cache_seed.sqlite.gz"
# przestrzenie, które nie trafiają do seeda – wygasają w ciągu godziny (prognoza, bieżące stany wód)
SEED_EXCLUDE = ("Open-Meteo", "IMGW-PIB (stany wód)")


def load_seed(seed_file: Path | None = None) -> int:
    """Gdy trwały cache jest pusty (np. Render Free po uśpieniu) – wczytuje seed z obrazu (`INSERT OR IGNORE`, wpis
    z wolumenu zawsze wygrywa). Zwraca liczbę wczytanych wpisów; brak seeda / pliku cache = 0."""
    import gzip
    import shutil
    import tempfile

    st = store()
    seed = seed_file or SEED_FILE
    if st is None or not settings.cache_seed or not seed.exists():
        return 0
    with st._lock:
        n = st._con.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    if n:
        return 0
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        with gzip.open(seed, "rb") as src:
            shutil.copyfileobj(src, tmp)
        tmp_path = tmp.name
    try:
        with st._lock:
            st._con.execute("ATTACH DATABASE ? AS seed", (tmp_path,))
            st._con.execute("INSERT OR IGNORE INTO cache SELECT ns, k, stored_at, ttl_s, value FROM seed.cache")
            st._con.commit()
            st._con.execute("DETACH DATABASE seed")
            loaded = st._con.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    log.info("Cache pusty – wczytano seed %s: %d wpisów", seed.name, loaded)
    return loaded


# ── bezpiecznik (wspólny dla źródła) ────────────────────────────────────────────────────────


@dataclass
class BreakerState:
    until: float = 0.0  # czas ścienny (time.time())
    reason: str = ""
    failures: list[float] = field(default_factory=list)  # P1: chwile błędów w oknie (próg `breaker_after`)
    probing: bool = False  # P1: po otwarciu – następne zapytanie jest próbne; błąd = od razu znowu otwarty

    @property
    def open(self) -> bool:
        return self.until > time.time()

    @property
    def until_local(self) -> dt.datetime:
        """Czas polski (kontener działa w UTC)."""
        try:
            from zoneinfo import ZoneInfo

            return dt.datetime.fromtimestamp(self.until, ZoneInfo("Europe/Warsaw"))
        except Exception:  # noqa: BLE001 – brak bazy stref czasowych
            return dt.datetime.fromtimestamp(self.until).astimezone()


BREAKERS: dict[str, BreakerState] = {}


def breaker(source: str) -> BreakerState:
    return BREAKERS.setdefault(source, BreakerState())


def trip(source: str, seconds: float, reason: str, after: int = 1, window_s: float = 60.0) -> None:
    """Otwarcie bezpiecznika na `seconds`. P1: `after` > 1 – dopiero po tylu błędach w `window_s` (np. ULDK: 5 w 60 s);
    błąd próbnego zapytania po zamknięciu – od razu znowu otwarty."""
    b = breaker(source)
    if b.open:
        return
    now = time.time()
    b.failures = [t for t in b.failures if now - t <= window_s] + [now]
    if after <= 1 or b.probing or len(b.failures) >= after:
        b.until, b.reason, b.probing = now + seconds, reason, after > 1
        b.failures = []


def breaker_ok(source: str) -> None:
    """P1: udane zapytanie – licznik błędów od zera, bezpiecznik zamknięty na dobre."""
    b = BREAKERS.get(source)
    if b is not None and (b.failures or b.probing):
        b.failures, b.probing = [], False


def breaker_line(source: str) -> str:
    """P1: stan bezpiecznika do logu – „otwarty do 12:03:15” / „zamknięty (błędy 2 w 60 s)”."""
    b = BREAKERS.get(source)
    if b is None:
        return "zamknięty"
    if b.open:
        return f"otwarty do {dt.datetime.fromtimestamp(b.until):%H:%M:%S}"
    return f"zamknięty (błędy {len(b.failures)} w oknie{', po próbie' if b.probing else ''})"


# ── cache źródła ────────────────────────────────────────────────────────────────────────────


@dataclass
class _Entry(Generic[V]):
    stored_at: float  # time.time()
    ttl_s: float  # FOREVER = bez wygasania
    value: V


def _k(key: Hashable) -> str:
    return repr(key)


class TTLCache(Generic[V]):
    def __init__(self, ttl_s: float | None, max_items: int = 512, name: str | None = None,
                 stale_max_s: float = STALE_MAX_S):
        self.ttl_s = FOREVER if ttl_s is None else ttl_s
        self.max_items = max_items
        self.stale_max_s = stale_max_s
        self.name = name or f"cache-{id(self)}"
        self._data: OrderedDict[str, _Entry[V]] = OrderedDict()
        REGISTRY.setdefault(self.name, []).append(self)

    @property
    def ns(self) -> str:
        return self.name

    # zgodność z kodem sprzed A5d: bezpiecznik jest teraz wspólny dla źródła (`breaker(name)`)
    @property
    def down_until(self) -> float:
        return breaker(self.name).until

    @staticmethod
    def _age(e: _Entry) -> float:
        return time.time() - e.stored_at

    def _entry(self, key: Hashable) -> _Entry[V] | None:
        k = _k(key)
        e = self._data.get(k)
        if e is None and (st := store()) is not None:
            row = st.get(self.ns, k)
            if row is not None:
                try:
                    e = _Entry(row[0], row[1], pickle.loads(row[2]))
                except Exception:  # noqa: BLE001 – zmieniona klasa / uszkodzony wpis = brak wpisu
                    st.delete(self.ns, k)
                    return None
                self._remember(k, e)
        if e is not None and self._age(e) >= e.ttl_s + self.stale_max_s:
            self._data.pop(k, None)
            if (st := store()) is not None:
                st.delete(self.ns, k)
            return None
        return e

    def _remember(self, k: str, e: _Entry[V]) -> None:
        self._data[k] = e
        self._data.move_to_end(k)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)  # z pamięci; w pliku zostaje

    def get(self, key: Hashable) -> V | None:
        """Tylko wpis w terminie ważności."""
        e = self._entry(key)
        return e.value if e is not None and self._age(e) < e.ttl_s else None

    def get_stale(self, key: Hashable) -> tuple[V, dt.datetime] | None:
        """Wpis także po terminie ważności (do `stale_max_s`) – z datą zapisu."""
        e = self._entry(key)
        if e is None:
            return None
        return e.value, dt.datetime.fromtimestamp(e.stored_at, dt.timezone.utc)

    def set(self, key: Hashable, value: V, ttl_s: float | None = None) -> None:
        ttl = self.ttl_s if ttl_s is None else ttl_s
        e = _Entry(time.time(), ttl, value)
        k = _k(key)
        self._remember(k, e)
        if (st := store()) is not None:
            st.put(self.ns, k, e.stored_at, ttl, pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))

    def keys(self) -> list[str]:
        """P1: klucze wpisów (pamięć + plik) jako tekst `repr(klucz)`, bez wczytywania wartości."""
        out = list(self._data.keys())
        if (st := store()) is not None:
            seen = set(out)
            out += [k for k in st.keys(self.ns) if k not in seen]
        return out

    def values(self) -> Iterator[V]:
        """Wszystkie wpisy (pamięć + plik) – np. indeks znanych działek ULDK."""
        seen = set()
        for k, e in list(self._data.items()):
            seen.add(k)
            yield e.value
        if (st := store()) is not None:
            for k, _s, _t, blob in st.rows(self.ns):
                if k in seen:
                    continue
                try:
                    yield pickle.loads(blob)
                except Exception:  # noqa: BLE001
                    continue

    def drop_memory(self) -> None:
        """Testy: symulacja restartu procesu – pamięć pusta, plik zostaje."""
        self._data.clear()

    def expire_all(self) -> None:
        """Testy: wszystkie wpisy przeterminowane (zostają jako „stare”) – także te bez wygasania."""
        for e in self._data.values():
            if math.isinf(e.ttl_s):
                e.ttl_s = 1.0
            e.stored_at -= e.ttl_s + 1
        if (st := store()) is not None:
            for k, s, t, v in st.rows(self.ns):
                t = 1.0 if math.isinf(t) else t
                st.put(self.ns, k, s - t - 1, t, v)

    def newest_age_s(self) -> float | None:
        ages = [self._age(e) for e in self._data.values()]
        if (st := store()) is not None:
            _n, newest = st.stats(self.ns)
            if newest is not None:
                ages.append(time.time() - newest)
        return min(ages, default=None)

    def count(self) -> int:
        st = store()
        return st.stats(self.ns)[0] if st is not None else len(self._data)

    def clear(self) -> None:
        self._data.clear()
        if (st := store()) is not None:
            st.delete(self.ns)
        BREAKERS.pop(self.name, None)

    def __len__(self) -> int:
        return self.count()


def cache_stats(name: str) -> tuple[int, float | None]:
    """(liczba wpisów, wiek najnowszego w s) dla źródła o tej nazwie."""
    caches = REGISTRY.get(name, [])
    ages = [a for c in caches if (a := c.newest_age_s()) is not None]
    return sum(c.count() for c in caches), (min(ages) if ages else None)


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


def offline(source: str | None = None) -> bool:
    """Tryb demo offline (wszystko z cache) albo – gdy podano źródło – to źródło wyłączone w OFFLINE_SOURCES (D89)."""
    from app.core.http import source_offline

    return bool(settings.demo_offline) or source_offline(source)


def offline_message(source: str | None = None) -> str:
    from app.core.http import SOURCE_OFF_MESSAGE

    return OFFLINE_MESSAGE if settings.demo_offline else (
        f"brak zapisanych danych dla tego miejsca ({SOURCE_OFF_MESSAGE}) – wybierz jeden z przykładów albo spróbuj później")


async def cached_fetch(
    cache: TTLCache[V], key: Hashable, source: str, fetch: Callable[[], Awaitable[V]], ttl_s: float | None = None,
    timeout_s: float | None = None,
    breaker_s: float | None = None,
    breaker_after: int = 1,
    breaker_window_s: float = 60.0,
) -> V:
    """Świeży wpis z cache → (tryb offline: stary wpis albo czytelny błąd) → bezpiecznik → zapytanie do źródła
    (z łącznym limitem `timeout_s`) → przy błędzie lub przekroczeniu czasu przeterminowany wpis (z adnotacją)."""
    hit = cache.get(key)
    if hit is not None:
        return hit
    if offline(source) or offline(cache.name):
        stale = cache.get_stale(key)
        if stale is None:
            raise SourceError(source, offline_message(source))
        return stale[0]  # w trybie demo offline stary wpis to zamierzone użycie, nie awaria
    try:
        b = breaker(cache.name)
        if b.open:  # bezpiecznik: źródło niedawno zawiodło – nie odpytujemy go ponownie
            left = b.until - time.time()
            when = f"za ok. {max(1, round(left / 60))} min" if left >= 60 else f"za {max(1, round(left))} s"
            raise SourceError(source, f"{b.reason} (ponowna próba {when})")
        try:
            value = await (asyncio.wait_for(fetch(), timeout_s) if timeout_s else fetch())
        except asyncio.TimeoutError as exc:
            raise SourceError(source, f"brak odpowiedzi w {timeout_s:.0f} s") from exc
    except NotFoundError:
        raise
    except SourceError as exc:
        if breaker_s:
            trip(cache.name, breaker_s, exc.message, breaker_after, breaker_window_s)
        stale = cache.get_stale(key)
        if stale is None:
            raise
        value, stored_at = stale
        note_stale(source, stored_at, exc.message)
        return value
    if breaker_after > 1:
        breaker_ok(cache.name)
    cache.set(key, value, ttl_s)
    return value
