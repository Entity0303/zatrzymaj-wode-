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
    # F29: teren i spływ dla pola narysowanego – POST z obrysem (dawniej 501, mapa była pusta)
    for lay in ("teren", "splyw"):
        r = client.post(f"/api/layers/{lay}", json={"geometry": geom})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["layer"] == lay and body["parcel_id"].startswith("narysowane_") and body["features"]["features"]
    assert client.post("/api/layers/gleba", json={"geometry": geom}).status_code == 501


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


# ── CZĘŚĆ 3: woda w okolicy (hydrologia), zgłoszenia ───────────────────────────────────────

from datetime import date  # noqa: E402

from shapely.geometry import LineString, Point  # noqa: E402

from app.analysis import hydro as H  # noqa: E402
from app.core.geo import to_2180, to_wgs84  # noqa: E402
from app.schemas.analysis import Hydro, TerrainOutlet  # noqa: E402
from app.sources import imgw_hydro, overpass  # noqa: E402
from test_a6 import GEOM_4326  # noqa: E402


def _line_at(dx_m: float, dy_m: float, length=200.0) -> list[dict]:
    """Linia (geometria Overpass) przesunięta od środka działki 201305 o (dx, dy) m – pionowo w EPSG:2180."""
    c = to_2180(GEOM_4326).centroid
    ln = to_wgs84(LineString([(c.x + dx_m, c.y + dy_m - length / 2), (c.x + dx_m, c.y + dy_m + length / 2)]))
    return [{"lon": x, "lat": y} for x, y in ln.coords]


def osm_elements():
    return [
        {"type": "way", "id": 1, "tags": {"waterway": "ditch"}, "geometry": _line_at(-180, -60)},  # rów na zachodzie
        {"type": "way", "id": 2, "tags": {"waterway": "stream", "name": "Struga"}, "geometry": _line_at(300, 0)},
        {"type": "way", "id": 3, "tags": {"waterway": "river", "name": "Daleka"}, "geometry": _line_at(2000, 0)},
    ]


def outlet_west():
    g = to_2180(GEOM_4326)
    w = to_wgs84(Point(g.bounds[0], g.centroid.y))  # zachodni brzeg działki
    return [TerrainOutlet(direction="zachód", direction_short="W", azimuth_deg=270.0, share_of_parcel_pct=80.0,
                          location=[w.x, w.y])]


def test_hydro_objects_distance_and_toward_outflow():
    objs = H.objects(osm_elements(), GEOM_4326, outlet_west())
    feats = [f for f, _ in objs]
    assert [f.kind for f in feats] == ["row", "ciek"]  # rzeka 2 km – poza promieniem 500 m
    row, ciek = feats
    assert row.toward_outflow and not ciek.toward_outflow and ciek.name == "Struga"
    assert 0 < row.distance_m < 200 and row.distance_m < ciek.distance_m <= 500
    s = H.sentence(feats, None)
    assert s.startswith("Rów melioracyjny") and "w kierunku odpływu wody – zastawka może zatrzymać wodę." in s
    lay = H.layer(objs)
    assert lay["type"] == "FeatureCollection" and {f["properties"]["kind"] for f in lay["features"]} == {"row", "ciek"}
    assert all(f["geometry"]["type"] in ("LineString", "Polygon") for f in lay["features"])
    assert H.sentence([], None).startswith("W promieniu 500 m od działki nie ma")


def test_hydro_rule_facts_states():
    assert H.rule_facts(None)["hydro_ditch_state"] == "nieznany"
    assert H.rule_facts(H.pending())["hydro_zastawka_conf"] == "ograniczona"
    assert H.rule_facts(Hydro(status="none", features=[]))["hydro_ditch_state"] == "brak"
    h, _ = H.build(osm_elements(), None, GEOM_4326, outlet_west(), date(2026, 11, 22))
    f = H.rule_facts(h)
    assert f["hydro_ditch_state"] == "w_kierunku_odplywu" and f["hydro_zastawka_conf"] == "wysoka"


def test_gauge_state_from_percentiles_and_warning(monkeypatch):
    monkeypatch.setattr(imgw_hydro, "_levels", lambda: {"1": {"p": {"11": [100, 150, 200, 250]}}})
    g = imgw_hydro.parse([{"id_stacji": "1", "stacja": "WIZNA", "rzeka": "Narew", "lon": "22.5", "lat": "53.2",
                           "stan_wody": "140", "stan_wody_data_pomiaru": "2026-11-22 06:00:00",
                           "stan_ostrzegawczy": "400", "stan_alarmowy": "450"}])[0]
    assert g.name == "Wizna" and imgw_hydro.state(g, 11) == "niski"
    g.level_cm = 180
    assert imgw_hydro.state(g, 11) == "sredni"
    g.level_cm = 410
    assert imgw_hydro.state(g, 11) == "wysoki"  # ≥ ostrzegawczego
    hit = imgw_hydro.nearest([g], 22.6, 53.05, 11)
    assert hit and 15 < hit[1] < 25


@respx.mock
def test_analysis_hydro_pending_then_cached_and_zastawka_rule(client):
    mock_all()
    nmt_route()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": D}).json())
    assert a.hydro.status == "pending"
    overpass._cache.set(tuple(round(v, 4) for v in H.search_bbox(GEOM_4326)), [])  # Overpass: brak wody w 500 m
    a2 = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": D}).json())
    assert a2.hydro.status == "none" and a2.hydro.sentence.startswith("W promieniu 500 m")
    assert "retencja.zastawka_na_rowie" not in [r.rule_id for r in a2.recommendations]
    assert any("wód gruntowych" in x for x in a2.reliability.limitations)


@respx.mock
def test_hydro_endpoint_and_water_layer(client):
    mock_all()
    nmt_route()
    respx.post(settings.overpass_url).mock(return_value=httpx.Response(200, json={"elements": osm_elements()}))
    respx.get(settings.imgw_hydro_url).mock(return_value=httpx.Response(200, json=[]))
    r = client.get("/api/hydro", params={"parcel_id": PID})
    assert r.status_code == 200, r.text
    h = Hydro.model_validate(r.json())
    assert h.status == "ok" and {f.kind for f in h.features} == {"row", "ciek"} and h.sources
    lay = client.get("/api/layers/woda", params={"parcel_id": PID})
    assert lay.status_code == 200 and lay.json()["features"]["features"]
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": D}).json())
    assert a.hydro.status == "ok"
    assert "Rów melioracyjny" in [s for s in a.verdict.statements if s.kind == "woda"][0].text


def test_infra_reports_crud_and_letter(client):
    from app.routers import infra_reports

    infra_reports.reset()
    r = client.post("/api/infra-reports", json={"object_type": "row", "lon": 22.6, "lat": 53.05,
                                                 "problem": "zatkany_przepust", "water_level": "wysoki",
                                                 "description": "Przepust pod drogą zatkany gałęziami."})
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["addressee"] == "Właściciel gruntu lub spółka wodna" and rep["confirmations"] == 0
    box_in = {"lon_min": 22, "lat_min": 53, "lon_max": 23, "lat_max": 54}
    assert [x["id"] for x in client.get("/api/infra-reports", params=box_in).json()] == [rep["id"]]
    box_out = {"lon_min": 14, "lat_min": 50, "lon_max": 15, "lat_max": 51}
    assert client.get("/api/infra-reports", params=box_out).json() == []
    assert client.post(f"/api/infra-reports/{rep['id']}/confirm").json()["confirmations"] == 1
    letter = client.get(f"/api/infra-reports/{rep['id']}/letter")
    assert letter.status_code == 200 and "Do: Właściciel gruntu lub spółka wodna" in letter.text
    bad = {"object_type": "ciek", "lon": 10, "lat": 50, "problem": "zamulony"}
    assert client.post("/api/infra-reports", json=bad).status_code == 422
    assert client.post("/api/infra-reports/nie-ma/confirm").status_code == 404


def test_demo_examples_less_instead_of_zulawy(client):
    ex = {e["id"]: e for e in client.get("/api/demo/examples").json()}
    assert "mady-zulawy" not in ex and ex["less-drzewce"]["parcel_id"] == "061408_5.0008.203"
    assert "stok i erozja na lessie" in ex["less-drzewce"]["description"].lower()
