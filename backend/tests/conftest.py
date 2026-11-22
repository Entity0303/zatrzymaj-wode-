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
settings.terrain_saved_results = False  # zapisane wyniki terenu (app/data/terrain) – tylko w testach A6, jawnie
settings.uldk_retry_delays_s = [0.0, 0.0]
settings.nmt_retry_delay_s = 0.0
settings.sentinel_background = False  # A11: bez liczenia satelity w tle w testach
settings.sentinel_enabled = False  # A11: Earth Search tylko w testach, które go jawnie włączają (respx)
settings.offline_sources = ""  # A8 (D89): w testach żadne źródło nie jest wyłączone (mocki respx)
settings.search_addresses = False  # A9: stare testy wyszukiwania – bez UUG / Nominatim (nowe włączają jawnie)
settings.hydro_background = False  # A9: bez Overpass / IMGW w tle w testach
settings.terrain_background = False  # A9: stare testy – teren liczony w analizie (nowe włączają tło jawnie)
settings.gugik_min_interval_s = 0.0  # A8 (D89): bez odstępów między zapytaniami do (mockowanego) GUGiK
settings.imgw_enabled = False  # A7: magazyn IMGW tylko w testach, które go jawnie włączają
settings.prng_min_interval_s = 0.0  # A5c: bez odstępów między zapytaniami do geokoderów w testach
settings.prng_retry_delay_s = 0.0
settings.nominatim_min_interval_s = 0.0


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

    from app.analysis import terrain

    terrain.clear_memo()
    saved = (settings.cache_db, settings.demo_offline, settings.demo_parcels_preload, settings.terrain_saved_results)
    saved_imgw = (settings.imgw_enabled, settings.imgw_store, settings.sentinel_enabled)
    reset()
    yield
    settings.cache_db, settings.demo_offline, settings.demo_parcels_preload, settings.terrain_saved_results = saved
    settings.imgw_enabled, settings.imgw_store, settings.sentinel_enabled = saved_imgw
    cache.store()  # wróć do magazynu z ustawień (pamięć)
    reset()
