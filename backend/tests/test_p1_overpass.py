"""P1 – Overpass: serwery równolegle (pierwsza dobra odpowiedź wygrywa), odchudzone zapytanie, „brak danych” 10 min."""

import asyncio

import httpx
import pytest
import respx

from app.analysis import hydro as H
from app.core.config import settings
from app.core.http import SourceError
from app.sources import overpass

BBOX = (22.59, 53.04, 22.61, 53.06)
A, B = "https://a.example/api/interpreter", "https://b.example/api/interpreter"


@pytest.fixture(autouse=True)
def _servers(monkeypatch):
    monkeypatch.setattr(settings, "overpass_url", A)
    monkeypatch.setattr(settings, "overpass_fallback_urls", B)


def test_query_is_slim():
    q = overpass.query(BBOX)
    assert "[timeout:10]" in q and "ditch|drain|stream|canal|river" in q
    assert 'way["water"]' in q and 'way["landuse"="reservoir"]' in q and q.endswith("out geom;")
    assert H._kind({"landuse": "reservoir"}) == "zbiornik" and H._kind({"water": "pond"}) == "zbiornik"
    assert H._kind({"waterway": "ditch"}) is not None and H._kind({"highway": "track"}) is None


@respx.mock
def test_parallel_first_good_answer_wins():
    slow = respx.post(A).mock(side_effect=httpx.ConnectError("brak"))
    fast = respx.post(B).mock(return_value=httpx.Response(200, json={"elements": [{"type": "way", "id": 1}]}))
    els = asyncio.run(overpass.water_elements(BBOX))
    assert els == [{"type": "way", "id": 1}] and slow.called and fast.called
    assert overpass.last_fetch["server"] == "b.example" and overpass.last_fetch["tried"] == 2
    asyncio.run(overpass.water_elements(BBOX))  # drugi raz z cache – bez zapytań
    assert fast.call_count == 1


@respx.mock
def test_all_servers_fail_then_no_requests_for_10_minutes():
    a = respx.post(A).mock(return_value=httpx.Response(504))
    b = respx.post(B).mock(return_value=httpx.Response(429))
    with pytest.raises(SourceError) as e:
        asyncio.run(overpass.water_elements(BBOX))
    assert e.value.message == "Mapa rowów (OpenStreetMap) chwilowo nie odpowiada – spróbuj za chwilę"
    n = a.call_count + b.call_count
    with pytest.raises(SourceError):
        asyncio.run(overpass.water_elements(BBOX))  # w ciągu 10 minut – bez nowych zapytań
    assert a.call_count + b.call_count == n == 2
    other = (19.0, 52.0, 19.02, 52.02)  # inne miejsce nie jest blokowane (brak bezpiecznika na całe źródło)
    b.mock(return_value=httpx.Response(200, json={"elements": []}))
    assert asyncio.run(overpass.water_elements(other)) == []
    overpass._failed[overpass._key(BBOX)] = 0.0  # po 10 minutach – znowu próba
    assert asyncio.run(overpass.water_elements(BBOX)) == []


def test_limits():
    assert settings.overpass_server_timeout_s == 8.0 and settings.overpass_total_timeout_s == 15.0
    assert overpass.CACHE_TTL_S == 30 * 86400 and overpass.FAIL_TTL_S == 600
