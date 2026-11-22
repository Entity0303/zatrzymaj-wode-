"""A5b-2b – werdykt działki, spójność teren × gleba, etykieta gleby ważona udziałem, uprawy wieloletnie poza rankingiem,
status nawadniania „informacyjne”, analiza po punkcie (obszar przybliżony), raport PDF w obu wariantach. Bez sieci."""

import io
from datetime import date

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.analysis import approx_area
from app.analysis import suggestions as S
from app.analysis import terrain_interpret as TI
from app.analysis import verdict as V
from app.analysis.soil import SoilAssessment, SoilShare
from app.analysis.soil_consistency import MapSummary
from app.analysis.soil_label import Part, SoilProfile, profile
from app.core.config import settings
from app.main import app
from app.schemas.analysis import AnalysisResponse, Indicator
from app.sources.soil_map import SoilMapResult
from test_a5 import mock_all
from test_a5b2 import long_weather  # noqa: F401 – fixture: pogoda z 12 lat
from test_a6 import RESEARCH
from test_water_model import _dry_2018, _et0_seasonal, _wet, synth

PID = "201305_2.0038.6/1"
LAST = date(2018, 11, 20)


@pytest.fixture(autouse=True)
def _fresh():
    S._sim_memo.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def weather(precip=_dry_2018):
    return synth(date(2006, 8, 1), LAST, precip, _et0_seasonal)


def ctx(**kw) -> S.Context:
    base = dict(wod_mm=186.2, category=3, complex_code="2", voivodeship="podlaskie", area_ha=2.0, area_estimated=False,
                area_note="podana", history=[], soil_txt="kat. III", soil_group="srednia")
    base.update(kw)
    return S.Context(**base)


GOOD = SoilProfile("srednia", 3.0, [Part(1.0, "glina lekka", 3)], "mapa glebowo-rolnicza")
WEAK = SoilProfile("lekka", 1.0, [Part(1.0, "piasek luźny", 1)], "mapa glebowo-rolnicza")
WEAK_CTX = dict(wod_mm=106.3, category=1, complex_code="7", soil_txt="piasek luźny", soil_group="lekka")


def verdict(prof, wod, precip=_dry_2018, terrain=None, **kw):
    w = weather(precip)
    sug = S.build(w, LAST, ctx(**kw))
    return V.build(prof, wod, w, LAST, terrain, sug, [], None), sug


# ── 1. werdykt ──────────────────────────────────────────────────────────────────────────────


def test_verdict_good_parcel():
    v, _ = verdict(GOOD, 186.2, precip=_wet, terrain=TI.to_contract(RESEARCH, "srednia"))
    kinds = [s.kind for s in v.statements]
    assert kinds == ["gleba", "opady", "teren", "uprawy", "woda"] and 4 <= len(kinds) <= 6
    soil = v.statements[0]
    assert soil.level == "ok" and soil.text.startswith("Gleba średnia") and "zmieści ok. 186 mm" in soil.text
    assert v.crops_good and 2 <= len(v.crops_good) <= 4
    assert v.headline.startswith("Dobra")
    assert "według stałych reguł" in v.note and "Te same dane dają te same zdania" in v.note


def test_verdict_weak_parcel_bad_wheat_and_rapeseed_good_rye():
    v, sug = verdict(WEAK, 106.3, **WEAK_CTX)
    soil = v.statements[0]
    assert soil.level == "bad" and soil.text.startswith("Gleba lekka") and "mało trzyma wody" in soil.text
    bad = {c.crop_id for c in v.crops_bad}
    good = {c.crop_id for c in v.crops_good}
    assert {"pszenica_ozima", "rzepak"} <= bad
    assert "zyto" in good
    assert all(c.reason for c in v.crops_bad)
    crops = next(s for s in v.statements if s.kind == "uprawy")
    assert crops.text.startswith("Tu nie siej pszenicy ozimej, rzepaku")
    assert "za mało wody na tej glebie" in crops.text
    assert v.headline.startswith("Słaba") and v.level == "bad"


def test_verdict_two_soils_sentence():
    two = SoilProfile("srednia", 2.75, [Part(0.75, "glina lekka pylasta", 3), Part(0.25, "piasek gliniasty", 2)],
                      "mapa glebowo-rolnicza")
    st = V.soil_statement(two, 166.0)
    assert st.text.startswith("Na działce są dwie gleby: 75% – glina lekka pylasta i 25% – piasek gliniasty.")
    assert st.numbers["udzial_a"] == 75 and st.numbers["udzial_b"] == 25
    one = SoilProfile("srednia", 2.9, [Part(0.85, "glina lekka", 3), Part(0.15, "piasek gliniasty", 2)], "x")
    assert "dwie gleby" not in V.soil_statement(one, 166.0).text  # mniejsza ≤ 20% – jedna gleba


def test_verdict_says_explicitly_when_nothing_is_discouraged():
    v, sug = verdict(GOOD, 186.2, precip=_wet)
    if not v.crops_bad:
        crops = next(s for s in v.statements if s.kind == "uprawy")
        assert "żadna z popularnych upraw nie jest odradzana" in crops.text


def test_verdict_crops_none_bad_text_directly():
    from app.schemas.analysis import CropSuggestions

    v, sug = verdict(GOOD, 186.2, precip=_wet)
    for g in sug.groups:
        for i in g.items:
            if i.category == "odradzane":
                i.category = "mozliwe"
    st, good, bad = V.crops_statement(CropSuggestions.model_validate(sug.model_dump()), False)
    assert not bad and "Na tej ziemi żadna z popularnych upraw nie jest odradzana." in st.text


def test_verdict_is_deterministic_and_perennials_excluded():
    a, _ = verdict(WEAK, 106.3, **WEAK_CTX)
    S._sim_memo.clear()
    b, _ = verdict(WEAK, 106.3, **WEAK_CTX)
    assert a.model_dump() == b.model_dump()
    ids = {c.crop_id for c in a.crops_good + a.crops_bad}
    assert not ids & {"drzewa_owocowe", "krzewy_owocowe", "truskawki"}


def test_precip_deficit_years_threshold_from_yaml():
    st = V.precip_stats(weather(_dry_2018), LAST)
    assert st and st["years"] == 10
    thr = V.cfg()["thresholds"]
    assert thr["kbw_may_june_deficit_mm"] == -100 and thr["deficit_years_warn"] == 3 and thr["deficit_years_bad"] == 5
    s = V.precip_statement(st)
    exp = "bad" if st["deficit_years"] >= 5 else "warn" if st["deficit_years"] >= 3 else None
    if exp:
        assert s.level == exp
    n = st["deficit_years"]  # A18: przy 0 – „ani razu”, nie „w 0 z 10 lat”
    assert (f"w {n} z 10 lat" in s.text if n else "ani razu" in s.text and "w 0 z" not in s.text) and "600 mm" in s.text


def test_verdict_with_chosen_crop_adds_statement():
    from app.schemas.analysis import OverallStatus

    w = weather()
    sug = S.build(w, LAST, ctx())
    status = OverallStatus(level="warn", score=55, headline="Zapas wody maleje", summary="x")
    v = V.build(GOOD, 186.2, w, LAST, None, sug, [], None, ("Zboża ozime", "krzewienie", status))
    last = v.statements[-1]
    assert last.kind == "uprawa_wybrana" and last.level == "warn" and last.text.startswith("Zboża ozime (krzewienie)")
    assert len(v.statements) == 6


# ── 2. spójność: dołek vs zagłębienie, etykieta gleby ───────────────────────────────────────


def test_wet_zone_and_closed_depression_do_not_contradict():
    t = TI.to_contract(RESEARCH, "srednia")
    wet = next(z for z in t.zones if z.key == "mokry_dolek")
    assert "obniżenie, gdzie spływa i zbiera się woda" in wet.sentence
    assert "Nie ma zagłębień" not in t.summary and "brak zagłębień" not in t.summary.lower()
    st = V.terrain_statement(t)
    if not t.depressions_count:
        assert "zagłębienie bez odpływu" not in st.text
    facts = dict(RESEARCH, depressions_count=0)
    assert "zagłębien" not in TI.to_contract(facts, "srednia").summary.lower()


def _soil(shares: dict[int, float]) -> SoilAssessment:
    return SoilAssessment(soil_capacity=Indicator(value=None, unit="mm", label="x", source_tag={"kind": "brak_danych"}),
                          shares=[SoilShare(code=c, label=str(c), share=s) for c, s in shares.items()])


def test_soil_label_weighted_201305_is_medium_not_heavy():
    m = MapSummary(category=3, counts={3: 7, 2: 2}, valid=9, total=9, representative=None, by_category={
        3: SoilMapResult("2", "B", ("glp",)), 2: SoilMapResult("4", "B", ("pgl",))})
    p = profile(_soil({3: 1.0}), m, None)
    assert p.group == "srednia" and p.two_soils and "zwięzł" not in p.text
    assert p.parts[0].share == pytest.approx(7 / 9)
    assert profile(_soil({1: 0.9, 2: 0.1}), None, None).group == "lekka"
    assert profile(_soil({4: 1.0}), None, None).group == "ciezka"
    assert profile(_soil({5: 0.8, 3: 0.2}), None, None).group == "organiczna"


def test_humus_rule_only_for_light_soil():
    import yaml

    rules = yaml.safe_load(open("app/analysis/rules/retencja.yaml", encoding="utf-8"))["rules"]
    r = next(x for x in rules if "prochnica" in x["id"])
    assert {"fact": "light_soil", "eq": True} in r["when"]["all"]
    assert "lekka gleba" in r["title"] and "zwięzł" not in r["description"]


# ── 3. ranking: wieloletnie osobno, kukurydza „informacyjne” ────────────────────────────────


def test_perennials_outside_ranking_with_low_confidence():
    sug = S.build(weather(), LAST, ctx())
    ranked = {i.crop_id for g in sug.groups for i in g.items}
    assert not ranked & {"drzewa_owocowe", "krzewy_owocowe", "truskawki"}
    per = sug.perennials
    assert per and per.label == "Uprawy wieloletnie – inwestycja na lata"
    assert {p.crop_id for p in per.items} == {"drzewa_owocowe", "krzewy_owocowe", "truskawki"}
    assert all("opłacalności" in p.note for p in per.items)


def test_complex_decides_soil_suitability_before_iung():
    from app.analysis.crops import ALL_CROPS

    rye = ALL_CROPS["zyto"]
    assert S.soil_suitability(rye, 4, "7") == "odpowiednia"  # kompleks żytni bardzo słaby – żyto pasuje
    wheat = ALL_CROPS["pszenica_ozima"]
    assert S.soil_suitability(wheat, 2, "7") == "nieodpowiednia"
    assert S.soil_suitability(wheat, 1, None) == "nieodpowiednia"  # bez kompleksu – kategoria IUNG


# ── 4. analiza po punkcie ───────────────────────────────────────────────────────────────────


def test_approximate_parcel_is_1ha_square():
    p = approx_area.approximate_parcel(16.26, 52.685)
    assert p.geom_2180.area == pytest.approx(10_000, rel=1e-6)
    assert p.voivodeship == "wielkopolskie" and approx_area.is_approximate(p.id)
    assert approx_area.nearest_voivodeship(22.57, 51.25) == "lubelskie"


@respx.mock
def test_point_analysis_falls_back_to_approximate_area(client):
    mock_all()
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(302, headers={"location": "https://x/resp"}))
    r = client.get("/api/analysis", params={"lon": 22.6021, "lat": 53.0500, "date": "2018-06-10"})
    assert r.status_code == 200, r.text
    a = AnalysisResponse.model_validate(r.json())
    assert a.approximate_area is not None and a.approximate_area.area_ha == 1.0
    assert a.approximate_area.note.startswith("Ewidencja gruntów chwilowo nie odpowiada")  # P1: ULDK nie odpowiada
    assert a.parcel.id.startswith("obszar_przyblizony")
    assert any("Obszar przybliżony" in x for x in a.reliability.limitations)
    assert a.verdict is not None and a.verdict.statements[-1].kind == "woda" and a.verdict.statements[-1].level == "info"
    step = next(s for s in a.steps if s.id == "parcel")
    assert "obszar przybliżony" in (step.note or "")


@respx.mock
def test_point_analysis_uses_parcel_when_uldk_works(client):
    mock_all()
    r = client.get("/api/analysis", params={"lon": 22.6021, "lat": 53.0500, "date": "2018-06-10"})
    assert r.status_code == 200, r.text
    a = AnalysisResponse.model_validate(r.json())
    assert a.approximate_area is None and a.parcel.id == PID


def test_point_or_parcel_required(client):
    assert client.get("/api/analysis").status_code == 422
    assert client.get("/api/analysis", params={"lon": 2.35, "lat": 48.85}).status_code == 404


# ── 5. raport PDF: oba warianty, strona 1 = werdykt ─────────────────────────────────────────


@respx.mock
@pytest.mark.parametrize("crop", [None, "zboza_ozime"])
def test_report_pdf_verdict_page_both_variants(client, long_weather, crop):
    settings.terrain_saved_results = True
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    q = {"parcel_id": PID, "date": "2018-11-21"} | ({"crop": crop} if crop else {})
    r = client.get("/api/report.pdf", params=q)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    pages = PdfReader(io.BytesIO(r.content)).pages
    assert len(pages) == 2  # A5e-2: raport skrócony
    p1 = pages[0].extract_text()
    up = p1.upper()  # etykiety pozycji – wersaliki przez CSS
    assert "Werdykt działki" in p1 and "GLEBA" in up and "OPADY" in up and "CO SIAĆ" in up
    if crop:
        assert "WYBRANA UPRAWA" in up
    text = "\n".join(p.extract_text() for p in pages)
    assert "Co tu posiać?" in text and "Co zrobić z wodą" in text and "Na tle 10 lat" in text


# ── A5b-2c: drobne poprawki PDF ─────────────────────────────────────────────────────────────


def test_verdict_water_statement_is_info_not_rated():
    v, _ = verdict(WEAK, 106.3, **WEAK_CTX)
    water = next(s for s in v.statements if s.kind == "woda")
    assert water.level == "info"
    assert v.level == "bad"  # poziom całości liczy się bez pozycji „woda”


def _pdf_text(client, params):
    r = client.get("/api/report.pdf", params=params)
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    return reader, " ".join(p.extract_text() for p in reader.pages), r.content


@respx.mock
def test_pdf_brand_no_qr_by_default_and_qr_with_public_url(client, long_weather, monkeypatch):
    settings.terrain_saved_results = True
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    q = {"parcel_id": PID, "date": "2018-11-21"}
    monkeypatch.setattr(settings, "public_url", "")
    reader, text, _ = _pdf_text(client, q)
    assert "WODOSKOP" in text.upper() and "prześwietl swoją działkę pod kątem suszy" in text
    assert "ZATRZYMAJ WODĘ" not in text and "Zeskanuj" not in text  # nazwa produktu (nie zdanie „zatrzymaj wodę z opadów”)
    assert "Wodoskop · Raport ma charakter pomocniczy" in " ".join(text.split())
    meta = reader.metadata
    assert "Wodoskop" in (meta.title or "") and meta.author == "Wodoskop"
    monkeypatch.setattr(settings, "public_url", "https://wodoskop.example")
    _, text2, _ = _pdf_text(client, q)
    assert "Zeskanuj – analiza online" in " ".join(text2.split())


@respx.mock
def test_pdf_approximate_area_has_no_technical_messages(client, long_weather):
    mock_all()
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(302, headers={"location": "https://x/resp"}))
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    _, text, _ = _pdf_text(client, {"lon": 22.6021, "lat": 53.0500, "date": "2018-11-21"})
    flat = " ".join(text.split())
    assert "Ewidencja gruntów chwilowo nie odpowiada – pokazuję obszar ok. 1 ha." in flat  # P1: nota przy awarii ULDK
    for bad in ("ponowna próba", "przekierowanie", "ogranicza ruch", "ULDK GUGiK: usługa"):
        assert bad not in flat, bad
