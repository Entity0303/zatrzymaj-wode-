"""A9+ – teren w tle, adresy w wyszukiwarce, woda w okolicy (hydrologia), zgłoszenia. Bez sieci (respx, mocki)."""

import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis import terrain as T
from app.core.config import settings
from app.main import app
from app.schemas.analysis import AnalysisResponse, Terrain
from test_a5 import mock_all
from test_a6 import GEOM, nmt_route

PID = "201305_2.0038.6/1"
D = "2018-06-10"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── CZĘŚĆ 1: teren w tle ────────────────────────────────────────────────────────────────────


@respx.mock
def test_analysis_returns_terrain_pending_then_terrain_endpoint_and_cache(client, monkeypatch):
    monkeypatch.setattr(settings, "terrain_background", True)
    mock_all()
    route, calls = nmt_route()
    monkeypatch.setattr(T, "start_background", lambda *a, **k: None)  # tło sprawdzamy osobno – tu deterministycznie
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": D}).json())
    assert a.terrain is not None and a.terrain.status == "pending" and a.terrain_note is None
    assert not route.called  # analiza nie czekała na NMT
    st = [s for s in a.verdict.statements if s.kind == "teren"][0]
    assert st.level == "info" and st.text.startswith("Liczę ukształtowanie terenu")
    step = [s for s in a.steps if s.id == "terrain"][0]
    assert step.state == "pending"
    r = client.get("/api/terrain", params={"parcel_id": PID})
    assert r.status_code == 200, r.text
    t = Terrain.model_validate(r.json())
    assert len(t.zones) == 4 and route.called and t.outlets
    n = route.call_count
    a2 = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": D}).json())
    assert isinstance(a2.terrain, Terrain) and route.call_count == n  # z cache, bez NMT
    assert client.get("/api/layers/splyw", params={"parcel_id": PID}).status_code == 200


@respx.mock
def test_background_task_fills_cache(client, monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "terrain_background", True)
    mock_all()
    route, _ = nmt_route()

    async def run():
        assert await T.cached_terrain(GEOM, PID) is None
        T.start_background(GEOM, PID)
        T.start_background(GEOM, PID)  # drugie wywołanie – to samo zadanie
        assert len(T._tasks) == 1
        await asyncio.gather(*T._tasks.values())
        return await T.cached_terrain(GEOM, PID)

    res = asyncio.run(run())
    assert res is not None and res.facts["zone_share_pct"] and route.called


def test_grid_max_5000_points_for_large_parcel():
    from shapely.geometry import box

    big = box(500000, 500000, 501500, 501000)  # 150 ha
    prep = T.prepare(big)
    assert prep.E.size <= 5000 * 1.05 and prep.step > 10


@respx.mock
def test_terrain_post_geometry_and_satellite_layer_post(client, monkeypatch):
    mock_all()
    nmt_route()
    from test_a11 import fake_live

    fake_live(monkeypatch, [])
    geom = {"type": "Polygon", "coordinates": [[[22.6, 53.05], [22.603, 53.05], [22.603, 53.052], [22.6, 53.052],
                                                [22.6, 53.05]]]}
    r = client.post("/api/terrain", json={"geometry": geom})
    assert r.status_code == 200, r.text
    assert len(Terrain.model_validate(r.json()).zones) == 4
    r = client.post("/api/layers/kondycja", json={"geometry": geom, "date": "2026-11-20"})
    assert r.status_code == 200, r.text
    assert r.json()["raster"]["image_url"].startswith("data:image/png;base64,")
    assert client.post("/api/layers/teren", json={"geometry": geom}).status_code == 501


# ── CZĘŚĆ 2: adresy w wyszukiwarce ─────────────────────────────────────────────────────────

import httpx  # noqa: E402

from app.core.search_query import parse  # noqa: E402
from app.schemas.search import SearchResponse  # noqa: E402
from app.sources import uug  # noqa: E402

UUG_TCZOW = ('{"type":"address","found objects":15,"returned objects":1,"results":{"1":{"city":"Tczów","citypart":null,'
             '"street":null,"number":"123","teryt":"143604","simc":"0639943","ulic":null,"code":"26-706",'
             '"jednostka":"{Polska,mazowieckie,zwoleński,Tczów}","x":"670477.23","y":"387247.04","accuracy":"1"}}}')
UUG_EMPTY = '{"type":"address","found objects":0,"returned objects":0,"results":null}'
OSM_DLUGA = [{"osm_type": "node", "osm_id": 1, "lat": "50.0687", "lon": "19.9406", "display_name": "5, Długa, Kraków",
              "address": {"house_number": "5", "road": "Długa", "city": "Kraków", "county": "Kraków",
                          "state": "województwo małopolskie"}}]


@pytest.mark.parametrize("q, name, street, number", [
    ("Kraków, ul. Długa 5", "Kraków", "Długa", "5"),
    ("Kraków, Długa 5a", "Kraków", "Długa", "5a"),
    ("Wola, al. Polna 12/3", "Wola", "Polna", "12/3"),
    ("Tczów 123", "Tczów", None, "123"),
    ("Wnory-Wandy 6/1", "Wnory-Wandy", None, "6/1"),
])
def test_parse_address_forms(q, name, street, number):
    pq = parse(q)
    assert (pq.kind, pq.name, pq.street, pq.number) == ("obreb_numer", name, street, number)
    assert parse("Nowa Wieś, Busko").kind == "name"


def test_uug_parse_point_and_admin():
    a = uug.parse(UUG_TCZOW)[0]
    assert (a.locality, a.street, a.house_number, a.gmina, a.powiat, a.wojewodztwo, a.source) == (
        "Tczów", None, "123", "Tczów", "zwoleński", "mazowieckie", "prg")
    assert 21.3 < a.lon < 21.6 and 51.2 < a.lat < 51.5
    assert uug.parse(UUG_EMPTY) == []


@respx.mock
def test_search_village_number_returns_parcel_and_address_groups(client, monkeypatch):
    from test_a5c import ULDK_ONE  # noqa: F401 – format odpowiedzi ULDK
    monkeypatch.setattr(settings, "search_addresses", True)
    uldk_txt = ULDK_ONE.replace("201305_2.0038.6/1", "143604_2.0011.123").replace("Wnory-Wandy", "Tczów") \
        .replace("6/1", "123")
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=uldk_txt))
    respx.get(settings.uug_url).mock(return_value=httpx.Response(200, text=UUG_TCZOW))
    r = SearchResponse.model_validate(client.get("/api/search", params={"q": "Tczów 123"}).json())
    kinds = [x.kind for x in r.results]
    assert kinds == ["parcel", "address"] and r.interpreted_as == "obreb_numer"
    a = r.results[1]
    assert a.locality == "Tczów" and a.house_number == "123" and a.street is None and a.source == "prg"
    assert a.label.startswith("Tczów 123, gm. Tczów") and r.attribution == "Adresy: PRG GUGiK"


@respx.mock
def test_search_street_address_falls_back_to_osm_when_uug_blocked(client, monkeypatch):
    monkeypatch.setattr(settings, "search_addresses", True)
    monkeypatch.setattr(settings, "nominatim_min_interval_s", 0)
    uldk_route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text="-1 brak\n"))
    respx.get(settings.uug_url).mock(return_value=httpx.Response(200, text="blocked for abuse"))
    respx.get(settings.nominatim_url.rstrip("/") + "/search").mock(return_value=httpx.Response(200, json=OSM_DLUGA))
    r = SearchResponse.model_validate(client.get("/api/search", params={"q": "Kraków, ul. Długa 5"}).json())
    assert [x.kind for x in r.results] == ["address"] and not uldk_route.called  # ulica = adres, nie działka
    a = r.results[0]
    assert (a.street, a.house_number, a.locality, a.source) == ("Długa", "5", "Kraków", "osm")
    assert "OpenStreetMap" in (r.attribution or "") and any("UUG" in n for n in r.notices)
