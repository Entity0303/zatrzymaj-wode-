"""Testy prognozy Open-Meteo i endpointu /api/forecast – bez sieci."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.sources import open_meteo

PAYLOAD = {
    "latitude": 52.33857,
    "longitude": 20.614014,
    "current": {"time": "2026-11-21T14:45", "temperature_2m": 2.3, "weather_code": 3, "is_day": 1},
    "daily": {
        "time": ["2026-11-21", "2026-11-22", "2026-11-23"],
        "weather_code": [51, 0, 85],
        "temperature_2m_max": [3.0, 3.6, 1.9],
        "temperature_2m_min": [-1.4, 1.3, 0.2],
        "precipitation_sum": [0.4, 0.0, 1.9],
        "et0_fao_evapotranspiration": [0.33, 0.36, 0.19],
    },
}


@pytest.fixture(autouse=True)
def _clean():
    open_meteo.clear_cache()
    yield
    open_meteo.clear_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_parse():
    fc = open_meteo.parse_response(PAYLOAD)
    assert fc.current_temp == 2.3
    assert open_meteo.describe(fc.current_code) == ("Pochmurno", "cloud")
    assert [d.precip_mm for d in fc.days] == [0.4, 0.0, 1.9]


def test_describe_unknown():
    assert open_meteo.describe(None)[0] == "Brak danych"
    assert open_meteo.describe(42)[1] == "unknown"


@respx.mock
def test_endpoint_ok(client):
    route = respx.get(settings.open_meteo_forecast_url).mock(
        return_value=httpx.Response(200, json=PAYLOAD))
    r = client.get("/api/forecast", params={"lon": 20.62, "lat": 52.33, "days": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["teraz"]["temperatura"] == 2.3
    assert body["teraz"]["opis"] == "Pochmurno"
    assert [d["opis"] for d in body["dni"]] == ["Lekka mżawka", "Bezchmurnie", "Przelotny śnieg"]
    assert body["dni"][0]["bilans_mm"] == pytest.approx(0.07)
    assert body["bilans_okresu_mm"] == pytest.approx(0.4 + 0 + 1.9 - 0.33 - 0.36 - 0.19, abs=0.05)
    assert route.calls.last.request.url.params["timezone"] == "Europe/Warsaw"


@respx.mock
def test_endpoint_missing_value_gives_no_sum(client):
    payload = {**PAYLOAD, "daily": {**PAYLOAD["daily"], "precipitation_sum": [0.4, None, 1.9]}}
    respx.get(settings.open_meteo_forecast_url).mock(return_value=httpx.Response(200, json=payload))
    body = client.get("/api/forecast", params={"lon": 20.62, "lat": 52.33, "days": 3}).json()
    assert body["dni"][1]["opad_mm"] is None
    assert body["dni"][1]["bilans_mm"] is None
    assert body["bilans_okresu_mm"] is None  # brak danych nie może udawać zera


@respx.mock
def test_endpoint_rate_limited_502(client):
    respx.get(settings.open_meteo_forecast_url).mock(return_value=httpx.Response(429))
    r = client.get("/api/forecast", params={"lon": 20.62, "lat": 52.33})
    assert r.status_code == 502
    assert r.json()["detail"]["source"] == open_meteo.SOURCE


def test_endpoint_outside_poland(client):
    assert client.get("/api/forecast", params={"lon": 2.3, "lat": 48.8}).status_code == 404
