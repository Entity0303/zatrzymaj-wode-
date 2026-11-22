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
