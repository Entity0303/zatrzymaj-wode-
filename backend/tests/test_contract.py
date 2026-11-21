"""Kontrakt API: backend/app/schemas ↔ frontend/src/api/types.ts – bez sieci.

Przykład z frontendu (frontend/src/mocks/analysis.sample.json) musi przejść walidację Pydantic;
modele mają extra="forbid", więc pole dodane tylko po jednej stronie wywraca test.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.analysis import AnalysisResponse

SAMPLE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "mocks" / "analysis.sample.json"
SAMPLE_NO_CROP = SAMPLE.with_name("analysis.no-crop.sample.json")
SAMPLE_HISTORY = SAMPLE.with_name("analysis.no-crop-history.sample.json")
TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "types.ts"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.skipif(not SAMPLE.exists(), reason="brak katalogu frontend/ obok backend/")
@pytest.mark.parametrize("sample", [SAMPLE, SAMPLE_NO_CROP, SAMPLE_HISTORY], ids=["z_uprawa", "bez_uprawy", "z_historia"])
def test_frontend_sample_matches_contract(sample):
    data = json.loads(sample.read_text(encoding="utf-8"))
    a = AnalysisResponse.model_validate(data)
    if sample == SAMPLE_HISTORY:  # A5b-2a: ranking z historią pola i podaną powierzchnią
        assert a.crop_history == ["pszenica_ozima", "rzepak"] and a.cultivated_area_ha == 0.5
        rank = {i.crop_id: i for g in a.suggestions.groups for i in g.items}
        assert rank["rzepak"].category == "odradzane" and rank["rzepak"].rotation.status == "naruszenie"
        assert not a.suggestions.area.estimated
    if sample != SAMPLE:
        assert a.suggestions is not None and {g.key for g in a.suggestions.groups} <= {"polowe", "wieloletnie"}
    if sample == SAMPLE_NO_CROP:  # A5b-1: odpowiedź bez uprawy
        assert a.crop is None and a.crop_season is None and a.irrigation is None and a.field_state is not None
    # zasady z kontraktu
    cats = [r.category for r in a.recommendations]
    order = ["retencja", "agrotechnika", "nawadnianie"]
    assert cats == sorted(cats, key=order.index), "kolejność: retencja → agrotechnika → nawadnianie"
    assert a.indicators.crop_health.source_tag.kind != "satelita" or a.indicators.crop_health.source_tag.date
    assert all(0 <= c.share <= 1 for c in a.causes)


@pytest.mark.skipif(not TYPES_TS.exists(), reason="brak katalogu frontend/ obok backend/")
@pytest.mark.skipif(not SAMPLE.exists(), reason="brak katalogu frontend/ obok backend/")
@pytest.mark.parametrize("layer", ["teren", "splyw"])
def test_layer_samples_match_contract(layer):
    """A6: przykłady warstw mapy (mocks/layers.*.sample.json) – LayerResponse + properties kind/color/label."""
    from app.schemas.layers import LayerResponse

    data = json.loads(SAMPLE.with_name(f"layers.{layer}.sample.json").read_text(encoding="utf-8"))
    r = LayerResponse.model_validate(data)
    assert r.layer == layer and r.features["type"] == "FeatureCollection" and r.features["features"]
    for f in r.features["features"]:
        assert {"kind", "color", "label"} <= set(f["properties"])


@pytest.mark.skipif(not SAMPLE.exists(), reason="brak katalogu frontend/ obok backend/")
def test_samples_have_terrain_section():
    a = AnalysisResponse.model_validate(json.loads(SAMPLE.read_text(encoding="utf-8")))
    assert a.terrain is not None and len(a.terrain.zones) == 4


def test_ts_types_name_every_contract_field():
    """Każde pole modeli odpowiedzi analizy występuje w types.ts (prosta kontrola rozjazdu)."""
    ts = TYPES_TS.read_text(encoding="utf-8")
    seen: set[type] = set()

    def walk(model):
        if model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            assert f"{name}:" in ts or f"{name}?:" in ts, f"pole '{name}' z {model.__name__} brak w types.ts"
            ann = field.annotation
            for sub in getattr(ann, "__args__", ()) or (ann,):
                inner = getattr(sub, "__args__", (sub,))
                for t in inner:
                    if isinstance(t, type) and hasattr(t, "model_fields"):
                        walk(t)
            if isinstance(ann, type) and hasattr(ann, "model_fields"):
                walk(ann)

    walk(AnalysisResponse)


def test_analysis_crop_is_optional(client):
    # A5b-1: bez uprawy – „Stan działki” (scenariusze z mockami źródeł w test_a5b.py); tu bez sieci – tylko OpenAPI
    params = client.get("/openapi.json").json()["paths"]["/api/analysis"]["get"]["parameters"]
    crop = next(p for p in params if p["name"] == "crop")
    assert crop["required"] is False


def test_analysis_rejects_unknown_crop(client):
    r = client.get("/api/analysis", params={"parcel_id": "x", "crop": "banany"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/layers/kondycja?parcel_id=x"),
        ("get", "/api/layers/gleba/point?lon=20&lat=52"),
        ("post", "/api/reports"),
        ("get", "/api/infra-reports?lon_min=20&lat_min=52&lon_max=21&lat_max=53"),
    ],
)
def test_skeleton_endpoints_501(client, method, path):
    body = {"parcel_id": "x", "crop": "zboza_ozime", "date": "2026-06-15"} if method == "post" else None
    r = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
    assert r.status_code == 501


def test_openapi_exposes_contract(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for name in ("AnalysisResponse", "Indicators", "Recommendation", "Reliability", "Parcel", "Forecast"):
        assert name in schemas


SAMPLE_WEAK_VERDICT = SAMPLE.with_name("verdict.weak.sample.json")


@pytest.mark.skipif(not SAMPLE_WEAK_VERDICT.exists(), reason="brak katalogu frontend/ obok backend/")
def test_verdict_samples_match_contract():
    """A5b-2b: werdykt dobrej (201305, w analysis.sample.json) i słabej działki (piasek, obszar przybliżony)."""
    from app.schemas.analysis import ApproximateArea, Verdict

    good = AnalysisResponse.model_validate(json.loads(SAMPLE.read_text(encoding="utf-8"))).verdict
    assert good is not None and good.level in ("ok", "warn") and not good.crops_bad
    weak = json.loads(SAMPLE_WEAK_VERDICT.read_text(encoding="utf-8"))
    v = Verdict.model_validate(weak["verdict"])
    ApproximateArea.model_validate(weak["approximate_area"])
    assert v.level == "bad" and {"pszenica_ozima", "rzepak"} <= {c.crop_id for c in v.crops_bad}
    assert "zyto" in {c.crop_id for c in v.crops_good}


SAMPLE_CHOICE = SAMPLE.with_name("analysis.choice.sample.json")


@pytest.mark.skipif(not SAMPLE_CHOICE.exists(), reason="brak katalogu frontend/ obok backend/")
def test_choice_sample_matches_contract():
    """A5e: wybór rolnika (planned_crops) + słupki „Na tle 10 lat” – prawdziwa odpowiedź."""
    a = AnalysisResponse.model_validate(json.loads(SAMPLE_CHOICE.read_text(encoding="utf-8")))
    assert a.planned_crops == ["pszenica_ozima", "zboza_jare"] and a.suggestions.choice and a.suggestions.alternatives
    grp = next(c for c in a.suggestions.choice if c.requested_id == "zboza_jare")  # A5e-2: grupa → najlepszy gatunek
    assert grp.group_note and grp.crop_id in ("jeczmien_jary", "owies")
    assert a.suggestions.choice_summary and a.suggestions.top_ids
    assert len(a.seasonal_balance_by_year) == 11 and a.seasonal_balance_by_year[-1].current
    assert a.weather_data_until is not None and a.history.details
