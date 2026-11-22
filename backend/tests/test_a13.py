"""A13 – hosting: seed cache w obrazie (wczytywany do pustego cache), CORS z regexem, lekki /api/health."""

import gzip
import pickle
import shutil
import sqlite3

from fastapi.testclient import TestClient

from app.core import cache
from app.core.config import settings
from app.main import app


def make_seed(tmp_path, rows):
    db = tmp_path / "seed.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE cache (ns TEXT NOT NULL, k TEXT NOT NULL, stored_at REAL NOT NULL, ttl_s REAL, "
              "value BLOB NOT NULL, PRIMARY KEY (ns, k))")
    c.executemany("INSERT INTO cache VALUES (?,?,?,?,?)", rows)
    c.commit()
    c.close()
    gz = tmp_path / "cache_seed.sqlite.gz"
    with open(db, "rb") as f, gzip.open(gz, "wb") as g:
        shutil.copyfileobj(f, g)
    return gz


def test_seed_loaded_only_into_empty_cache(tmp_path):
    gz = make_seed(tmp_path, [("ULDK GUGiK", "k1", 1.0, None, pickle.dumps(["działka"])),
                              ("NASA POWER", "k2", 2.0, None, pickle.dumps({"a": 1}))])
    settings.cache_db = str(tmp_path / "c.sqlite")
    assert cache.load_seed(gz) == 2
    st = cache.store()
    assert st.get("ULDK GUGiK", "k1")[2] == pickle.dumps(["działka"])
    st.put("NASA POWER", "k3", 3.0, cache.FOREVER, pickle.dumps(1))
    assert cache.load_seed(gz) == 0  # cache nie jest pusty – seed nie nadpisuje wolumenu


def test_seed_skipped_without_store_or_disabled(tmp_path, monkeypatch):
    gz = make_seed(tmp_path, [("ULDK GUGiK", "k1", 1.0, None, pickle.dumps(1))])
    settings.cache_db = ""
    assert cache.load_seed(gz) == 0
    settings.cache_db = str(tmp_path / "c2.sqlite")
    monkeypatch.setattr(settings, "cache_seed", False)
    assert cache.load_seed(gz) == 0
    assert cache.load_seed(tmp_path / "nie-ma.gz") == 0


def test_health_is_light_and_cors_regex_setting_exists():
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}
    assert settings.cors_origin_regex == "" and "http://localhost:5173" in settings.cors_origins


def test_seed_exclude_lists_short_lived_sources():
    assert "Open-Meteo" in cache.SEED_EXCLUDE and "IMGW-PIB (stany wód)" in cache.SEED_EXCLUDE
