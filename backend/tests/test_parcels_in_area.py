"""F30: POST /api/parcels-in-area – działki ewidencyjne pod polem narysowanym (próbkowanie punktami, ULDK na atrapie)."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.http import SourceError
from app.main import app
from app.routers import parcel as parcel_router
from app.sources import uldk

GEOM = {"type": "Polygon", "coordinates": [[[22.60, 53.05], [22.61, 53.05], [22.61, 53.06], [22.60, 53.06], [22.60, 53.05]]]}


@pytest.fixture
def client():
    parcel_router._area_cache.clear()
    return TestClient(app)


def fake(pid, numer):
    return SimpleNamespace(id=pid, region="Wnory-Wandy", commune="Kobylin-Borzymy", number=numer)


def test_two_parcels_with_shares(client, monkeypatch):
    calls = []

    async def by_point(lon, lat):
        calls.append((lon, lat))
        return fake("A.1", "6/1") if lon < 22.606 else fake("A.2", "7")

    monkeypatch.setattr(uldk, "by_point", by_point)
    r = client.post("/api/parcels-in-area", json={"geometry": GEOM})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["note"] is None and 2 <= len(calls) <= parcel_router.AREA_POINTS
    assert {p["id"] for p in b["parcels"]} == {"A.1", "A.2"} and sum(p["share"] for p in b["parcels"]) in (99, 100, 101)
    assert b["parcels"][0]["share"] >= b["parcels"][1]["share"]
    assert set(b["parcels"][0]) == {"id", "obreb", "gmina", "numer", "share"}
    n = len(calls)
    assert client.post("/api/parcels-in-area", json={"geometry": GEOM}).json() == b and len(calls) == n  # z pamięci


def test_uldk_error_gives_empty_list_with_note(client, monkeypatch):
    async def by_point(lon, lat):
        raise SourceError("ULDK GUGiK", "usługa nie odpowiada")

    monkeypatch.setattr(uldk, "by_point", by_point)
    b = client.post("/api/parcels-in-area", json={"geometry": GEOM}).json()
    assert b == {"parcels": [], "note": parcel_router.AREA_NOTE}


def test_bad_geometry_is_422(client):
    assert client.post("/api/parcels-in-area", json={"geometry": {"type": "Point", "coordinates": [22.6, 53.05]}}).status_code == 422
