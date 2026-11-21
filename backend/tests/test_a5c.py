"""A5c – wyszukiwanie (GET /api/search), działka z kliknięcia (GET /api/parcel?lon&lat) i własny obrys pola (POST).
Bez sieci (respx); fixture'y PRNG i Nominatim to zapisane prawdziwe odpowiedzi z 2026-11-21."""

import io
import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.analysis import drawn_field
from app.core.config import settings
from app.core.search_query import fold, parse
from app.main import app
from app.schemas.analysis import AnalysisResponse
from app.schemas.search import SearchResponse
from app.sources import nominatim, places, prng, uldk
from test_a5 import mock_all
from test_a5b2 import long_weather  # noqa: F401 – fixture: pogoda z 12 lat
from test_analysis import ULDK_ONE, WKT_201305

FIX = Path(__file__).parent / "fixtures"
PRNG_XML = (FIX / "prng_tcz.xml").read_text(encoding="utf-8")
OSM_TCZOW = (FIX / "nominatim_tczow.json").read_text(encoding="utf-8")
OSM_REVERSE = (FIX / "nominatim_reverse.json").read_text(encoding="utf-8")
PID = "201305_2.0038.6/1"
# 201305: środek działki ≈ 22.6004 E, 53.0502 N
ULDK_TWO = ULDK_ONE + ULDK_ONE.splitlines()[1].replace("201305_2.0038.6/1", "061704_2.0011.6/1").replace(
    "Kobylin-Borzymy", "Rybczewice").replace("podlaskie", "lubelskie").replace("wysokomazowiecki", "świdnicki") + "\n"
ULDK_NOT_FOUND = "-1 brak wyników\n"
PRNG_EMPTY = ('<?xml version="1.0"?><wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
              'numberMatched="unknown" numberReturned="0"></wfs:FeatureCollection>')


def block_302(request: httpx.Request) -> httpx.Response:
    return httpx.Response(302, headers={"location": "https://integracja01.gugik.gov.pl/resp/uldk.php"})


@pytest.fixture(autouse=True)
def _fresh():
    places.clear_cache()
    yield
    places.clear_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def search(client, q: str) -> SearchResponse:
    r = client.get("/api/search", params={"q": q})
    assert r.status_code == 200, r.text
    return SearchResponse.model_validate(r.json())


# ── 1. rozpoznawanie formatu zapytania ──────────────────────────────────────────────────────


@pytest.mark.parametrize("q,kind,name,number", [
    ("201305_2.0038.6/1", "parcel_id", None, None),
    ("201305_2.0038.6/1 ", "parcel_id", None, None),
    ("Wnory-Wandy 6/1", "obreb_numer", "Wnory-Wandy", "6/1"),
    ("wnory  wandy 6 / 1", "obreb_numer", "wnory wandy", "6/1"),
    ("Tczów 123/4", "obreb_numer", "Tczów", "123/4"),
    ("TCZOW, 123", "obreb_numer", "TCZOW", "123"),
    ("Wola 1", "obreb_numer", "Wola", "1"),
    ("dz. 6/1 Wnory-Wandy", "obreb_numer", "Wnory-Wandy", "6/1"),
    ("Kobylin–Borzymy 5", "obreb_numer", "Kobylin-Borzymy", "5"),
    ("Nowa Wieś 12a", "obreb_numer", "Nowa Wieś", "12a"),
    ("Tczów", "name", "Tczów", None),
    ("  nowa   wieś ", "name", "nowa wieś", None),
    ("Nowa Wieś, Busko", "name", "Nowa Wieś", None),
    ("Wnory-Wandy", "name", "Wnory-Wandy", None),
    ("xyzabc", "name", "xyzabc", None),
    ("", "empty", None, None),
    ("   ", "empty", None, None),
    ("123", "unrecognized", None, None),
    ("???", "unrecognized", None, None),
])
def test_parse_query_formats(q, kind, name, number):
    p = parse(q)
    assert p.kind == kind and p.name == name and p.number == number
    if kind == "parcel_id":
        assert p.parcel_id == "201305_2.0038.6/1"


def test_parse_query_area_hint_and_fold():
    assert parse("Nowa Wieś, Busko").area_hint == ["Busko"]
    assert fold("Wnory–Wandy") == fold("wnory wandy") == "wnory wandy"
    assert fold("Łódź") == "lodz" and fold("Brzeźno") == fold("BRZEZNO")


# ── 2. PRNG: wzorce filtra i parsowanie ─────────────────────────────────────────────────────


def test_prng_like_pattern_and_filter():
    assert prng.like_pattern("Tczów") == "Tcz.w*"                    # literał „ó” usługa nie dopasowuje
    assert prng.like_pattern("Tczow") == "Tczow*"
    assert prng.like_pattern("Tczow", loose=True) == "T...w*"        # bez ogonków: c z o → „.” (szeroki wzorzec)
    assert prng.like_pattern("Wnory-Wandy") == "Wnory.Wandy*"
    assert prng.like_pattern("Wnory Wandy") == prng.like_pattern("Wnory-Wandy")
    assert "*" not in prng.like_pattern("a*b!c")[:-1] and "!" not in prng.like_pattern("a*b!c")
    f = prng.build_filter("Nowa Wieś", hints=("Busko",))
    assert "<And>" in f and "GMINA" in f and "POWIAT" in f and "WOJEWODZTWO" in f and "matchCase=\"false\"" in f


def test_prng_parse_response_real_fixture():
    rows = prng.parse_response(PRNG_XML)
    names = {r.name: r for r in rows}
    assert {"Tczew", "Tczów"} <= set(names)
    t = names["Tczów"]
    assert (t.gmina, t.powiat, t.wojewodztwo) == ("Tczów", "zwoleński", "mazowieckie")  # „-gmina wiejska” obcięte
    assert t.lon == pytest.approx(21.4458, abs=1e-3) and t.lat == pytest.approx(51.3261, abs=1e-3)


# ── 3. GET /api/search ──────────────────────────────────────────────────────────────────────


@respx.mock
def test_search_parcel_id(client):
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    r = search(client, PID)
    assert r.interpreted_as == "parcel_id" and r.total == 1 and not r.truncated and r.hint is None
    x = r.results[0]
    assert x.kind == "parcel" and x.parcel_id == PID == x.id and x.source == "ULDK GUGiK"
    assert x.label == "Wnory-Wandy 6/1, gm. Kobylin-Borzymy, pow. wysokomazowiecki, podlaskie"
    assert x.bbox and x.bbox[0] < x.lon < x.bbox[2] and x.bbox[1] < x.lat < x.bbox[3] and not x.bbox_approx
    assert x.area_ha == pytest.approx(0.58, abs=0.01)
    assert route.call_count == 1
    search(client, PID)  # drugi raz – z cache, bez ULDK
    assert route.call_count == 1


@respx.mock
def test_search_obreb_and_number(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    r = search(client, "wnory-wandy 6/1")
    assert r.interpreted_as == "obreb_numer" and r.total == 1 and r.results[0].kind == "parcel"
    assert r.results[0].name == "Wnory-Wandy 6/1" and r.hint is None


@respx.mock
def test_search_obreb_in_several_communes_lists_all_with_gmina_and_powiat(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_TWO))
    r = search(client, "Wola 1")
    assert r.total == 2 and {x.gmina for x in r.results} == {"Kobylin-Borzymy", "Rybczewice"}
    assert all(x.kind == "parcel" and x.powiat and x.wojewodztwo and x.parcel_id for x in r.results)
    assert "Kilka obrębów" in (r.hint or "")


@respx.mock
def test_search_canonical_name_retry_for_typed_without_diacritics(client):
    """„Tczow 123” – ULDK nie zna zapisu bez ogonków; powtarzamy z nazwą kanoniczną z geokodera („Tczów”)."""
    calls = []

    def uldk_handler(request: httpx.Request):
        q = request.url.params.get("id")
        calls.append(q)
        return httpx.Response(200, text=ULDK_ONE if q == "Tczów 123" else ULDK_NOT_FOUND)

    respx.get(settings.uldk_url).mock(side_effect=uldk_handler)
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=PRNG_XML))
    r = search(client, "Tczow 123")
    assert r.total == 1 and r.results[0].kind == "parcel"
    assert calls[0] == "Tczow 123" and "Tczów 123" in calls


@respx.mock
def test_search_parcel_missing_falls_back_to_place_with_hint(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_NOT_FOUND))
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=PRNG_XML))
    r = search(client, "Tczów 123")
    assert r.interpreted_as == "obreb_numer" and r.total >= 1
    assert all(x.kind == "place" for x in r.results) and r.results[0].name == "Tczów"
    assert "Nie znaleziono działki nr 123" in (r.hint or "") and "kliknij swoje pole" in (r.hint or "")


@respx.mock
def test_search_uldk_blocked_is_notice_not_error(client):
    respx.get(settings.uldk_url).mock(side_effect=block_302)
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=PRNG_XML))
    r = search(client, "Tczów 123")
    assert r.results and r.results[0].kind == "place"
    assert any("ULDK GUGiK" in n for n in r.notices) and "ewidencja" in (r.hint or "")


@respx.mock
def test_search_place_name_from_prng(client):
    route = respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=PRNG_XML))
    r = search(client, "Tczów")
    assert r.interpreted_as == "name" and r.total == 1 and r.hint is None  # „Tczew” nie zaczyna się od „Tczów”
    x = r.results[0]
    assert x.kind == "place" and x.type == "miejscowosc" and x.type_label == "wieś" and x.source == "PRNG GUGiK"
    assert x.label == "Tczów, gm. Tczów, pow. zwoleński, mazowieckie" and x.parcel_id is None
    assert x.bbox and x.bbox_approx and x.bbox[0] < x.lon < x.bbox[2]
    search(client, "Tczów")
    assert route.call_count == 1  # cache bez wygasania


@respx.mock
def test_search_place_without_diacritics_uses_loose_pattern(client):
    seen = []

    def handler(request: httpx.Request):
        seen.append(request.url.params.get("filter", ""))
        return httpx.Response(200, text=PRNG_EMPTY if len(seen) == 1 else PRNG_XML)

    respx.get(settings.prng_url).mock(side_effect=handler)
    r = search(client, "Tczow")
    assert r.total == 1 and r.results[0].name == "Tczów"
    assert "Tczow*" in seen[0] and "T...w*" in seen[1]


@respx.mock
def test_search_many_places_with_same_name_truncated_to_10(client):
    members = "".join(
        f'<wfs:member><ms:M1_UrzedoweNazwyMiejscowosci xmlns:ms="http://mapserver.gis.umn.edu/mapserver" '
        f'xmlns:gml="http://www.opengis.net/gml/3.2"><ms:msGeometry><gml:Point><gml:pos>{50 + i / 10} {20 + i / 10}'
        f"</gml:pos></gml:Point></ms:msGeometry><ms:IDENTYFIKATORPRNG>{i}</ms:IDENTYFIKATORPRNG>"
        f"<ms:NAZWAGLOWNA>Nowa Wieś</ms:NAZWAGLOWNA><ms:RODZAJOBIEKTU>wieś</ms:RODZAJOBIEKTU>"
        f"<ms:GMINA>Gmina{i:02d}-gmina wiejska</ms:GMINA><ms:POWIAT>powiat</ms:POWIAT>"
        f"<ms:WOJEWODZTWO>mazowieckie</ms:WOJEWODZTWO></ms:M1_UrzedoweNazwyMiejscowosci></wfs:member>" for i in range(25))
    xml = ('<?xml version="1.0"?><wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0">' + members +
           "</wfs:FeatureCollection>")
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=xml))
    r = search(client, "Nowa Wieś")
    assert len(r.results) == 10 and r.total == 25 and r.truncated
    assert "dopisz gminę" in (r.hint or "") and all(x.gmina for x in r.results)
    assert [x.gmina for x in r.results] == sorted(x.gmina for x in r.results)  # lista z gminami, posortowana


@respx.mock
def test_search_prng_down_falls_back_to_nominatim_with_attribution(client):
    respx.get(settings.prng_url).mock(side_effect=block_302)
    respx.get(f"{settings.nominatim_url}/search").mock(return_value=httpx.Response(200, text=OSM_TCZOW))
    r = search(client, "Tczów")
    assert {x.type for x in r.results} == {"miejscowosc", "gmina"}
    assert r.attribution and "OpenStreetMap" in r.attribution
    village = next(x for x in r.results if x.type == "miejscowosc")
    assert village.source == nominatim.SOURCE and village.label == "Tczów, gm. Tczów, pow. zwoleński, mazowieckie"
    assert village.bbox == pytest.approx((21.4050574, 51.3013491, 21.4748965, 51.3554159)) and not village.bbox_approx
    assert any("PRNG GUGiK" in n for n in r.notices)


@respx.mock
def test_search_no_results_is_200_with_hint(client):
    respx.get(settings.prng_url).mock(return_value=httpx.Response(200, text=PRNG_EMPTY))
    respx.get(f"{settings.nominatim_url}/search").mock(return_value=httpx.Response(200, text="[]"))
    r = search(client, "xyzabc")
    assert r.results == [] and r.total == 0 and r.notices == []
    assert r.hint == "Wpisz nazwę wsi albo obręb i numer działki, np. Wnory-Wandy 6/1"


@respx.mock
def test_search_all_geocoders_down_is_200_with_notices(client):
    respx.get(settings.prng_url).mock(side_effect=block_302)
    respx.get(f"{settings.nominatim_url}/search").mock(return_value=httpx.Response(503))
    r = search(client, "xyzabc")
    assert r.results == [] and len(r.notices) == 2 and r.hint


@pytest.mark.parametrize("q", ["", "   ", "123", "???"])
def test_search_unusable_query_hint_without_network(client, q):
    r = client.get("/api/search", params={"q": q})
    assert r.status_code == 200
    body = r.json()
    assert body["results"] == [] and body["hint"].startswith("Wpisz nazwę wsi")


def test_search_demo_offline_uses_local_dictionary_and_known_parcels(client):
    settings.demo_offline = True
    settings.demo_parcels_preload = True
    uldk.clear_cache()
    with respx.mock(assert_all_called=False) as m:
        any_call = m.route().mock(return_value=httpx.Response(500))
        r = search(client, "Wnory-Wandy")
        assert r.results and r.results[0].source == "słownik demo" and r.results[0].gmina == "Kobylin-Borzymy"
        assert r.results[0].lon == pytest.approx(22.599, abs=0.01)
        p = search(client, "Wnory-Wandy 6/1")  # działka demo – z indeksu znanych, bez ULDK
        assert p.results and p.results[0].kind == "parcel" and p.results[0].parcel_id == PID
        t = search(client, "Tczów")
        assert t.results and t.results[0].gmina == "Tczów"
        assert not any_call.called


# ── 4. GET /api/parcel?lon&lat – działka z kliknięcia ───────────────────────────────────────


@respx.mock
def test_parcel_from_click(client):
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    r = client.get("/api/parcel", params={"lon": 22.6009, "lat": 53.0500})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == PID and body["source"] == "uldk" and body["name"] is None
    req = route.calls[0].request
    assert req.url.params["request"] == "GetParcelByXY" and req.url.params["xy"].endswith(",4326")
    assert req.url.params["xy"].startswith("22.6009000,53.0500000")
    # drugi klik w tę samą działkę – z indeksu znanych działek (bez ULDK)
    assert client.get("/api/parcel", params={"lon": 22.6009, "lat": 53.0500}).status_code == 200
    assert route.call_count == 1


@respx.mock
def test_parcel_from_click_errors(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_NOT_FOUND))
    assert client.get("/api/parcel", params={"lon": 22.5, "lat": 53.0}).status_code == 404  # droga / brak działki
    assert client.get("/api/parcel", params={"lon": 2.35, "lat": 48.85}).status_code == 404  # poza Polską
    assert client.get("/api/parcel", params={"lon": 22.5}).status_code == 422  # brak lat
    respx.get(settings.uldk_url).mock(side_effect=block_302)
    r = client.get("/api/parcel", params={"lon": 20.0, "lat": 52.0})
    assert r.status_code == 502 and r.json()["detail"]["source"] == "ULDK GUGiK"


# ── 5. własny obrys pola ────────────────────────────────────────────────────────────────────

# ok. 1,3 ha na polach przy 201305 (≈ 90 × 140 m)
D_LON, D_LAT = 22.6009, 53.0500
SQUARE = [[D_LON - 0.0007, D_LAT - 0.0006], [D_LON + 0.0007, D_LAT - 0.0006], [D_LON + 0.0007, D_LAT + 0.0006],
          [D_LON - 0.0007, D_LAT + 0.0006], [D_LON - 0.0007, D_LAT - 0.0006]]


def poly(ring=None):
    return {"type": "Polygon", "coordinates": [ring if ring is not None else SQUARE]}


def scaled(k: float) -> list:
    return [[D_LON + (x - D_LON) * k, D_LAT + (y - D_LAT) * k] for x, y in SQUARE]


def test_drawn_validation_ok_and_stable_id():
    g = drawn_field.parse_polygon(poly())
    ha = drawn_field.area_ha(g)
    assert 0.8 < ha < 1.4
    assert drawn_field.drawn_id(g) == drawn_field.drawn_id(drawn_field.parse_polygon(poly(list(reversed(SQUARE)))))
    assert drawn_field.drawn_id(g).startswith("narysowane_")
    open_ring = SQUARE[:-1]  # niezamknięty pierścień – domykamy
    assert drawn_field.parse_polygon(poly(open_ring)).is_valid
    feat = {"type": "Feature", "properties": {}, "geometry": poly()}
    assert drawn_field.parse_polygon(feat).equals(g)


@pytest.mark.parametrize("geometry,fragment", [
    (poly(scaled(0.15)), "za małe"),
    (poly(scaled(14)), "za duże"),
    (poly([[2.30, 48.85], [2.31, 48.85], [2.31, 48.86], [2.30, 48.86], [2.30, 48.85]]), "poza Polską"),
    (poly([[53.05, 22.60], [53.06, 22.60], [53.06, 22.61], [53.05, 22.61], [53.05, 22.60]]), "odwróconą kolejność"),
    (poly([[D_LON, D_LAT], [D_LON + 0.001, D_LAT + 0.001], [D_LON + 0.001, D_LAT], [D_LON, D_LAT + 0.001],
           [D_LON, D_LAT]]), "przecina sam siebie"),
    ({"type": "Point", "coordinates": [D_LON, D_LAT]}, "jednym wielokątem"),
    ({"type": "MultiPolygon", "coordinates": [poly()["coordinates"]]}, "jednym wielokątem"),
    ({"type": "Polygon", "coordinates": [[[D_LON, D_LAT], [D_LON + 0.001, D_LAT]]]}, "za mało punktów"),
    ({"type": "Polygon", "coordinates": [[["a", "b"], [1, 2], [3, 4], [1, 2]]]}, "niepoprawne współrzędne"),
    ({"type": "Polygon", "coordinates": []}, "nie ma współrzędnych"),
    (None, "Brak obrysu"),
])
def test_drawn_validation_errors(geometry, fragment):
    with pytest.raises(drawn_field.DrawnError) as exc:
        drawn_field.parse_polygon(geometry)
    assert fragment in str(exc.value)


@respx.mock
def test_post_analysis_drawn_field_full_analysis(client, long_weather):
    mock_all()
    body = {"geometry": poly(), "date": "2018-11-21"}
    r = client.post("/api/analysis", json=body)
    assert r.status_code == 200, r.text
    a = AnalysisResponse.model_validate(r.json())
    p = a.parcel
    assert p.source == "drawn" and p.name == "Pole narysowane przez rolnika" and p.id.startswith("narysowane_")
    g = drawn_field.parse_polygon(poly())
    assert p.powierzchnia_ha == pytest.approx(drawn_field.area_ha(g), abs=0.001)  # z kształtu
    assert p.wojewodztwo == "podlaskie" and p.gmina == "Kobylin-Borzymy"  # z działki ULDK w środku pola
    assert p.zrodlo.nazwa == "Pole narysowane przez rolnika" and "nie jest działka ewidencyjna" in p.zrodlo.uwagi
    # cała analiza jak dla działki
    assert a.verdict is not None and a.suggestions is not None and a.soil.dominant_code is not None
    assert a.approximate_area is None and a.cultivated_area_ha == pytest.approx(p.powierzchnia_ha, abs=0.1)
    assert any("Pole narysowane" in x for x in a.reliability.limitations)
    assert any(s.id == "parcel" and "narysowany" in s.label for s in a.steps)
    # ten sam obrys → ten sam wynik (id z kształtu)
    b = AnalysisResponse.model_validate(client.post("/api/analysis", json=body).json())
    assert b.parcel.id == p.id and b.verdict.headline == a.verdict.headline


@respx.mock
def test_post_analysis_drawn_admin_from_nominatim_when_uldk_down(client, long_weather):
    mock_all()
    respx.get(settings.uldk_url).mock(side_effect=block_302)
    respx.get(f"{settings.nominatim_url}/reverse").mock(return_value=httpx.Response(200, text=OSM_REVERSE))
    r = client.post("/api/analysis", json={"geometry": poly(), "date": "2018-11-21", "crop": "zboza_ozime"})
    assert r.status_code == 200, r.text
    p = AnalysisResponse.model_validate(r.json()).parcel
    assert (p.wojewodztwo, p.powiat, p.gmina) == ("podlaskie", "powiat wysokomazowiecki", "Kobylin-Borzymy")
    assert "OpenStreetMap" in p.zrodlo.uwagi and p.teryt_gminy == ""


@respx.mock
def test_post_analysis_drawn_admin_nearest_voivodeship_when_no_geocoder(client, long_weather):
    mock_all()
    respx.get(settings.uldk_url).mock(side_effect=block_302)
    respx.get(f"{settings.nominatim_url}/reverse").mock(return_value=httpx.Response(503))
    r = client.post("/api/analysis", json={"geometry": poly(), "date": "2018-11-21"})
    assert r.status_code == 200, r.text
    p = AnalysisResponse.model_validate(r.json()).parcel
    assert p.wojewodztwo == "podlaskie" and p.gmina == "nieznana" and "przybliżone" in p.zrodlo.uwagi


@respx.mock
def test_post_analysis_drawn_errors_are_readable_422(client):
    for geometry, fragment in [(poly(scaled(0.15)), "za małe"), (poly(scaled(14)), "za duże"),
                               (poly([[2.30, 48.85], [2.31, 48.85], [2.31, 48.86], [2.30, 48.86], [2.30, 48.85]]), "poza Polską")]:
        r = client.post("/api/analysis", json={"geometry": geometry})
        assert r.status_code == 422 and fragment in r.json()["detail"]["message"]
    r = client.post("/api/analysis", json={"geometry": poly(), "parcel_id": PID})
    assert r.status_code == 422 and "nie kilka naraz" in r.json()["detail"]["message"]
    assert client.post("/api/analysis", json={}).status_code == 422


@respx.mock
def test_post_report_pdf_drawn_field(client, long_weather):
    settings.terrain_saved_results = True
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    r = client.post("/api/report.pdf", json={"geometry": poly(), "date": "2018-11-21"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    pages = PdfReader(io.BytesIO(r.content)).pages
    assert len(pages) <= 6
    text = " ".join(" ".join(p.extract_text() for p in pages).split())
    assert "Pole narysowane przez rolnika" in text and "nie jest działką ewidencyjną" in text


# ── 6. kontrakt: przykłady (frontend/src/mocks/search.sample.json, drawn.sample.json) ────────

MOCKS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "mocks"


@pytest.mark.skipif(not (MOCKS / "search.sample.json").exists(), reason="brak katalogu frontend/ obok backend/")
def test_search_and_drawn_samples_match_contract():
    from app.schemas.analysis import AnalysisRequest
    from app.schemas.parcel import Parcel

    data = json.loads((MOCKS / "search.sample.json").read_text(encoding="utf-8"))
    for key in ("parcel_id", "obreb_numer", "name"):
        r = SearchResponse.model_validate(data[key])
        assert r.interpreted_as == {"parcel_id": "parcel_id", "obreb_numer": "obreb_numer", "name": "name"}[key]
        assert r.results
    kinds = {x.kind for k in data if k in ("parcel_id", "obreb_numer", "name") for x in SearchResponse.model_validate(data[k]).results}
    assert kinds == {"parcel", "place"}
    SearchResponse.model_validate(data["empty"])
    assert data["empty"]["results"] == [] and data["empty"]["hint"]
    drawn = json.loads((MOCKS / "drawn.sample.json").read_text(encoding="utf-8"))
    req = AnalysisRequest.model_validate(drawn["request"])
    g = drawn_field.parse_polygon(req.geometry)
    parcel = Parcel.model_validate(drawn["parcel"])
    assert parcel.source == "drawn" and parcel.name == "Pole narysowane przez rolnika"
    assert parcel.powierzchnia_ha == pytest.approx(drawn_field.area_ha(g), abs=0.001)


def test_ts_types_name_search_and_request_fields():
    """Każde pole kontraktu wyszukiwania i żądania analizy jest w frontend/src/api/types.ts (A5c)."""
    ts = Path(MOCKS.parent, "api", "types.ts")
    if not ts.exists():
        pytest.skip("brak katalogu frontend/ obok backend/")
    from app.schemas.analysis import AnalysisRequest
    from app.schemas.search import SearchResponse as SR
    from app.schemas.search import SearchResult as SRes

    text = ts.read_text(encoding="utf-8")
    for model in (SRes, SR, AnalysisRequest):
        for field in model.model_fields:
            assert f"{field}:" in text or f"{field}?:" in text, f"{model.__name__}.{field} brak w types.ts"
    for name in ("SearchResult", "SearchResponse", "AnalysisRequest"):
        assert f"export type {name}" in text
    assert "source?: 'uldk' | 'drawn' | 'approximate'" in text
