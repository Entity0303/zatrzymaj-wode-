"""A5d – odporność demo (bez sieci): trwały cache SQLite, działki z cache i z repo, blokada ULDK i bezpiecznik,
tryb DEMO_OFFLINE i pełna ścieżka demo z samego cache."""

import asyncio
import datetime as dt
import io
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pypdf import PdfReader
from shapely import wkt

from app import demo
from app.core import cache
from app.core.cache import BREAKERS, FOREVER, TTLCache, breaker, cached_fetch, store, trip
from app.core.config import settings
from app.core.geo import to_wgs84
from app.core.http import NotFoundError, SourceError
from app.main import app
from app.sources import uldk, weather_openmeteo
from test_a5 import mock_all
from test_analysis import ULDK_ONE, WKT_201305
from test_demo_status_report import png_1x1

PID = "201305_2.0038.6/1"
HTML_BLOCK = "<!DOCTYPE html><html><body>Przekroczono limit</body></html>"


@pytest.fixture
def db(tmp_path):
    settings.cache_db = str(tmp_path / "cache.sqlite")
    store()
    yield settings.cache_db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def restart() -> None:
    """Symulacja restartu procesu: pamięć wszystkich cache pusta, indeks działek pusty – plik SQLite zostaje."""
    for caches in cache.REGISTRY.values():
        for c in caches:
            c.drop_memory()
    BREAKERS.clear()
    uldk._known.clear()
    uldk._known_loaded = False


# ── 0. trwały cache ─────────────────────────────────────────────────────────────────────────


def test_cache_write_read_and_survives_restart(db):
    c1: TTLCache[dict] = TTLCache(ttl_s=None, name="test-trwaly")
    c1.set(("a", 1.5), {"x": [1, 2]})
    assert c1.get(("a", 1.5)) == {"x": [1, 2]}
    c1.drop_memory()
    c2: TTLCache[dict] = TTLCache(ttl_s=None, name="test-trwaly")  # nowa instancja na tym samym pliku
    assert c2.get(("a", 1.5)) == {"x": [1, 2]} and c2.count() == 1
    assert store().get("test-trwaly", repr(("a", 1.5)))[1] == FOREVER


def test_forecast_ttl_one_hour_and_stale_after(db):
    assert settings.cache_ttl_forecast_s == 3600 and weather_openmeteo._cache.ttl_s == 3600
    c: TTLCache[int] = TTLCache(ttl_s=3600, name="test-prognoza")
    c.set("k", 7)
    store().shift("test-prognoza", 3601)  # wpis sprzed ponad godziny (także po restarcie – czas ścienny)
    c.drop_memory()
    assert c.get("k") is None and c.get_stale("k")[0] == 7


def test_history_weather_never_expires():
    from app.sources.weather_power import ttl_for

    assert ttl_for(dt.date(2018, 6, 9)) == FOREVER
    assert ttl_for(__import__("app.core.clock", fromlist=["today_pl"]).today_pl() - dt.timedelta(days=1)) == settings.cache_ttl_current_s


def test_persistent_entry_used_when_source_down(db):
    c: TTLCache[int] = TTLCache(ttl_s=60, name="test-zapas")
    c.set("k", 1)
    store().shift("test-zapas", 120)
    c.drop_memory()

    async def boom():
        raise SourceError("X", "nie działa")

    assert asyncio.run(cached_fetch(c, "k", "X", boom)) == 1  # stary wpis z pliku zamiast błędu


# ── 1. działki: zero zbędnych zapytań do ULDK ───────────────────────────────────────────────


@respx.mock
def test_parcel_cached_by_id_and_by_point(db):
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    p = asyncio.run(uldk.by_id(PID))[0]
    assert route.call_count == 1
    restart()  # po restarcie – z pliku, bez ULDK
    assert asyncio.run(uldk.by_id(PID))[0].id == PID and route.call_count == 1
    pt = p.geom_4326.representative_point()
    assert asyncio.run(uldk.by_point(pt.x, pt.y)).id == PID and route.call_count == 1  # punkt w znanej działce
    asyncio.run(uldk.by_point(14.5, 53.4))  # punkt poza znanymi działkami – dopiero teraz ULDK
    assert route.call_count == 2


@respx.mock
def test_demo_parcels_preloaded_without_network(client):
    settings.demo_parcels_preload = True
    uldk.load_known(force=True)  # jak przy starcie aplikacji z DEMO_PARCELS_PRELOAD
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(503))
    r = client.get("/api/parcel", params={"id": PID})
    assert r.status_code == 200 and r.json()["obreb"] == "Wnory-Wandy" and r.json()["numer"] == "6/1"
    assert not route.called
    flagged = [d for d in uldk.demo_parcels() if d.get("needs_fetch")]
    assert all(not d.get("geom_wkt_2180") for d in flagged)
    ids = {d.get("id") for d in uldk.demo_parcels()}
    assert {e.parcel_id for e in demo.EXAMPLES} <= ids  # wszystkie działki z /api/demo/examples są na liście


@respx.mock
def test_region_number_falls_back_to_known_parcel_when_uldk_blocked():
    uldk.remember(uldk.parse_response(ULDK_ONE))
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(302, headers={"location": "https://x/resp/uldk.php"}))
    assert asyncio.run(uldk.by_id("Wnory-Wandy 6/1"))[0].id == PID


# ── 3. blokada ULDK i bezpiecznik ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("resp", [
    httpx.Response(302, headers={"location": "https://integracja01.gugik.gov.pl/resp/uldk.php"}),
    httpx.Response(429),
    httpx.Response(200, text=HTML_BLOCK, headers={"content-type": "text/html"}),
], ids=["302", "429", "html"])
@respx.mock
def test_uldk_block_retries_twice_then_breaker(resp):
    route = respx.get(settings.uldk_url).mock(return_value=resp)
    with pytest.raises(SourceError) as e:
        asyncio.run(uldk.by_id("061704_2.0011.383/2"))
    assert not isinstance(e.value, NotFoundError) and "ogranicza" in e.value.message or "HTML" in e.value.message
    assert route.call_count == 3  # pierwsze zapytanie + 2 ponowienia (1 s, 3 s)
    b = breaker(uldk.SOURCE)
    assert not b.open  # P1: jeden błąd nie otwiera bezpiecznika ULDK (dopiero 5 w 60 s)
    for k in range(4):  # kolejne 4 nieudane zapytania (inne działki) → 5 błędów w oknie → otwarty na 30 s
        with pytest.raises(SourceError):
            asyncio.run(uldk.by_id(f"061704_2.0011.38{k}/9"))
    assert b.open and 25 <= b.until - time.time() <= 30
    n = route.call_count
    with pytest.raises(SourceError) as e2:  # otwarty: bez zapytań
        asyncio.run(uldk.by_id("143203_2.0027.112/11"))
    assert route.call_count == n and "ponowna próba" in e2.value.message
    b.until = time.time() - 1  # po 30 s – próbne zapytanie
    route.mock(return_value=httpx.Response(200, text=ULDK_ONE))
    assert asyncio.run(uldk.by_id(PID))[0].id == PID and route.call_count == n + 1
    assert not b.probing and not b.failures  # udane – zamknięty na dobre


def test_retry_delays_are_1_and_3_seconds_by_default():
    from app.core.config import Settings

    s = Settings()
    assert s.uldk_retry_delays_s == [1.0, 3.0] and s.uldk_breaker_s == 30.0  # P1: próbne zamknięcie po 30 s
    assert s.uldk_breaker_failures == 5 and s.uldk_breaker_window_s == 60.0 and s.uldk_retry_timeout_s == 15.0


@respx.mock
def test_status_shows_uldk_limited_until_and_does_not_query_it(client):
    uldk_route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text="0\n"))
    for u in (settings.nasa_power_url, settings.open_meteo_forecast_url, settings.iung_wms_url, settings.kieg_url,
              settings.soilgrids_url, settings.soil_map_url, settings.nmt_url):
        respx.get(u).mock(return_value=httpx.Response(200, text="{}"))
    trip(uldk.SOURCE, 60, "usługa chwilowo ogranicza ruch (przekierowanie)")
    s = next(x for x in client.get("/api/status").json()["services"] if x["name"] == "ULDK GUGiK")
    until = breaker(uldk.SOURCE).until_local
    assert not s["ok"] and s["error"].startswith(f"ograniczony (do {until:%H:%M})")
    assert not uldk_route.called


@respx.mock
def test_status_probe_detects_uldk_block_and_trips_breaker(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=HTML_BLOCK))
    for u in (settings.nasa_power_url, settings.open_meteo_forecast_url, settings.iung_wms_url, settings.kieg_url,
              settings.soilgrids_url, settings.soil_map_url, settings.nmt_url):
        respx.get(u).mock(return_value=httpx.Response(200, text="{}"))
    s = next(x for x in client.get("/api/status").json()["services"] if x["name"] == "ULDK GUGiK")
    assert not s["ok"] and s["error"].startswith("ograniczony (do ") and breaker(uldk.SOURCE).open


@respx.mock
def test_warmup_does_not_query_uldk_for_known_parcels():
    settings.demo_parcels_preload = True
    routes = mock_all()
    routes["uldk"].mock(return_value=httpx.Response(302, headers={"location": "https://x/resp/uldk.php"}))
    respx.get(settings.open_meteo_forecast_url).mock(return_value=httpx.Response(503))  # A8: przykłady „na dziś”
    asyncio.run(demo.warmup_once())
    states = {k: w.state for k, w in demo._state.items()}
    assert states["dobra-dzialka"] == "gotowe" and states["slaba-ziemia"] == "gotowe"
    # ULDK pytane tylko o działki spoza cache (061704, 143203) – i to najwyżej raz z ponowieniami, potem bezpiecznik
    asked = {c.request.url.params.get("id") for c in routes["uldk"].calls}
    assert PID not in asked and routes["uldk"].call_count <= 3


# ── 4. DEMO_OFFLINE ─────────────────────────────────────────────────────────────────────────


@respx.mock
def test_offline_missing_data_is_clear_502_not_500(client):
    settings.demo_offline = True
    routes = mock_all()
    r = client.get("/api/analysis", params={"parcel_id": "061704_2.0011.383/2"})
    assert r.status_code == 502 and "tryb pokazowy bez internetu" in r.json()["detail"]["message"]
    r = client.get("/api/report.pdf", params={"parcel_id": "061704_2.0011.383/2"})
    assert r.status_code == 502
    assert not any(rt.called for rt in routes.values())  # ani jednego zapytania zewnętrznego


@respx.mock
def test_offline_status_without_probes(client):
    settings.demo_offline = True
    route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, text="{}"))
    services = client.get("/api/status").json()["services"]
    assert all("tryb demo offline" in s["error"] for s in services) and not route.called


@respx.mock
def test_demo_path_from_cache_only(db, client):
    """Ścieżka demo: rozgrzanie (z „siecią” = mocki) → restart → DEMO_OFFLINE → wyszukanie (id, obręb+numer,
    punkt) → analiza bez uprawy → analiza z uprawą → PDF – bez ani jednego zapytania zewnętrznego."""
    routes = mock_all()
    routes["ortho"] = respx.get(settings.ortho_wms_url).mock(
        return_value=httpx.Response(200, content=png_1x1(), headers={"content-type": "image/png"}))
    q_crop = {"parcel_id": PID, "crop": "zboza_ozime", "date": "2018-06-10", "previous_crop": "zboza_ozime"}
    q_none = {"parcel_id": PID, "date": "2018-06-10"}
    online = {k: client.get("/api/analysis", params=q).json() for k, q in (("crop", q_crop), ("none", q_none))}
    for q in (q_crop, q_none):
        assert client.get("/api/report.pdf", params=q).status_code == 200
    calls = {k: r.call_count for k, r in routes.items()}

    restart()
    settings.demo_offline = True
    pt = to_wgs84(wkt.loads(WKT_201305)).representative_point()
    t0 = time.perf_counter()
    for params in ({"id": PID}, {"id": "Wnory-Wandy 6/1"}, {"lon": pt.x, "lat": pt.y}):
        r = client.get("/api/parcel", params=params)
        assert r.status_code == 200 and r.json()["id"] == PID, (params, r.text)
    a_none = client.get("/api/analysis", params=q_none)
    a_crop = client.get("/api/analysis", params=q_crop)
    pdf = client.get("/api/report.pdf", params=q_crop)
    pdf_none = client.get("/api/report.pdf", params=q_none)
    elapsed = time.perf_counter() - t0
    assert a_none.status_code == 200 and a_crop.status_code == 200, (a_none.text, a_crop.text)
    assert a_crop.json()["status"] == online["crop"]["status"] and a_none.json()["status"] == online["none"]["status"]
    assert a_crop.json()["field_state"]["series"] == online["crop"]["field_state"]["series"]
    assert pdf.status_code == 200 and pdf_none.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "Ortofotomapa niedostępna" not in "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert {k: r.call_count for k, r in routes.items()} == calls  # offline: zero nowych zapytań
    assert elapsed < 15


@respx.mock
def test_demo_examples_hide_unavailable_when_offline_or_uldk_blocked(db, client):
    settings.demo_parcels_preload = True
    uldk.load_known(force=True)
    assert len(client.get("/api/demo/examples").json()) == 6  # normalnie – wszystkie
    trip(uldk.SOURCE, 60, "usługa chwilowo ogranicza ruch")
    ids = [e["id"] for e in client.get("/api/demo/examples").json()]
    # A8: wszystkie działki przykładów są już w repo (demo_parcels.json) – przy blokadzie ULDK widać wszystkie
    assert ids == [e.id for e in demo.EXAMPLES]
    BREAKERS.clear()
    mock_all()
    respx.get(settings.open_meteo_forecast_url).mock(return_value=httpx.Response(503))  # A8: przykłady „na dziś”
    client.get("/api/analysis", params={"parcel_id": PID, "crop": "zboza_ozime", "date": __import__("app.core.clock", fromlist=["today_pl"]).today_pl().isoformat()})
    settings.demo_offline = True
    ids = [e["id"] for e in client.get("/api/demo/examples").json()]
    assert ids == ["dobra-dzialka"]  # offline: tylko to, co liczy się z samego cache
