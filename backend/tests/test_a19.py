"""A19: wyszukiwanie „gmina + numer” (obręby gminy z PRNG → ULDK, sekwencyjnie, maks. 10) i odporna konfiguracja CORS.
Bez sieci (respx)."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core import parcel_search as ps
from app.core.config import DEFAULT_CORS_ORIGIN_REGEX, Settings, parse_origins, settings
from app.core.search_query import parse
from app.main import app
from app.schemas.search import SearchResponse
from app.sources import places
from test_a5c import ULDK_NOT_FOUND, ULDK_TWO
from test_analysis import ULDK_ONE

PID = "201305_2.0038.6/1"


# ── CORS ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    ('["https://a.vercel.app", "https://b.pl"]', ["https://a.vercel.app", "https://b.pl"]),
    ("https://a.vercel.app,https://b.pl/", ["https://a.vercel.app", "https://b.pl"]),
    (" https://a.pl ", ["https://a.pl"]),
    ("", []),
    ("[]", []),
])
def test_cors_origins_json_or_comma_list(monkeypatch, raw, expected):
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert Settings(_env_file=None).cors_origins == expected


@pytest.mark.parametrize("raw", ['["https://a.pl"', '{"a": 1}', "[1, 2", "localhost:5173"])
def test_cors_bad_value_does_not_break_start(monkeypatch, raw):
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert Settings(_env_file=None).cors_origins == []


def test_cors_regex_default_and_invalid(monkeypatch):
    assert Settings(_env_file=None).cors_origin_regex == DEFAULT_CORS_ORIGIN_REGEX == r"^https://.*\.vercel\.app$"
    monkeypatch.setenv("CORS_ORIGIN_REGEX", "^https://(")
    assert Settings(_env_file=None).cors_origin_regex == ""
    monkeypatch.setenv("CORS_ORIGIN_REGEX", "")
    assert Settings(_env_file=None).cors_origin_regex == ""
    assert parse_origins(None) == [] and parse_origins(["https://x.pl"]) == ["https://x.pl"]


# ── parser ──────────────────────────────────────────────────────────────────────────────────


def test_parse_gmina_forms():
    p = parse("Wnory-Wandy 6/1 Kobylin-Borzymy")
    assert (p.kind, p.name, p.number, p.area_hint) == ("obreb_numer", "Wnory-Wandy", "6/1", ["Kobylin-Borzymy"])
    p = parse("Wnory-Wandy 6/1, gm. Kobylin-Borzymy")
    assert (p.name, p.area_hint) == ("Wnory-Wandy", ["Kobylin-Borzymy"])
    p = parse("Kobylin-Borzymy, Wnory-Wandy 6/1")  # wygląda jak adres bez „ul.” – sprawdzamy też działkę
    assert p.street == "Wnory-Wandy" and p.alt_parcel == ("Wnory-Wandy", ["Kobylin-Borzymy"])
    assert parse("Kraków, ul. Długa 5").alt_parcel is None
    assert parse("Kobylin-Borzymy 6/1").name == "Kobylin-Borzymy"


# ── „gmina + numer” na mockach ──────────────────────────────────────────────────────────────


def prng_xml(names: list[str], gmina: str = "Kobylin-Borzymy", kind: str = "wieś") -> str:
    members = "".join(
        f'<wfs:member><ms:M1_UrzedoweNazwyMiejscowosci xmlns:ms="http://mapserver.gis.umn.edu/mapserver" '
        f'xmlns:gml="http://www.opengis.net/gml/3.2"><ms:msGeometry><gml:Point><gml:pos>{53.0 + i / 100} {22.6}'
        f"</gml:pos></gml:Point></ms:msGeometry><ms:IDENTYFIKATORPRNG>{i}</ms:IDENTYFIKATORPRNG>"
        f"<ms:NAZWAGLOWNA>{n}</ms:NAZWAGLOWNA><ms:RODZAJOBIEKTU>{kind}</ms:RODZAJOBIEKTU>"
        f"<ms:GMINA>{gmina}-gmina wiejska</ms:GMINA><ms:IDENTYFIKATORGMINY>2013052</ms:IDENTYFIKATORGMINY>"
        f"<ms:POWIAT>wysokomazowiecki</ms:POWIAT><ms:WOJEWODZTWO>podlaskie</ms:WOJEWODZTWO>"
        f"</ms:M1_UrzedoweNazwyMiejscowosci></wfs:member>" for i, n in enumerate(names))
    return '<?xml version="1.0"?><wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0">' + members + \
        "</wfs:FeatureCollection>"


VILLAGES = ["Kobylin-Borzymy", "Zalesie", "Wnory-Wandy", "Kropiwnica"]


@pytest.fixture(autouse=True)
def _fresh():
    places.clear_cache()
    ps.clear_cache()
    yield
    places.clear_cache()
    ps.clear_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def search(client, q: str) -> SearchResponse:
    r = client.get("/api/search", params={"q": q})
    assert r.status_code == 200, r.text
    return SearchResponse.model_validate(r.json())


def uldk_by_query(answers: dict[str, str], seen: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("id", "")
        seen.append(q)
        return httpx.Response(200, text=answers.get(q, ULDK_NOT_FOUND))
    return handler


@respx.mock
def test_gmina_and_number_finds_parcel_in_gmina_obreby(client):
    seen: list[str] = []
    respx.get(settings.uldk_url).mock(side_effect=uldk_by_query({"Wnory-Wandy 6/1": ULDK_ONE}, seen))
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=prng_xml(VILLAGES)))
    r = search(client, "Kobylin-Borzymy 6/1")
    assert [x.parcel_id for x in r.results if x.kind == "parcel"] == [PID]
    assert "gminie Kobylin-Borzymy" in (r.hint or "") and "Wnory-Wandy" in (r.hint or "")
    assert seen[0] == "Kobylin-Borzymy 6/1" and len(seen) <= 1 + 3  # obręb = nazwa gminy, potem pozostałe wsie gminy
    n = len(seen)
    search(client, "Kobylin-Borzymy 6/1")  # drugi raz – z cache (ani jednego nowego zapytania o wsie gminy)
    assert len(seen) - n <= 1


@respx.mock
def test_gmina_as_filter_narrows_same_named_obreby(client):
    seen: list[str] = []
    respx.get(settings.uldk_url).mock(side_effect=uldk_by_query({"Wnory-Wandy 6/1": ULDK_TWO}, seen))
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=prng_xml(VILLAGES)))
    for q in ("Wnory-Wandy 6/1 Kobylin-Borzymy", "Wnory-Wandy 6/1, gm. Kobylin-Borzymy", "Kobylin-Borzymy, Wnory-Wandy 6/1"):
        r = search(client, q)
        ids = [x.parcel_id for x in r.results if x.kind == "parcel"]
        assert ids == [PID], (q, ids)  # ten sam obręb w gminie Rybczewice – odfiltrowany
    bez = search(client, "Wnory-Wandy 6/1")
    assert len([x for x in bez.results if x.kind == "parcel"]) == 2  # bez gminy – oba obręby do wyboru


@respx.mock
def test_more_than_10_obreby_without_hit_asks_for_village(client):
    names = [f"Wieś{i:02d}" for i in range(15)]
    seen: list[str] = []
    respx.get(settings.uldk_url).mock(side_effect=uldk_by_query({}, seen))
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=prng_xml(names, gmina="Duża Gmina")))
    respx.get(f"{settings.nominatim_url}/search").mock(return_value=httpx.Response(200, text="[]"))
    r = search(client, "Duża Gmina 7/2")
    assert not [x for x in r.results if x.kind == "parcel"]
    assert (r.hint or "").startswith("Dopisz nazwę wsi (obrębu), np. Wieś10 7/2")
    gmina_queries = [q for q in seen if q.startswith("Wieś")]
    assert len(gmina_queries) == settings.search_gmina_max_obreby  # maks. 10 obrębów na zapytanie, sekwencyjnie


def test_candidates_order_similar_seat_kind():
    P = ps.prng.PrngPlace
    pl = [P("1", None, "Zalesie", "wieś", "Kobylin-Borzymy", "2013052", "", "", 0, 0),
          P("2", None, "Kobylin-Borzymy", "wieś", "Kobylin-Borzymy", "2013052", "", "", 0, 0),
          P("3", None, "Wnory-Wandy", "wieś", "Kobylin-Borzymy", "2013052", "", "", 0, 0),
          P("4", None, "Wnory-Przypki", "przysiółek", "Kobylin-Borzymy", "2013052", "", "", 0, 0),
          P("5", None, "Borki", "kolonia", "Kobylin-Borzymy", "2013052", "", "", 0, 0)]
    # siedziba gminy, potem wsie alfabetycznie, potem kolonie; przysiółki pominięte (nie są obrębami)
    assert ps.candidates(pl, "Kobylin-Borzymy") == ["Kobylin-Borzymy", "Wnory-Wandy", "Zalesie", "Borki"]
    assert ps.candidates(pl, "Kobylin-Borzymy", rest="Wnory")[0] == "Wnory-Wandy"


@respx.mock
def test_obreb_named_like_gmina_counts_in_hint(client):
    """Obręb o nazwie gminy ma działkę – podpowiedź nie może mówić „nie ma działki” (wynik na żywo 22.11)."""
    names = ["Kobylin-Borzymy"] + [f"Wieś{i:02d}" for i in range(14)]
    seen: list[str] = []
    respx.get(settings.uldk_url).mock(side_effect=uldk_by_query({"Kobylin-Borzymy 6/1": ULDK_ONE}, seen))
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=prng_xml(names)))
    r = search(client, "Kobylin-Borzymy 6/1")
    assert [x.parcel_id for x in r.results if x.kind == "parcel"] == [PID]
    h = r.hint or ""
    assert h.startswith("Działka nr 6/1 w gminie Kobylin-Borzymy") and "nie ma działki" not in h
    assert "Sprawdziłem 11 z 15 obrębów" in h and "Wieś10 6/1" in h
