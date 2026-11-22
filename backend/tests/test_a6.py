"""A6 – teren i spływ wody z NMT (bez sieci): źródło NMT, przekierowania bez czytania treści, sekcja `terrain`,
ocena stref z glebą, progi oczka, warstwy /api/layers/teren i /api/layers/splyw, brak NMT, zapisany wynik,
DEMO_OFFLINE, wydajność i raport PDF."""

import asyncio
import io
import json
import time
import urllib.parse
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient
from pypdf import PdfReader
from shapely import wkt
from shapely.geometry import shape

from app.analysis import terrain as T
from app.analysis import terrain_interpret as TI
from app.analysis.recommendations import evaluate
from app.core.cache import store
from app.core.config import settings
from app.core.http import RedirectBlocked, SourceError, get_with_retry, request
from app.main import app
from app.schemas.analysis import AnalysisResponse
from app.sources import nmt, uldk
from test_a5 import mock_all
from test_analysis import ULDK_ONE, WKT_201305, facts

PID = "201305_2.0038.6/1"
Q = {"parcel_id": PID, "crop": "zboza_ozime", "date": "2018-06-10"}
RESEARCH = json.loads((Path(__file__).parent / "fixtures" / "terrain_201305_research.facts.json").read_text(encoding="utf-8"))
GEOM = wkt.loads(WKT_201305)
GEOM_4326 = uldk.parse_response(ULDK_ONE)[0].geom_4326


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def surface(e: float, n: float) -> float:
    """Sztuczny teren przy 201305: spadek 1% na południowy zachód + misa 1,5 m w środku działki."""
    e0, n0 = 741261.0, 582133.0
    plane = 141.0 + 0.01 * ((e - e0) + (n - n0)) / np.sqrt(2)
    bowl = -1.5 * np.exp(-((e - e0) ** 2 + (n - n0) ** 2) / (2 * 18.0**2))
    return float(plane + bowl)


def nmt_route(fn=surface):
    """Mock NMT: odpowiada 'N E h' dla każdego punktu z listy (x = północ, y = wschód)."""
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = urllib.parse.parse_qs(req.content.decode())
        assert body["request"] == ["GetHByPointList"]
        pts = body["list"][0].split(",")
        calls.append(len(pts))
        out = []
        for p in pts:
            n, e = (float(v) for v in p.split())
            out.append(f"{n:.2f} {e:.2f} {fn(e, n):.2f}")
        return httpx.Response(200, text=",".join(out))

    route = respx.post(settings.nmt_url).mock(side_effect=handler)
    return route, calls


# ── przekierowania (D56): nigdy nie podążamy, treści 3xx nie czytamy ───────────────────────


class Boom(httpx.AsyncByteStream):
    """Treść, której przeczytanie oznacza błąd (symulacja pliku ~126 MB z resp/uldk.php)."""

    async def __aiter__(self):
        raise AssertionError("przeczytano treść odpowiedzi 3xx")
        yield b""  # pragma: no cover

    async def aclose(self) -> None:
        pass


REDIRECT_TARGET = "https://integracja01.gugik.gov.pl/resp/uldk.php"


@respx.mock
def test_302_is_block_without_reading_body_any_source():
    target = respx.get(REDIRECT_TARGET).mock(return_value=httpx.Response(200, content=b"x" * 10))
    respx.get(settings.soil_map_url).mock(return_value=httpx.Response(
        302, headers={"location": REDIRECT_TARGET, "content-length": "126000000"}, stream=Boom()))
    with pytest.raises(RedirectBlocked) as e:
        asyncio.run(get_with_retry(settings.soil_map_url, {}, source="Mapa", timeout_s=2))
    assert "ogranicza ruch" in e.value.message and e.value.location == REDIRECT_TARGET
    assert not target.called  # za przekierowaniem nie idziemy


@respx.mock
def test_uldk_302_block_no_body_no_follow():
    target = respx.get(REDIRECT_TARGET).mock(return_value=httpx.Response(200, text="0\n"))
    route = respx.get(settings.uldk_url).mock(return_value=httpx.Response(
        302, headers={"location": REDIRECT_TARGET}, stream=Boom()))
    with pytest.raises(SourceError) as e:
        asyncio.run(uldk.by_id("061704_2.0011.383/2"))
    assert "ogranicza ruch" in e.value.message and route.call_count == 3 and not target.called


@respx.mock
def test_nmt_302_block_no_body_no_follow():
    target = respx.get(REDIRECT_TARGET).mock(return_value=httpx.Response(200))
    route = respx.post(settings.nmt_url).mock(return_value=httpx.Response(
        302, headers={"location": REDIRECT_TARGET}, stream=Boom()))
    prep = T.prepare(GEOM)
    with pytest.raises(SourceError):
        asyncio.run(nmt.heights_for_grid(prep.key, prep.E, prep.N))
    assert route.called and not target.called


@respx.mock
def test_oversized_response_is_aborted():
    respx.get(settings.soilgrids_url).mock(return_value=httpx.Response(200, headers={"content-length": "999999999"},
                                                                       stream=Boom()))
    with pytest.raises(SourceError) as e:
        asyncio.run(request("GET", settings.soilgrids_url, source="SoilGrids", timeout_s=2, max_bytes=1000))
    assert "za duża" in e.value.message


@respx.mock
def test_gzip_response_decoded_once():
    import gzip

    body = json.dumps({"ok": "zażółć"}).encode()
    respx.get(settings.soilgrids_url).mock(return_value=httpx.Response(
        200, headers={"content-encoding": "gzip", "content-type": "application/json"},
        stream=httpx.ByteStream(gzip.compress(body))))
    r = asyncio.run(get_with_retry(settings.soilgrids_url, {}, source="SoilGrids", timeout_s=2))
    assert r.json() == {"ok": "zażółć"} and r.text == body.decode()


@respx.mock
def test_corrupt_gzip_is_source_error_not_500():
    respx.get(settings.soil_map_url).mock(return_value=httpx.Response(
        200, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(b"to nie jest gzip")))
    with pytest.raises(SourceError) as e:
        asyncio.run(get_with_retry(settings.soil_map_url, {}, source="Mapa", timeout_s=2, retries=0))
    assert "uszkodzoną" in e.value.message


@respx.mock
def test_honest_user_agent_for_all_sources():
    route = respx.get(settings.soilgrids_url).mock(return_value=httpx.Response(200, json={}))
    asyncio.run(get_with_retry(settings.soilgrids_url, {}, source="SoilGrids", timeout_s=2))
    assert route.calls[0].request.headers["user-agent"] == "Wodoskop/0.1 (HackNation 2026)"


# ── źródło NMT ──────────────────────────────────────────────────────────────────────────────


def test_parse_heights_order_north_east():
    out = nmt.parse_heights("582100.00 741200.00 140.5,582105.00 741205.00 141.2,bad,1 2")
    assert out == {(741200.0, 582100.0): 140.5, (741205.0, 582105.0): 141.2}


@respx.mock
def test_nmt_chunks_parallel_and_cached(tmp_path):
    settings.cache_db = str(tmp_path / "c.sqlite")
    store()
    route, calls = nmt_route()
    prep = T.prepare(GEOM)
    h, info = asyncio.run(nmt.heights_for_grid(prep.key, prep.E, prep.N))
    assert max(calls) <= 1000 and sum(calls) == prep.E.size and info["requests"] == len(calls)
    assert np.isfinite(h).all() and h.size == prep.E.size
    n_calls = route.call_count
    nmt._cache.drop_memory()  # restart – z pliku, bez zapytań
    h2, _ = asyncio.run(nmt.heights_for_grid(prep.key, prep.E, prep.N))
    assert route.call_count == n_calls and np.allclose(h, h2)


def test_match_heights_tolerates_service_rounding():
    """A8: NMT odsyła współrzędne zaokrąglone po swojemu (448300.25 → 448300.2) – dopasowanie nie może ich gubić."""
    e = np.array([448300.25, 448311.75, 448323.25])
    n = np.array([541062.55, 541062.55, 541062.55])
    txt = "541062.6 448300.2 85.7,541062.6 448311.8 85.8,541062.6 448323.2 85.9"
    assert nmt.match_heights(e, n, txt).tolist() == [85.7, 85.8, 85.9]  # po kolejności
    shuffled = "541062.6 448323.2 85.9,541062.6 448300.2 85.7"  # inna kolejność, jeden brak
    h = nmt.match_heights(e, n, shuffled)
    assert h[0] == 85.7 and np.isnan(h[1]) and h[2] == 85.9


@respx.mock
def test_nmt_mostly_missing_is_error():
    respx.post(settings.nmt_url).mock(return_value=httpx.Response(200, text=""))
    prep = T.prepare(GEOM)
    with pytest.raises(SourceError) as e:
        asyncio.run(nmt.heights_for_grid(prep.key, prep.E, prep.N))
    assert "brak" in e.value.message


# ── teren × gleba (rules/teren_gleba.yaml) ──────────────────────────────────────────────────


def test_zone_rating_with_soil():
    """A5b-2b (D66): grupy lekka / średnia / ciężka (dawne „zwięzła” rozdzielone); strefa dołka = obniżenie."""
    f = {"zone_share_pct": {"sucha_gorka": 50.0, "stok": 0.4, "plasko": 30.0, "mokry_dolek": 20.0}}
    light = {z.key: z for z in TI.zones(f, "lekka")}
    medium = {z.key: z for z in TI.zones(f, "srednia")}
    heavy = {z.key: z for z in TI.zones(f, "ciezka")}
    unknown = {z.key: z for z in TI.zones(f, None)}
    assert light["mokry_dolek"].rating == "dobrze" and heavy["mokry_dolek"].rating == "zle"  # obniżenie: piasek + / glina ciężka −
    assert medium["mokry_dolek"].rating == "uwaga" and "może być podmokło" in medium["mokry_dolek"].sentence
    assert light["sucha_gorka"].rating == "zle" and medium["sucha_gorka"].rating == "uwaga"  # górka na piasku – najgorzej
    assert light["plasko"].rating == medium["plasko"].rating == heavy["plasko"].rating == "dobrze"
    assert heavy["stok"].rating is None and heavy["stok"].sentence is None  # < 1% – bez oceny
    assert light["sucha_gorka"].sentence.startswith("50% działki to górka")
    assert "20% działki to obniżenie" in heavy["mokry_dolek"].sentence and "wymakać" in heavy["mokry_dolek"].sentence
    assert unknown["mokry_dolek"].rating == "uwaga" and medium["mokry_dolek"].label == "obniżenie – zbiera się woda"
    assert [z.key for z in TI.zones(f, "srednia")] == ["sucha_gorka", "stok", "plasko", "mokry_dolek"]
    assert [z.color for z in TI.zones(f, "srednia")] == ["#8B6B4A", "#E8B931", "#5BB37F", "#2F80C9"]
    assert TI.soil_group(1) == "lekka" and TI.soil_group(3) == "srednia" and TI.soil_group(4) == "ciezka"
    assert TI.soil_group(None) == "nieznana"


def test_summary_plain_language_from_research_facts():
    s = TI.summary(RESEARCH)
    assert 2 <= s.count(".") <= 4 and "TWI" not in s and "D8" not in s
    assert "lekko nachylona" in s and "2,0 m" in s and "południowy zachód" in s and "z całej działki" in s
    assert "3,6 ha" in s  # dopływ 36 328 m² spoza działki
    # obniżenie (strefa) ≠ zagłębienie bez odpływu: 0 zagłębień – o zagłębieniach nic, o obniżeniach – tak (D66)
    assert "zagłębie" not in s and "W obniżeniach (32% działki) zbiera się woda" in s


def test_contract_from_research_facts():
    t = TI.to_contract(RESEARCH, "srednia")
    assert t.zone_share_pct == {"sucha_gorka": 0.0, "stok": 56.4, "plasko": 11.5, "mokry_dolek": 32.1}
    assert t.relief_m == 2.0 and t.slope_mean_pct == 3.1 and t.slope_max_pct == 6.1
    assert t.main_flow_direction_short == "SW" and t.outlets[0].share_of_parcel_pct == 100.0
    assert t.inflow_from_outside_ratio == 6.25 and t.depressions_count == 0 and t.largest_depression is None
    assert t.soil_group == "srednia" and t.confidence == "wysoka" and t.details.twi_mean == 8.54
    dolek = next(z for z in t.zones if z.key == "mokry_dolek")
    assert dolek.rating == "uwaga" and dolek.sentence.startswith("32% działki to obniżenie")


# ── progi oczka i reguły z terenu (D59) ────────────────────────────────────────────────────


def _main_depression_facts() -> dict:
    f = json.loads(json.dumps(RESEARCH))
    f["parcel_area_ha"] = 2.0
    f["n_depressions"] = 1
    f["largest_depression"] = {"area_m2": 900.0, "area_in_parcel_m2": 800.0, "max_depth_m": 0.6, "volume_m3": 250.0,
                               "catchment_m2": 30000.0, "location_lonlat": [22.6, 53.05]}
    f["proposals"] = [{"type": "oczko_w_zaglebieniu", "catchment_m2": 30000.0, "max_depth_m": 0.6,
                       "inflow_runoff_m3": 180.0, "suggested_pond_area_m2": 120.0, "location_lonlat": [22.6, 53.05]}]
    return f


def test_pond_thresholds():
    assert TI.rule_facts(RESEARCH, 3)["terrain_pond"] == "opcja"  # 201305: 0,58 ha, 2 m różnicy, brak zagłębień
    assert TI.rule_facts(_main_depression_facts(), 3)["terrain_pond"] == "glowna"
    small = dict(_main_depression_facts(), parcel_area_ha=0.2)
    assert TI.rule_facts(small, 3)["terrain_pond"] is None
    shallow = _main_depression_facts()
    shallow["proposals"][0]["max_depth_m"] = 0.2
    assert TI.rule_facts(shallow, 3)["terrain_pond"] == "opcja"
    tiny_catchment = _main_depression_facts()
    tiny_catchment["proposals"][0]["catchment_m2"] = 3000.0
    assert TI.rule_facts(tiny_catchment, 3)["terrain_pond"] is None
    assert TI.rule_facts(None, 3)["terrain_pond"] is None


def _with_terrain(f_terrain: dict, **kw):
    v = dict(facts(**kw).values)
    v.update(TI.rule_facts(f_terrain, 3))
    from app.analysis.hydro import rule_facts as hydro_facts

    v.update(hydro_facts(None))  # A9: woda w okolicy jeszcze nie sprawdzona – jak w analizie przed /api/hydro
    return type(facts())(v)


def test_pond_on_small_flat_parcel_is_only_option_not_main():
    recs = evaluate(_with_terrain(RESEARCH), available={"terrain"}, limit=False).recommendations
    ids = [r.id for r in recs]
    assert "retencja.oczko_opcja" in ids and "retencja.oczko_w_zaglebieniu" not in ids
    opt = next(r for r in recs if r.id == "retencja.oczko_opcja")
    assert opt.title.startswith("Do rozważenia") and opt.warning and opt.permit == "maybe"
    assert "zgłoszenia lub pozwolenia" in opt.permit_note and "starostwie" in opt.permit_note
    panel = evaluate(_with_terrain(RESEARCH), available={"terrain"}).recommendations
    assert not next((r for r in panel if r.id == "retencja.oczko_opcja"), opt).in_panel  # nigdy główna


def test_main_pond_and_wetland_from_real_depression():
    recs = evaluate(_with_terrain(_main_depression_facts()), available={"terrain"}, limit=False).recommendations
    ids = {r.id for r in recs}
    assert {"retencja.oczko_w_zaglebieniu", "retencja.mokradlo_srodpolne"} <= ids
    pond = next(r for r in recs if r.id == "retencja.oczko_w_zaglebieniu")
    assert "3 ha" in pond.description and "120 m²" in pond.description and pond.permit == "maybe"


def test_buffer_strip_and_culvert_rules():
    f = json.loads(json.dumps(RESEARCH))
    f["steep_share_pct"], f["slope_max_pct"] = 25.0, 12.0
    f["proposals"].append({"type": "pas_buforowy", "length_m": 80.0, "line_lonlat": [[22.6, 53.05], [22.601, 53.05]]})
    recs = evaluate(_with_terrain(f), available={"terrain"}, limit=False).recommendations
    strip = next(r for r in recs if r.id == "retencja.pas_buforowy_na_stoku")
    assert "12%" in strip.description and strip.permit == "none" and strip.eco_scheme.code == "E_MIOD"
    culvert = next(r for r in recs if r.id == "retencja.zastawka_na_rowie")
    assert culvert.warning and "spółką wodną" in culvert.description and culvert.permit == "maybe"
    assert all(r.eco_scheme is None or r.eco_scheme.code in ("E_MPW", "E_USU", "E_WSG", "E_PN", "E_MIOD", "E_EKSTUZ")
               for r in recs)


def test_terrain_rules_need_terrain_data():
    ev = evaluate(_with_terrain(RESEARCH))  # bez available={"terrain"}
    assert {"retencja.oczko_opcja", "retencja.zastawka_na_rowie"} <= set(ev.disabled)


# ── analiza z terenem / bez NMT ─────────────────────────────────────────────────────────────


@respx.mock
def test_analysis_with_terrain_from_nmt(client):
    routes = mock_all()
    routes["nmt"], _ = nmt_route()
    for params in (Q, {"parcel_id": PID, "date": "2018-06-10"}):  # z uprawą i bez uprawy
        r = client.get("/api/analysis", params=params)
        assert r.status_code == 200, r.text
        a = AnalysisResponse.model_validate(r.json())
        t = a.terrain
        assert t is not None and a.terrain_note is None
        assert sum(t.zone_share_pct.values()) == pytest.approx(100.0, abs=0.5)
        assert t.depressions_count >= 1 and t.largest_depression.max_depth_m > 0.3  # misa 1,5 m
        assert t.main_flow_direction_short in ("SW", "S", "W") and t.soil_group == "srednia"
        assert any(z.sentence for z in t.zones) and t.summary and t.source_tag.source.startswith("NMT GUGiK")
        steps = {s.id: s for s in a.steps}
        assert steps["terrain"].state == "done"
        nmt_src = next(s for s in a.reliability.sources if s.name == "NMT GUGiK")
        assert nmt_src.status == "ok"
        assert any(c.factor == "teren" and c.share == 0 and "informacyjnie" in c.description for c in a.causes)  # A18


@respx.mock
def test_analysis_without_nmt_terrain_null_with_reason(client):
    mock_all()  # NMT = 503
    b = client.get("/api/analysis", params=Q).json()
    assert b["terrain"] is None and "NMT GUGiK" in b["terrain_note"]
    assert next(s for s in b["reliability"]["sources"] if s["name"] == "NMT GUGiK")["status"] == "brak"
    assert not any(r["rule_id"] and r["rule_id"].startswith("retencja.oczko") for r in b["recommendations"])


@respx.mock
def test_saved_research_result_when_nmt_down_matches_facts_json(client):
    """Zapisany wynik osoby C (prawdziwe NMT, 21.11) – liczby zgodne z research/terrain/out/…facts.json."""
    settings.terrain_saved_results = True
    mock_all()  # NMT = 503
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params=Q).json())
    t = a.terrain
    assert t is not None and t.zone_share_pct == {k: float(RESEARCH["zone_share_pct"][k]) for k in t.zone_share_pct}
    assert t.relief_m == RESEARCH["relief_m"] and t.slope_mean_pct == RESEARCH["slope_mean_pct"]
    assert t.inflow_from_outside_m2 == RESEARCH["inflow_from_outside_m2"]
    assert "zapisanego wyniku" in t.limitations[0]
    nmt_src = next(s for s in a.reliability.sources if s.name == "NMT GUGiK")
    assert nmt_src.status == "czesciowo" and "21.11.2026" in nmt_src.note
    ids = [r.id for r in a.recommendations]
    assert "retencja.oczko_w_zaglebieniu" not in ids  # 201305: oczko co najwyżej jako opcja


# ── warstwy mapy ────────────────────────────────────────────────────────────────────────────


@respx.mock
def test_layer_teren_zones_clipped_and_light(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    nmt_route()
    r = client.get("/api/layers/teren", params={"parcel_id": PID, "date": "2018-06-10"})
    assert r.status_code == 200, r.text
    b = r.json()
    feats = b["features"]["features"]
    assert feats and all(f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in feats)
    parcel = GEOM_4326.buffer(1e-6)
    for f in feats:
        p = f["properties"]
        assert p["kind"] in ("gorka", "stok", "plasko", "dolek") and p["color"].startswith("#") and p["label"]
        assert parcel.contains(shape(f["geometry"]))  # przycięte do działki
    assert len(json.dumps(b)) < 60_000  # lekkie
    assert b["value_range"][0] < b["value_range"][1] and b["source_tag"]["source"] == "NMT GUGiK"


@respx.mock
def test_layer_splyw_paths_outlets_proposals(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    nmt_route()
    b = client.get("/api/layers/splyw", params={"parcel_id": PID}).json()
    kinds = {f["properties"]["kind"] for f in b["features"]["features"]}
    assert {"flow", "outflow", "retencja"} <= kinds
    out = next(f for f in b["features"]["features"] if f["properties"]["kind"] == "outflow")
    assert out["geometry"]["type"] == "Point" and out["properties"]["share_pct"] > 0 and "%" in out["properties"]["label"]
    assert all(f["geometry"]["type"] == "LineString" or f["geometry"]["type"] == "MultiLineString"
               for f in b["features"]["features"] if f["properties"]["kind"] == "flow")


@respx.mock
def test_layers_from_saved_result_and_errors(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    respx.post(settings.nmt_url).mock(return_value=httpx.Response(503))
    assert client.get("/api/layers/teren", params={"parcel_id": PID}).status_code == 502  # brak NMT, brak zapisu
    settings.terrain_saved_results = True
    b = client.get("/api/layers/teren", params={"parcel_id": PID}).json()
    shares = {f["properties"]["zone"]: f["properties"]["share_pct"] for f in b["features"]["features"]}
    assert shares == {"plasko": 11.5, "stok": 56.4, "mokry_dolek": 32.1} and "21.11.2026" in b["source_tag"]["source"]
    assert client.get("/api/layers/gleba", params={"parcel_id": PID}).status_code == 501  # A11: kondycja działa


# ── demo offline, wydajność, raport ─────────────────────────────────────────────────────────


@respx.mock
def test_offline_terrain_from_cache(tmp_path, client):
    settings.cache_db = str(tmp_path / "c.sqlite")
    store()
    routes = mock_all()
    routes["nmt"], _ = nmt_route()
    online = client.get("/api/analysis", params=Q).json()["terrain"]
    calls = routes["nmt"].call_count
    T.clear_memo()
    nmt._cache.drop_memory()
    settings.demo_offline = True
    b = client.get("/api/analysis", params=Q).json()
    assert b["terrain"] is not None and b["terrain"]["zone_share_pct"] == online["zone_share_pct"]
    assert client.get("/api/layers/splyw", params={"parcel_id": PID}).status_code == 200
    assert routes["nmt"].call_count == calls


def test_compute_under_one_second():
    prep = T.prepare(GEOM)
    h = np.array([surface(e, n) for e, n in zip(prep.E.ravel(), prep.N.ravel())])
    t0 = time.perf_counter()
    res = T.compute(prep, h, {"requests": 5})
    assert time.perf_counter() - t0 < 1.0 and res.facts["grid_step_m"] == RESEARCH["grid_step_m"]
    assert res.facts["parcel_cells"] == RESEARCH["parcel_cells"] and res.facts["nmt_points"] == RESEARCH["nmt_points"]


@respx.mock
def test_report_pdf_terrain_section(client):
    settings.terrain_saved_results = True
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    r = client.get("/api/report.pdf", params=Q)
    assert r.status_code == 200
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
    for phrase in ("obniżenie – zbiera się woda", "32% działki to obniżenie"):  # strona 1 (werdykt)
        assert phrase in text, phrase
    full = client.get("/api/report.pdf", params={**Q, "report_type": "full"})  # A5e-2: teren w raporcie szczegółowym
    text_full = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(full.content)).pages)
    for phrase in ("Gleba, teren i skąd dane", "NMT GUGiK", "Woda spływa", "Teren – szczegóły", "Siatka"):
        assert phrase in text_full, phrase
