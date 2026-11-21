"""Testy klienta ULDK i endpointu /api/parcel – na zapisanych odpowiedziach, bez sieci."""

import asyncio

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.http import NotFoundError, SourceError, close_client
from app.main import app
from app.sources import uldk

# Prawdziwa odpowiedź ULDK dla 201305_2.0038.6/1 (GetParcelById, srid=2180)
ULDK_ONE = (
    "0\n"
    "SRID=2180;POLYGON((741326.598870282 582135.860610104,741196.719087438 582172.956309767,"
    "741196.080461016 582126.579753392,741319.716303976 582092.766677043,"
    "741323.823760127 582113.17232317,741326.598870282 582135.860610104))"
    "|201305_2.0038.6/1|podlaskie|powiat wysokomazowiecki|Kobylin-Borzymy|Wnory-Wandy|6/1\n"
)

# GetParcelByIdOrNr „Wola 1” – kilka działek (pierwsza linia = liczba rekordów)
_SQ = "POLYGON((500000 500000,500100 500000,500100 500100,500000 500100,500000 500000))"
ULDK_MANY = (
    "3\n"
    f"SRID=2180;{_SQ}|041905_2.0022.1|kujawsko-pomorskie|powiat żniński|Rogowo|Wola|1\n"
    f"SRID=2180;{_SQ}|060203_2.0028.1|lubelskie|powiat biłgorajski|Biłgoraj|Wola|1\n"
    f"{_SQ}|142004_5.0018.1|mazowieckie|powiat płoński|Czerwińsk nad Wisłą|Wola|1\n"
)

ULDK_NONE = (
    "-1 brak wyników\n"
    "błędny format odpowiedzi XML, usługa zwróciła odpowiedźZbiorcza baza danych obsłużyła zapytanie.\n"
)


@pytest.fixture(autouse=True)
def _clean_cache():
    uldk.clear_cache()
    yield
    uldk.clear_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# --- parser -------------------------------------------------------------------------------------


def test_parse_one_parcel():
    [p] = uldk.parse_response(ULDK_ONE)
    assert p.id == "201305_2.0038.6/1"
    assert (p.voivodeship, p.county, p.commune, p.region, p.number) == (
        "podlaskie", "powiat wysokomazowiecki", "Kobylin-Borzymy", "Wnory-Wandy", "6/1")
    # pole wieloboku policzone ręcznie (wzór Gaussa) ≈ 6 010 m²
    assert p.area_ha == pytest.approx(0.60, abs=0.02)
    c = p.geom_4326.centroid
    assert 22.4 < c.x < 22.7 and 52.8 < c.y < 53.1  # gm. Kobylin-Borzymy
    assert p.geom_4326.is_valid


def test_parse_many_parcels():
    parcels = uldk.parse_response(ULDK_MANY)
    assert [p.id for p in parcels] == ["041905_2.0022.1", "060203_2.0028.1", "142004_5.0018.1"]
    assert all(p.area_ha == pytest.approx(1.0) for p in parcels)  # 100 m × 100 m


def test_parse_no_results():
    with pytest.raises(NotFoundError):
        uldk.parse_response(ULDK_NONE)


def test_parse_garbage():
    with pytest.raises(SourceError) as e:
        uldk.parse_response("<html>Service Unavailable</html>")
    assert not isinstance(e.value, NotFoundError)


@pytest.mark.parametrize(("text", "full"), [
    ("143203_2.0027.112/11", True),
    ("201305_2.0038.6/1", True),
    ("Szczytno 112/11", False),
    ("112/11", False),
])
def test_is_full_id(text, full):
    assert uldk.is_full_id(text) is full


def test_normalize_query():
    assert uldk.normalize_query("  Szczytno,  112/11 ") == "Szczytno 112/11"


# --- endpoint /api/parcel -----------------------------------------------------------------------


@respx.mock
def test_endpoint_by_id_ok(client):
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    r = client.get("/api/parcel", params={"id": "201305_2.0038.6/1"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "201305_2.0038.6/1"
    assert body["gmina"] == "Kobylin-Borzymy"
    assert body["obreb"] == "Wnory-Wandy"
    assert body["numer"] == "6/1"
    assert body["powierzchnia_ha"] == pytest.approx(0.60, abs=0.02)
    assert body["geometria"]["type"] == "Polygon"
    lon, lat = body["geometria"]["coordinates"][0][0]
    assert 14 < lon < 24.2 and 49 < lat < 55  # WGS84, kolejność lon,lat
    assert body["zrodlo"]["nazwa"] == "ULDK GUGiK"
    sent = route.calls.last.request.url.params
    assert sent["request"] == "GetParcelById"
    assert sent["srid"] == "2180"


@respx.mock
def test_endpoint_name_number_uses_id_or_nr(client):
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    assert client.get("/api/parcel", params={"id": "Szczytno 112/11"}).status_code == 200
    sent = route.calls.last.request.url.params
    assert sent["request"] == "GetParcelByIdOrNr"
    assert sent["id"] == "Szczytno 112/11"


@respx.mock
def test_endpoint_many_returns_409(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_MANY))
    r = client.get("/api/parcel", params={"id": "Wola 1"})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["total"] == 3
    assert [c["id"] for c in detail["candidates"]] == [
        "041905_2.0022.1", "060203_2.0028.1", "142004_5.0018.1"]
    assert detail["candidates"][1]["gmina"] == "Biłgoraj"


@respx.mock
def test_endpoint_not_found_404(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_NONE))
    r = client.get("/api/parcel", params={"id": "999999_9.9999.1/1"})
    assert r.status_code == 404
    assert r.json()["detail"]["source"] == "ULDK GUGiK"


@respx.mock
def test_endpoint_by_point(client):
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    r = client.get("/api/parcel", params={"lon": 22.55, "lat": 52.95})
    assert r.status_code == 200
    sent = route.calls.last.request.url.params
    assert sent["request"] == "GetParcelByXY"
    assert sent["xy"].endswith(",4326")
    assert sent["xy"].startswith("22.55")  # lon pierwsze


def test_endpoint_point_outside_poland(client):
    assert client.get("/api/parcel", params={"lon": 2.35, "lat": 48.85}).status_code == 404


@respx.mock
def test_endpoint_service_down_502(client):
    respx.get(settings.uldk_url).mock(side_effect=httpx.ConnectError("boom"))
    r = client.get("/api/parcel", params={"id": "201305_2.0038.6/1"})
    assert r.status_code == 502
    assert r.json()["detail"]["source"] == "ULDK GUGiK"


@respx.mock
def test_endpoint_timeout_502(client):
    respx.get(settings.uldk_url).mock(side_effect=httpx.ReadTimeout("slow"))
    r = client.get("/api/parcel", params={"id": "201305_2.0038.6/1"})
    assert r.status_code == 502
    assert "nie odpowiada" in r.json()["detail"]["message"]


@respx.mock
def test_endpoint_http_error_502(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(503, text="maintenance"))
    assert client.get("/api/parcel", params={"id": "201305_2.0038.6/1"}).status_code == 502


@respx.mock
def test_retry_once_on_connection_error(client):
    respx.get(settings.uldk_url).mock(
        side_effect=[httpx.ConnectError("dns"), httpx.Response(200, text=ULDK_ONE)])
    assert client.get("/api/parcel", params={"id": "201305_2.0038.6/1"}).status_code == 200


def test_endpoint_missing_params_422(client):
    assert client.get("/api/parcel").status_code == 422


# --- test na żywo (pytest -m live) --------------------------------------------------------------


@pytest.mark.live
def test_live_uldk_parcel():
    async def run():
        try:
            return await uldk.by_id("201305_2.0038.6/1")
        finally:
            await close_client()

    [p] = asyncio.run(run())
    assert p.id == "201305_2.0038.6/1"
    assert p.commune == "Kobylin-Borzymy"
    assert 0.3 < p.area_ha < 1.0
