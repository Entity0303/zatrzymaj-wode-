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
TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "types.ts"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.skipif(not SAMPLE.exists(), reason="brak katalogu frontend/ obok backend/")
@pytest.mark.parametrize("sample", [SAMPLE, SAMPLE_NO_CROP], ids=["z_uprawa", "bez_uprawy"])
def test_frontend_sample_matches_contract(sample):
    data = json.loads(sample.read_text(encoding="utf-8"))
    a = AnalysisResponse.model_validate(data)
    if sample == SAMPLE_NO_CROP:  # A5b-1: odpowiedź bez uprawy
        assert a.crop is None and a.crop_season is None and a.irrigation is None and a.field_state is not None
    # zasady z kontraktu
    cats = [r.category for r in a.recommendations]
    order = ["retencja", "agrotechnika", "nawadnianie"]
    assert cats == sorted(cats, key=order.index), "kolejność: retencja → agrotechnika → nawadnianie"
    assert a.indicators.crop_health.source_tag.kind != "satelita" or a.indicators.crop_health.source_tag.date
    assert all(0 <= c.share <= 1 for c in a.causes)


@pytest.mark.skipif(not TYPES_TS.exists(), reason="brak katalogu frontend/ obok backend/")
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
