"""A4: ocena stanu, pewność, przyczyny, silnik reguł i pełne /api/analysis – bez sieci."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis.causes import build_causes
from app.analysis.confidence import ConfidenceInputs, reliability
from app.analysis.facts import Facts
from app.analysis.recommendations import CATEGORY_ORDER, RuleError, _validate, evaluate, load_rules
from app.analysis.scoring import overall_status, risk_points, score_value, status_for
from app.analysis.soil import SoilAssessment, assess_soil
from app.core.config import settings
from app.core.http import SourceError
from app.main import app
from app.schemas.analysis import AnalysisResponse, Soil, SourceTag
from app.sources import iung, kieg, soil_map, soilgrids, uldk, weather_openmeteo, weather_power
from app.sources.iung import SoilResult

FIX = Path(__file__).parent / "fixtures"
NASA = json.loads((FIX / "nasa_power_2017_2018.json").read_text(encoding="utf-8"))
OM = json.loads((FIX / "open_meteo_archive_2017_2018.json").read_text(encoding="utf-8"))
WCS_201305 = (FIX / "iung_wcs_201305.txt").read_text(encoding="utf-8")
KIEG_CLASSES = (FIX / "kieg_201305_klasy.html").read_text(encoding="utf-8")
SOILGRIDS = json.loads((FIX / "soilgrids_201305.json").read_text(encoding="utf-8"))
SOIL_MAP = (FIX / "soil_map_201305.xml").read_text(encoding="utf-8")
WKT_201305 = (
    "POLYGON((741326.598870282 582135.860610104,741196.719087438 582172.956309767,"
    "741196.080461016 582126.579753392,741319.716303976 582092.766677043,"
    "741323.823760127 582113.17232317,741326.598870282 582135.860610104))"
)
ULDK_ONE = f"0\nSRID=2180;{WKT_201305}|201305_2.0038.6/1|podlaskie|powiat wysokomazowiecki|Kobylin-Borzymy|Wnory-Wandy|6/1\n"
SOIL_OK = Soil(dominant_code=3, dominant_label="Kat. III", shares=[], source_tag=SourceTag(kind="pomiar"))


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


def facts(**kw) -> Facts:
    base = {
        "crop": "zboza_ozime", "crop_label": "Zboża ozime", "crop_kind": "ozima", "month": 6, "phase": "pelnia",
        "phase_label": "pełnia rozwoju", "sensitive": True, "off_season": False, "season_complete": False,
        "non_agricultural": False, "soil_category": 3, "soil_category_roman": "III", "wod_mm": 186.0,
        "water_pct": 60.0, "water_mm": 100.0, "water_scope": "strefa_korzeni", "water_rank_pct": 50.0,
        "days_to_stress": None, "risk": "niskie", "stress_days_season": 0, "stress_days_mean": 5.0, "stress_ratio": 0.0,
        "kc": 1.15, "irrigation_status": "niepotrzebne", "irrigation_message": None, "irrigation_dose_mm": None,
        "irrigation_total_mm": None, "irrigation_when": None, "irrigation_confidence": "ograniczona",
        "balance_mm": -50.0, "balance_mean_mm": -40.0, "balance_deviation_mm": -10.0, "balance_percentile": 50.0,
        "longest_dry_spell_days": 7, "season_start_txt": "1 marca", "precip_mm": 150.0, "precip_mean_mm": 180.0,
        "precip_pct_of_mean": 83, "precip_deficit_mm": 30.0, "et0_mm": 220.0, "et0_mean_mm": 200.0,
        "et0_excess_mm": 20.0, "etc_mm_day": 4.6, "terrain": None, "water_nearby": None, "horizon_kind": "scenariusz",
        # A5
        "balance_vs_mean_txt": "o 10 mm mniej niż zwykle", "in_season": True, "strong_stress": False,
        "light_soil": False, "soil_txt": "kat. III", "crop_label_lower": "zboża ozime", "previous_crop": None,
        "previous_crop_label": None, "same_crop": None, "cereal_after_cereal": None, "rotation_issue": None,
        "rain_retention": None, "rain_retention_label": None, "ksat_mm_h": None, "sand_pct": None,
        "texture_label": None, "soil_species": None, "soil_complex_label": None,
        # A5b-1 (praktyka nawadniania – tu „optional”, żeby testy silnika obejmowały wszystkie kategorie)
        "has_crop": True, "irrigation_practice": "optional", "irrigation_practice_note": "", "water_stress_7d": False,
        "stress_when_txt": "", "no_irrigation_txt": None, "water_description": None, "water_rank_lower": 5,
        "water_rank_of": 10, "kbw30_mm": -20.0, "kbw30_percentile": 50.0, "kbw30_deviation_mm": -5.0,
        "kbw30_mean_mm": -15.0, "kbw30_vs_mean_txt": "o 5 mm mniej niż zwykle", "et0_recent_mm_day": 4.0,
    }
    base.update(kw)
    return Facts(base)


# ── ocena ───────────────────────────────────────────────────────────────────────────────────


def test_score_components_and_thresholds():
    assert risk_points(0) == 0 and risk_points(5) == 50 and risk_points(None) == 100
    assert score_value(facts()) == round(0.45 * 60 + 0.35 * 100 + 0.20 * 50)
    assert status_for(85, True) == "ok" and status_for(55, True) == "warn"
    assert status_for(35, True) == "risk" and status_for(10, True) == "danger"


def test_stressed_plants_alarm_in_sensitive_phase():
    s = overall_status(facts(water_pct=15.0, days_to_stress=0, balance_percentile=0.0, water_rank_pct=0.0), SOIL_OK)
    assert s.level == "danger" and s.score < 30 and "cierpią" in s.headline
    assert "15% wody dostępnej w strefie korzeni" in s.summary and "o 10 mm mniej niż zwykle" in s.summary
    assert "już odczuwają brak wody" in s.summary


@pytest.mark.parametrize("phase", ["dojrzewanie", "po_zbiorze", "spoczynek_zimowy", "przed_siewem"])
def test_no_plant_stress_alarm_outside_sensitive_phases(phase):
    s = overall_status(facts(phase=phase, phase_label=phase, sensitive=False, water_pct=5.0, days_to_stress=None,
                             balance_percentile=0.0, water_rank_pct=0.0), SOIL_OK)
    assert s.level == "risk"  # najwyżej „ryzyko” – nie „susza” roślin
    assert "zapas wody w glebie" in s.headline and "cierpią" not in s.headline
    assert "ocena dotyczy zapasu wody w glebie" in s.summary or "oceniamy zapas wody w glebie" in s.summary


def test_non_agricultural_no_score():
    soil = Soil(dominant_code=11, dominant_label="Las", shares=[], non_agricultural=True, non_agricultural_reason="las",
                non_agricultural_note="Według mapy gleb IUNG większość działki to las.", source_tag=SourceTag(kind="pomiar"))
    s = overall_status(facts(), soil)
    assert s.level == "no_data" and s.score is None and "las" in s.summary


# ── pewność ─────────────────────────────────────────────────────────────────────────────────


def _conf(**kw) -> ConfidenceInputs:
    base = dict(
        analysis_date=date(2018, 6, 10), today=date(2026, 11, 21), parcel_fetched=date(2026, 11, 21),
        weather_name="NASA POWER", weather_resolution="ok. 50 km", weather_fallback=False, weather_notes=[],
        weather_until=date(2018, 6, 9), forecast_ok=None, forecast_error=None,
        soil=assess_soil(SoilResult(counts={3: 100}, method="wcs")), model=None, wb=None, hg_share_season=0.0,
    )
    base.update(kw)
    return ConfidenceInputs(**base)


def test_confidence_capped_at_medium_without_satellite_and_terrain():
    rel, prem, pts = reliability(_conf())
    assert rel.confidence == "srednia" and pts >= 60
    assert {p.key for p in prem} >= {"satelita_brak", "teren_brak", "pogoda_nasa"}
    assert "brak zdjęć satelitarnych" in rel.reason
    names = [s.name for s in rel.sources]
    assert names[:2] == ["ULDK GUGiK", "NASA POWER"] and "Sentinel-2 L2A" in names
    assert rel.completeness.available < rel.completeness.total
    assert any("tylko gleby mineralne" in x for x in rel.limitations)


def test_confidence_lower_when_sources_fail():
    _, _, pts_ok = reliability(_conf())
    rel, _, pts = reliability(_conf(soil=assess_soil(SourceError("IUNG-PIB", "timeout"))))
    assert pts < pts_ok and rel.confidence == "ograniczona"
    _, _, pts_fb = reliability(_conf(weather_name="Open-Meteo archiwum", weather_fallback=True, weather_resolution="ok. 10–25 km"))
    assert pts_fb < pts_ok
    rel_fc, prem_fc, _ = reliability(_conf(analysis_date=date(2026, 11, 21), forecast_ok=False, forecast_error="429"))
    assert "prognoza_brak" in {p.key for p in prem_fc}
    assert any(s.name == "Open-Meteo (prognoza)" and s.status == "brak" for s in rel_fc.sources)


# ── przyczyny ───────────────────────────────────────────────────────────────────────────────


def test_causes_shares_sum_to_100_and_terrain_without_share():
    cs = build_causes(facts())
    assert sum(c.share for c in cs) == pytest.approx(1.0)
    assert cs[-1].factor == "teren" and cs[-1].share == 0 and cs[-1].source_tag.kind == "brak_danych"
    assert [c.share for c in cs[:-1]] == sorted([c.share for c in cs[:-1]], reverse=True)
    opady = next(c for c in cs if c.factor == "opady")
    assert "150 mm, zwykle 180 mm" in opady.description and opady.title == "Mało opadów"


def test_causes_wet_season_precip_share_zero():
    cs = build_causes(facts(precip_mm=250.0, et0_mm=180.0))
    assert next(c for c in cs if c.factor == "opady").share == 0
    assert sum(c.share for c in cs) == pytest.approx(1.0)


# ── silnik reguł ────────────────────────────────────────────────────────────────────────────


def test_rules_load_and_validate():
    rules = load_rules()
    assert 15 <= len(rules) <= 35
    assert {r.category for r in rules} == set(CATEGORY_ORDER)
    assert all(r.all or r.any for r in rules)  # każda reguła ma warunek
    with pytest.raises(RuleError):
        _validate({"id": "x", "category": "retencja", "priority": 1, "title": "t", "description": "d", "when": {}}, "t.yaml")


def test_autumn_rules_order_and_panel():
    f = facts(phase="po_zbiorze", phase_label="po zbiorze", sensitive=False, off_season=True, month=8,
              in_season=False, light_soil=True, soil_txt="kat. II",
              soil_category=2, soil_category_roman="II", wod_mm=148.7, water_pct=40.0, water_scope="profil",
              stress_days_season=30, stress_days_mean=12.0, stress_ratio=2.5, irrigation_status="nieuzasadnione_w_fazie")
    ev = evaluate(f)
    ids = [r.id for r in ev.all_matched]
    assert "retencja.nie_zostawiaj_scierniska" in ids and "retencja.prochnica" in ids
    assert "agrotechnika.odmiany_odporne" in ids
    cats = [r.category for r in ev.recommendations]
    assert cats == sorted(cats, key=CATEGORY_ORDER.index)  # retencja → agrotechnika → nawadnianie
    panel = [r for r in ev.recommendations if r.in_panel]
    assert len(panel) <= 3 and len({r.category for r in panel}) == len(panel)
    assert panel[0].id == "retencja.nie_zostawiaj_scierniska" and panel[0].when == "teraz"
    rec = next(r for r in ev.recommendations if r.id == "retencja.nie_zostawiaj_scierniska")
    assert "−50 mm" in rec.description and "40% wody" in rec.why and rec.inputs and "Dane:" in rec.why
    assert not any(r.category == "nawadnianie" for r in ev.recommendations)


def test_terrain_rules_disabled_until_data():
    ev = evaluate(facts())
    assert {"retencja.oczko_w_zaglebieniu", "retencja.zastawka_na_rowie", "retencja.pas_buforowy_na_stoku"} <= set(ev.disabled)
    ev2 = evaluate(facts(terrain_pond="glowna", pond_catchment_ha=1.2, pond_place_txt="w zagłębieniu",
                         pond_area_m2=80.0, pond_inflow_runoff_m3=70.0, pond_depth_m=0.6), available={"terrain"})
    assert "retencja.oczko_w_zaglebieniu" in [r.id for r in ev2.recommendations]


def test_no_recommendation_without_data():
    f = facts(**{k: None for k in ("soil_category", "water_pct", "balance_percentile", "days_to_stress", "stress_ratio",
                                   "balance_mm", "balance_vs_mean_txt", "light_soil", "strong_stress")},
              irrigation_status=None, wod_mm=None)
    for ph in ("po_zbiorze", "przed_siewem", "pelnia"):
        assert evaluate(Facts({**f.values, "phase": ph, "off_season": ph != "pelnia"})).recommendations == []


def test_irrigation_rule_uses_model_plan():
    f = facts(irrigation_status="zalecane", irrigation_message="27,5 mm teraz, powtórz za ok. 2 dni",
              irrigation_when="teraz", irrigation_confidence="srednia", days_to_stress=0)
    rec = next(r for r in evaluate(f).recommendations if r.category == "nawadnianie")
    assert rec.title == "Nawadnianie teraz" and rec.description.startswith("27,5 mm teraz")
    assert rec.confidence == "srednia" and rec.in_panel


# ── endpoint /api/analysis ──────────────────────────────────────────────────────────────────

Q = {"parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-06-10"}


def _mock(nasa=True, wcs=True):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(200, json=NASA) if nasa else httpx.Response(503))
    respx.get(settings.open_meteo_archive_url).mock(return_value=httpx.Response(200, json=OM))
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=WCS_201305) if wcs else httpx.Response(503))
    respx.get(settings.iung_wms_url).mock(return_value=httpx.Response(503))
    respx.get(settings.kieg_url).mock(return_value=httpx.Response(200, text=KIEG_CLASSES))
    respx.get(settings.soilgrids_url).mock(return_value=httpx.Response(200, json=SOILGRIDS))
    respx.get(settings.soil_map_url).mock(return_value=httpx.Response(200, text=SOIL_MAP))
    respx.post(settings.nmt_url).mock(return_value=httpx.Response(503))  # A6: bez NMT (teren = null)


@respx.mock
def test_analysis_success(client):
    _mock()
    r = client.get("/api/analysis", params=Q)
    assert r.status_code == 200, r.text
    a = AnalysisResponse.model_validate(r.json())
    assert a.crop == "zboza_ozime" and a.historical and a.crop_season.phase == "pelnia"
    assert a.status.level in ("ok", "warn", "risk", "danger") and a.status.score is not None
    assert a.indicators.soil_capacity.value == 166 and a.soil.classes == ["RIIIb", "RIVa", "RIVb"]
    assert a.indicators.crop_health.source_tag.kind == "brak_danych"
    assert sum(c.share for c in a.causes) == pytest.approx(1.0)
    cats = [x.category for x in a.recommendations]
    assert cats == sorted(cats, key=CATEGORY_ORDER.index) and sum(x.in_panel for x in a.recommendations) <= 3
    steps = {s.id: s for s in a.steps}
    assert steps["parcel"].state == "done" and steps["satellite"].state == "pending"
    # A6: NMT nie odpowiada (mock 503) – teren = null z powodem, analiza działa dalej
    assert steps["terrain"].state == "error" and a.terrain is None and "NMT GUGiK" in a.terrain_note
    assert steps["total"].duration_ms is not None and steps["total"].duration_ms < 30_000
    assert a.reliability.confidence in ("srednia", "ograniczona")


@respx.mock
def test_analysis_iung_down_no_crash(client):
    _mock(wcs=False)
    r = client.get("/api/analysis", params=Q)
    assert r.status_code == 200, r.text
    b = r.json()
    # A5b-1 (D49): bez IUNG kategoria i WOD z mapy glebowo-rolniczej (glina lekka pylasta – kat. III)
    assert b["indicators"]["soil_capacity"]["value"] == 186 and b["status"]["level"] != "no_data"
    assert b["soil"]["consistency"]["basis"] == "mapa_glebowo_rolnicza"
    assert b["reliability"]["confidence"] == "ograniczona"
    assert next(s for s in b["steps"] if s["id"] == "soil")["state"] == "error"


@respx.mock
def test_analysis_weather_fallback_open_meteo(client):
    _mock(nasa=False)
    b = client.get("/api/analysis", params=Q).json()
    assert any(s["name"] == "Open-Meteo archiwum" and s["status"] == "czesciowo" for s in b["reliability"]["sources"])
    assert next(s for s in b["steps"] if s["id"] == "weather")["note"] == "źródło zapasowe"


@respx.mock
def test_analysis_without_weather_is_502(client):
    _mock(nasa=False)
    respx.get(settings.open_meteo_archive_url).mock(return_value=httpx.Response(429))
    r = client.get("/api/analysis", params=Q)
    assert r.status_code == 502 and "NASA POWER" in r.json()["detail"]["source"]


@respx.mock
def test_analysis_non_agricultural(client):
    _mock()
    forest = WCS_201305.split("Band 0:")[0] + "Band 0:\n" + "\n".join(" ".join(["11"] * 26) for _ in range(16)) + "\n"
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=forest))
    b = client.get("/api/analysis", params=Q).json()
    assert b["status"]["level"] == "no_data" and b["soil"]["non_agricultural_reason"] == "las"
    assert b["recommendations"] == [] and b["causes"] == []
    assert "nie ma tu zastosowania" in b["status"]["summary"]


@pytest.mark.parametrize(
    ("params", "msg"),
    [
        ({"parcel_id": "x", "crop": "banany"}, "Nieznana uprawa"),
        ({"parcel_id": "x", "crop": "zboza_ozime", "date": "2999-01-01"}, "przyszłości"),
        ({"parcel_id": "x", "crop": "zboza_ozime", "date": "2001-01-01"}, "lat wstecz"),
    ],
)
def test_analysis_validation_422(client, params, msg):
    r = client.get("/api/analysis", params=params)
    assert r.status_code == 422 and msg in r.json()["detail"]["message"]


# ── test na żywo (pytest -m live -s) ────────────────────────────────────────────────────────


@pytest.mark.live
def test_live_full_analysis():
    import time

    today = date.today().isoformat()
    cases = [
        ("201305_2.0038.6/1", "zboza_ozime", "2018-06-10"),
        ("201305_2.0038.6/1", "zboza_ozime", today),
        ("061704_2.0011.383/2", "kukurydza_ziarno", "2021-07-15"),
        ("143203_2.0027.112/11", "zboza_ozime", today),
    ]
    with TestClient(app) as c:
        for pid, crop, d in cases:
            t0 = time.perf_counter()
            r = c.get("/api/analysis", params={"parcel_id": pid, "crop": crop, "date": d})
            sec = time.perf_counter() - t0
            assert r.status_code == 200, r.text
            b = r.json()
            print(f"\n===== {pid} · {crop} · {d} · {sec:.2f} s =====")
            st = b["status"]
            print(f"STATUS: {st['level']} ({st['score']}) – {st['headline']}\n  {st['summary']}")
            print("PRZYCZYNY: " + "; ".join(f"{c['title']} {round(c['share'] * 100)}% ({c['description']})" for c in b["causes"]))
            print("PANEL: " + " | ".join(f"[{x['category']}] {x['title']}: {x['description']}" for x in b["recommendations"] if x["in_panel"]))
            print(f"WSZYSTKIE REKOMENDACJE: {len(b['recommendations'])}")
            rel = b["reliability"]
            print(f"PEWNOŚĆ: {rel['confidence']} – {rel['reason']} (źródła {rel['completeness']['available']}/{rel['completeness']['total']})")
            print("OGRANICZENIA: " + " · ".join(rel["limitations"]))
            print("KROKI: " + ", ".join(f"{s['id']}={s['state']}" + (f" {s['duration_ms']} ms" if s['duration_ms'] is not None else "") for s in b["steps"]))
            assert sec < 30
