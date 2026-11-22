"""A5b-1: nawadnianie zgodne z praktyką, tylko potwierdzone ekoschematy, status poza sezonem, zgodność gleby,
stan działki bez uprawy (/api/analysis i /api/report.pdf) – bez sieci."""

import io
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
import yaml
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.analysis.confidence import PENALTY, premises
from app.analysis.crops import CROPS, IRRIGATION_PRACTICE, get_crop, no_irrigation_sentence
from app.analysis.field_state import REFERENCE_KC, field_state_model, series_start
from app.analysis.recommendations import ALLOWED_ECO_CODES, ECO_SCHEMES, RULES_DIR, RuleError, _validate, evaluate, load_rules
from app.analysis.scoring import overall_status, reserve_score
from app.analysis.soil import assess_soil
from app.analysis.soil_consistency import MapSummary, apply, assess, species_category, summarize_map
from app.analysis.soil_texture import texture
from app.analysis.water_balance import recent_balance, soil_water_model
from app.core.config import settings
from app.main import app
from app.schemas.analysis import AnalysisResponse
from app.sources import iung, kieg, soil_map, soilgrids, uldk, weather_openmeteo, weather_power
from app.sources.iung import SoilResult
from app.sources.soil_map import parse_response
from app.sources.soilgrids import SoilGridsResult
from test_a5 import mock_all, stress_facts
from test_analysis import SOIL_MAP, SOIL_OK, facts
from test_water_model import WOD, _dry_2018, _et0_seasonal, _wet, synth

Q = {"parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-06-10"}
NO_CROP = {"parcel_id": "201305_2.0038.6/1", "date": "2018-06-10"}
LIGHT_MAP = SOIL_MAP.replace('PODLOZE1="glp"', 'PODLOZE1="pgl"').replace('KOMPLEKS="2"', 'KOMPLEKS="6"')


@pytest.fixture(autouse=True)
def _clean():
    for m in (iung, kieg, uldk, weather_power, soilgrids, soil_map):
        m.clear_cache()
    weather_openmeteo.clear_archive_cache()
    weather_openmeteo.clear_cache()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── 1. nawadnianie zgodne z praktyką ────────────────────────────────────────────────────────


def test_irrigation_practice_for_every_crop():
    assert set(IRRIGATION_PRACTICE) == set(CROPS)
    assert all(c.irrigation_practice in ("not_practiced", "optional", "common") for c in CROPS.values())
    for cid in ("zboza_ozime", "zboza_jare", "rzepak", "rzepak_jesien"):
        assert CROPS[cid].irrigation_practice == "not_practiced"
    for cid in ("kukurydza_ziarno", "kukurydza_kiszonka", "ziemniak"):  # A5e (D76): ziemniak optional
        assert CROPS[cid].irrigation_practice == "optional"
    for cid in ("warzywa", "drzewa_owocowe", "krzewy_owocowe", "truskawki"):
        assert CROPS[cid].irrigation_practice == "common"
    assert no_irrigation_sentence(CROPS["zboza_ozime"]) == "Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie"
    assert no_irrigation_sentence(CROPS["warzywa"]) is None


def test_not_practiced_crop_has_no_irrigation_plan_in_drought():
    w = synth(date(2006, 8, 1), date(2018, 6, 9), _dry_2018, _et0_seasonal)
    r = soil_water_model(w, get_crop("zboza_ozime"), WOD, date(2018, 6, 10), soil_category=3)
    assert r.sensitive and r.days_to_stress is not None and r.days_to_stress <= 7  # stres jest…
    assert r.irrigation.status == "nie_praktykowane" and r.irrigation.dose_mm is None  # …ale bez dawek
    assert r.irrigation.message.startswith("Zbóż w Polsce się nie nawadnia")


def test_engine_never_recommends_irrigation_for_not_practiced():
    f = stress_facts(irrigation_practice="not_practiced", water_stress_7d=True, stress_when_txt=" – rośliny już odczuwają brak wody",
                     no_irrigation_txt="Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie",
                     et0_recent_mm_day=4.8)
    recs = evaluate(f, limit=False).recommendations
    assert recs and not any(r.category == "nawadnianie" for r in recs)
    ids = {r.id for r in recs}
    assert {"retencja.bez_nawadniania_zatrzymaj_wode", "agrotechnika.bez_nawadniania_parowanie",
            "agrotechnika.bez_nawadniania_termin_zabiegow"} <= ids
    first = next(r for r in recs if r.id == "retencja.bez_nawadniania_zatrzymaj_wode")
    assert "Zbóż w Polsce się nie nawadnia – liczy się zatrzymanie wody w glebie" in first.description
    panel = [r for r in evaluate(f).recommendations if r.in_panel]
    assert panel[0].id == "retencja.bez_nawadniania_zatrzymaj_wode"
    # te same dane dla uprawy nawadnianej – plan dawek jest
    irrigated = evaluate(stress_facts(irrigation_practice="common"), limit=False).recommendations
    assert any(r.category == "nawadnianie" for r in irrigated)


@respx.mock
def test_drought_2018_winter_cereals_zero_irrigation(client):
    """Kontrola z zadania: „Susza 2018” (zboża ozime, 10.06.2018) → ZERO zaleceń nawadniania."""
    mock_all()
    b = client.get("/api/analysis", params={**Q, "previous_crop": "zboza_ozime"}).json()
    assert b["irrigation"]["status"] == "nie_praktykowane" and b["irrigation"]["practice"] == "not_practiced"
    assert b["irrigation"]["dose_mm"] is None
    assert not any(r["category"] == "nawadnianie" for r in b["recommendations"])
    assert not any("awadnia" in r["title"] and "nie nawadnia" not in r["description"] for r in b["recommendations"])


# ── 2. ekoschematy – tylko potwierdzone kody ────────────────────────────────────────────────


def test_eco_schemes_only_confirmed_codes():
    assert set(ALLOWED_ECO_CODES) == {"E_MPW", "E_USU", "E_WSG", "E_PN", "E_MIOD", "E_EKSTUZ"}
    assert set(ECO_SCHEMES) == set(ALLOWED_ECO_CODES) and all(e.code in ALLOWED_ECO_CODES for e in ECO_SCHEMES.values())
    for path in sorted(Path(RULES_DIR).glob("*.yaml")):  # surowy YAML, nie tylko wczytane reguły
        for raw in yaml.safe_load(path.read_text(encoding="utf-8")).get("rules") or []:
            assert raw.get("eco_scheme") in (None, *ALLOWED_ECO_CODES), (path.name, raw["id"])
    assert all(r.eco_scheme in (None, *ALLOWED_ECO_CODES) for r in load_rules())
    by_id = {r.id: r for r in load_rules()}
    assert by_id["agrotechnika.odloz_nawozenie"].eco_scheme is None
    for bad in ("E_ZSU", "PLAN_NAWOZENIA", "TUZ_RETENCJA"):
        with pytest.raises(RuleError):
            _validate({"id": "t", "category": "retencja", "priority": 1, "title": "T", "description": "D",
                       "when": {"all": [{"fact": "month", "gte": 1}]}, "eco_scheme": bad}, "test.yaml")


# ── 3. status poza sezonem ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("phase", "scope"), [("po_zbiorze", "poza_sezonem"), ("przed_siewem", "poza_sezonem"),
                                              ("spoczynek_zimowy", "zimowanie"), ("wschody_jesienne", "zimowanie")])
def test_off_season_status_from_soil_water_and_recent_balance(phase, scope):
    """Poza fazami uprawy status z zapasu wody i bilansu 30 dni (A5b-2a: na tle tej samej daty w 10 latach, D65) –
    bez kar za stres i historię sezonu uprawy."""
    f = facts(crop="kukurydza_ziarno", phase=phase, phase_label=phase, sensitive=False, water_pct=80.0, water_mm=150.0,
              days_to_stress=0, risk="wysokie", balance_percentile=0.0, water_rank_pct=0.0,
              stress_days_season=60, kbw30_percentile=70.0)
    s = overall_status(f, SOIL_OK)
    assert s.scope == scope and s.level == "ok" and s.score >= 70
    assert "cierpią" not in s.headline and "zapas wody w glebie" in s.summary
    assert "Bilans wody z ostatnich 30 dni (opad minus parowanie)" in s.summary
    assert reserve_score(80.0, 70.0) == round(0.6 * 80 + 0.4 * 70)  # zapas, gdy brak lat porównawczych (D52)


def test_in_season_status_scope():
    s = overall_status(facts(), SOIL_OK)
    assert s.scope == "sezon" and s.scope_label == "w sezonie"


def test_recent_balance_30_days():
    w = synth(date(2006, 8, 1), date(2018, 11, 20), _wet, _et0_seasonal)
    rb = recent_balance(w, date(2018, 11, 21))
    assert rb.until == date(2018, 11, 20) and rb.start == date(2018, 10, 22) and rb.of_years == 10
    assert rb.balance_mm == pytest.approx(10 * (4.5 - 1.5) + 20 * (4.5 - 0.5), abs=0.1)
    assert rb.deviation_mm == pytest.approx(0, abs=0.1) and rb.lower_years == 0


# ── 4. spójność gleby ───────────────────────────────────────────────────────────────────────


def _iung(counts: dict[int, int]):
    return assess_soil(SoilResult(counts=counts, method="wcs"))


def _sg(sand, silt, clay):
    return texture(SoilGridsResult(sand_pct=sand, silt_pct=silt, clay_pct=clay, soc_g_kg=20.0, lon=22.6, lat=52.9))


def test_species_category_parse():
    assert species_category("pgl") == 2 and species_category("ps") == 1 and species_category("glp") == 3
    assert species_category("gs") == 4 and species_category("pgl.ps") == 2 and species_category("xyz") is None


def test_conflict_map_light_vs_iung_cat3():
    """Przypadek z zadania (201305): IUNG kat. III, mapa glebowo-rolnicza i SoilGrids – gleba lekka."""
    soil = _iung({3: 75, 1: 25})
    m = summarize_map([parse_response(LIGHT_MAP)] * 5)
    c = assess(soil, m, _sg(66.5, 24.4, 9.1))
    assert c.contract.status == "conflict" and c.conflict and c.contract.basis == "mapa_glebowo_rolnicza"
    assert c.category_used == 2 and c.wod_used == pytest.approx(148.7)
    assert "Źródła się różnią" in c.contract.note and "sprawdź glebę na polu" in c.contract.note
    assert "też wskazuje glebę lekką" in c.contract.note
    assert [v.source for v in c.contract.by_source] == ["mapa_glebowo_rolnicza", "iung", "soilgrids"]
    apply(soil, c)
    assert soil.wod_mm == pytest.approx(148.7) and soil.dominant_mineral == 2 and soil.soil_capacity.value == 149


def test_parcel_on_two_soil_contours_is_not_a_conflict():
    """Prawdziwy przypadek 201305 (badanie A5b-1): 3 z 8 punktów mapy – piasek gliniasty lekki (kompleks 6),
    5 – glina lekka pylasta (kompleks 2); IUNG: 75% kat. III, 25% kat. I. Źródła zgodne, dwie gleby."""
    soil = _iung({3: 75, 1: 25})
    m = summarize_map([parse_response(LIGHT_MAP)] * 3 + [parse_response(SOIL_MAP)] * 5)
    assert m.light_share == pytest.approx(3 / 8) and m.category == 3
    c = assess(soil, m, _sg(66.5, 24.4, 9.1))
    assert c.contract.status == "ok" and not c.substituted and c.wod_used == soil.wod_mm
    assert "dwie gleby" in c.contract.note and "SoilGrids" in c.contract.note
    assert "piasek gliniasty lekki" in c.contract.by_source[0].description


def test_sources_agree_keep_iung_wod():
    soil = _iung({3: 100})
    c = assess(soil, summarize_map([parse_response(SOIL_MAP)]), _sg(30, 52, 18))
    assert c.contract.status == "ok" and not c.substituted and c.wod_used == soil.wod_mm and c.category_used == 3
    assert c.contract.note.startswith("Źródła zgodne")


def test_without_map_iung_beats_soilgrids():
    soil = _iung({3: 100})
    c = assess(soil, MapSummary(None, {}, 0, 5, None), _sg(85, 10, 5))
    assert c.contract.status == "conflict" and c.contract.basis == "iung" and not c.substituted
    assert c.wod_used == soil.wod_mm


def test_non_agricultural_contour_on_map_ignored():
    forest = SOIL_MAP.replace('KOMPLEKS="2"', 'KOMPLEKS="Ls"')
    m = summarize_map([parse_response(forest)])
    assert m.category is None and m.valid == 0


def test_conflict_lowers_confidence():
    from test_analysis import _conf
    assert "gleba_konflikt" in {p.key for p in premises(_conf(soil_conflict=True))}
    assert PENALTY["gleba_konflikt"] > 0


@respx.mock
def test_analysis_soil_conflict_endpoint(client):
    mock_all()
    respx.get(settings.soil_map_url).mock(return_value=httpx.Response(200, text=LIGHT_MAP))
    b = client.get("/api/analysis", params=Q).json()
    k = b["soil"]["consistency"]
    assert k["status"] == "conflict" and k["basis"] == "mapa_glebowo_rolnicza" and k["category_used"] == 2
    assert b["soil"]["wod_mm"] == pytest.approx(148.7) and b["indicators"]["soil_capacity"]["value"] == 149
    assert b["soil"]["dominant_code"] == 3  # sekcja IUNG bez zmian
    assert any("źródła gleby się różnią" in x for x in b["reliability"]["limitations"])


@respx.mock
def test_analysis_soil_consistent_endpoint(client):
    mock_all()
    b = client.get("/api/analysis", params=Q).json()
    assert b["soil"]["consistency"]["status"] == "ok" and b["soil"]["wod_mm"] == 166.2


# ── 5. stan działki bez uprawy ──────────────────────────────────────────────────────────────


def test_series_start_hydrological_year():
    assert series_start(date(2018, 6, 9)) == date(2017, 11, 1)
    assert series_start(date(2026, 11, 20)) == date(2025, 11, 1)  # < 30 dni od 1 XI – rok wcześniej
    assert series_start(date(2026, 12, 15)) == date(2026, 11, 1)


def test_field_state_model_reference_cover():
    w = synth(date(2006, 8, 1), date(2018, 6, 9), _dry_2018, _et0_seasonal)
    r = field_state_model(w, WOD, date(2018, 6, 10))
    assert REFERENCE_KC == 1.0 and r.status == "ok" and r.series_start == date(2017, 11, 1)
    assert r.series[0][0] == date(2017, 11, 1) and r.series[-1][0] == date(2018, 6, 9)
    assert r.water_pct == round(r.series[-1][1]) and 0 <= r.water_pct < 50  # sucha wiosna 2018
    assert r.rank_of == 10 and r.rank_lower == 0 and len(r.band) == len(r.series)
    wet = field_state_model(synth(date(2006, 8, 1), date(2018, 6, 9), _wet, _et0_seasonal), WOD, date(2018, 6, 10))
    assert wet.water_pct > r.water_pct


@respx.mock
def test_analysis_without_crop(client):
    mock_all()
    r = client.get("/api/analysis", params=NO_CROP)
    assert r.status_code == 200, r.text
    a = AnalysisResponse.model_validate(r.json())
    assert a.crop is None and a.crop_season is None and a.irrigation is None and a.suggestions is None
    assert a.status.scope == "bez_uprawy" and a.status.scope_label == "stan wody na działce"
    assert a.status.level in ("ok", "warn", "risk", "danger") and a.status.score is not None
    f = a.field_state
    assert f is not None and f.series_start == date(2017, 11, 1) and f.series and f.series[-1].date == date(2018, 6, 9)
    assert f.soil_water_pct.value == a.indicators.soil_water_pct.value and a.soil_water.scope == "profil"
    assert f.balance_30d.value is not None and "typowego pola" in f.cover and "FAO-56" in f.soil_water_mm.source_tag.source and f.status == a.status
    assert a.indicators.risk_7d.label == "Nie dotyczy" and a.history.stress_days_by_year == []
    assert a.soil.consistency is not None and a.soil.wod_mm == 166.2
    assert a.recommendations and all(x.category == "retencja" for x in a.recommendations)
    assert "retencja.dzialka_wiosna" in {x.id for x in a.recommendations}
    assert not any(c.factor == "uprawa" for c in a.causes)


@respx.mock
def test_analysis_with_crop_also_has_field_state(client):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params=Q).json())
    assert a.field_state is not None and a.field_state.status.scope == "bez_uprawy" and a.status.scope == "sezon"


@respx.mock
def test_analysis_without_crop_non_agricultural(client):
    mock_all()
    from test_analysis import WCS_201305
    forest = WCS_201305.split("Band 0:")[0] + "Band 0:\n" + "\n".join(" ".join(["11"] * 26) for _ in range(16)) + "\n"
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=forest))
    b = client.get("/api/analysis", params=NO_CROP).json()
    assert b["status"]["level"] == "no_data" and b["field_state"] is None and b["recommendations"] == []


@respx.mock
def test_report_pdf_without_crop(client):
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    r = client.get("/api/report.pdf", params=NO_CROP)
    assert r.status_code == 200, r.text
    assert 'filename="stan-wodny-dzialki-201305_2.0038.6-1-2018-06-10-skrocony.pdf"' in r.headers["content-disposition"]
    reader = PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() for p in reader.pages)
    for phrase in ("Werdykt działki", "Raport skrócony", "Co tu posiać?", "Co zrobić z wodą", "Na tle 10 lat"):
        assert phrase in text, phrase
    assert "Paszport wodny" not in text and "Dni stresu" not in text
    assert len(reader.pages) == 2  # A5e-2: raport skrócony = dokładnie 2 strony
    full = client.get("/api/report.pdf", params={**NO_CROP, "report_type": "full"})
    tf = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(full.content)).pages)
    for phrase in ("Raport szczegółowy", "Woda na działce", "stan wody na działce", "Gleba, teren i skąd dane", "Skąd te dane"):
        assert phrase in tf, phrase


def test_unknown_crop_still_422(client):
    r = client.get("/api/analysis", params={"parcel_id": "x", "crop": "banany"})
    assert r.status_code == 422
