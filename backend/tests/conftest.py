"""Wspólne ustawienia testów: bez sieci, bez rozgrzewki przykładów demo przy starcie aplikacji, cache tylko w pamięci
(trwały plik SQLite – tylko w testach, które go jawnie włączają), bez wczytywania działek demo do indeksu ULDK."""

import os

os.environ["DEMO_WARMUP"] = "false"
os.environ["CACHE_DB"] = ""
os.environ["DEMO_OFFLINE"] = "false"

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402

settings.demo_warmup = False
settings.cache_db = ""
settings.demo_offline = False
settings.demo_parcels_preload = False
settings.uldk_retry_delays_s = [0.0, 0.0]


@pytest.fixture(autouse=True)
def _isolated_caches():
    """Każdy test zaczyna z pustym cache wszystkich źródeł i zamkniętymi bezpiecznikami."""
    from app.core import cache
    from app.sources import uldk

    def reset():
        for caches in cache.REGISTRY.values():
            for c in caches:
                c.drop_memory()
        cache.BREAKERS.clear()
        uldk._known.clear()
        uldk._known_loaded = False

    saved = (settings.cache_db, settings.demo_offline, settings.demo_parcels_preload)
    reset()
    yield
    settings.cache_db, settings.demo_offline, settings.demo_parcels_preload = saved
    cache.store()  # wróć do magazynu z ustawień (pamięć)
    reset()
