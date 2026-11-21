"""A5 część B: przykłady demo, rozgrzewka cache, /api/status, raport PDF, odporność ULDK – bez sieci."""

import asyncio
import io
import struct
import zlib
from datetime import date

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import demo
from app.core.config import settings
from app.core.http import NotFoundError, SourceError
from app.main import app
from app.report.builder import analysis_url, filename, render_html
from app.schemas.analysis import AnalysisResponse
from app.sources import uldk
from test_a5 import ALL_CACHED, mock_all
from test_analysis import ULDK_ONE

Q = {"parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-06-10", "previous_crop": "zboza_ozime"}


@pytest.fixture(autouse=True)
def _clean():
    for m in ALL_CACHED:
        m.clear_cache()
    demo.reset_state()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def png_1x1() -> bytes:
    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x40\x80\x40")) + chunk(b"IEND", b""))


# ── B1: przykłady ───────────────────────────────────────────────────────────────────────────


def test_demo_examples(client):
    r = client.get("/api/demo/examples")
    assert r.status_code == 200
    ex = {e["id"]: e for e in r.json()}
    assert list(ex) == ["susza-2018", "mokry-rok-2021", "kukurydza-dzis", "to-nie-jest-pole"]
    assert ex["susza-2018"] == {
        "id": "susza-2018", "title": "Susza 2018", "description": ex["susza-2018"]["description"],
        "parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-06-10", "previous_crop": "zboza_ozime",
    }
    assert ex["mokry-rok-2021"]["date"] == "2021-07-15" and ex["mokry-rok-2021"]["previous_crop"] is None
    today = date.today().isoformat()
    assert ex["kukurydza-dzis"]["date"] == today and ex["kukurydza-dzis"]["crop"] == "kukurydza_ziarno"
    assert ex["to-nie-jest-pole"]["parcel_id"] == "143203_2.0027.112/11" and ex["to-nie-jest-pole"]["date"] == today
    # tylko parametry – żadnych zapisanych wyników
    assert not any(k in e for e in r.json() for k in ("status", "recommendations"))


# ── B2: rozgrzewka ──────────────────────────────────────────────────────────────────────────


@respx.mock
def test_warmup_runs_examples_through_normal_analysis(monkeypatch):
    mock_all()
    respx.get(settings.open_meteo_forecast_url).mock(return_value=httpx.Response(503))
    monkeypatch.setattr(settings, "demo_warmup", True)
    states = asyncio.run(demo.warmup_once())
    assert [s.id for s in states] == [e.id for e in demo.EXAMPLES]
    assert all(s.state == "gotowe" and s.duration_ms is not None and s.finished_at for s in states), states
    assert len(uldk._cache) >= 1 and len(demo.warmup_state()) == 4  # dane źródeł trafiły do cache


@respx.mock
def test_warmup_error_does_not_crash(monkeypatch):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(503))
    monkeypatch.setattr(settings, "demo_warmup", True)
    states = asyncio.run(demo.warmup_once())
    assert all(s.state == "blad" and "ULDK" in s.error for s in states)


def test_warmup_disabled_state():
    assert settings.demo_warmup is False  # conftest: DEMO_WARMUP=false
    assert {s.state for s in demo.warmup_state()} == {"wylaczona"}


# ── B4: /api/status ─────────────────────────────────────────────────────────────────────────


def _mock_probes(fail: str | None = None):
    urls = [settings.uldk_url, settings.nasa_power_url, settings.open_meteo_forecast_url, settings.iung_wms_url,
            settings.kieg_url, settings.soilgrids_url, settings.soil_map_url, settings.nmt_url]
    for u in urls:
        body = "0\n201305_2.0038.6/1\n" if u == settings.uldk_url else "{}"
        respx.get(u).mock(return_value=httpx.Response(503) if u == fail else httpx.Response(200, text=body))


@respx.mock
def test_status_all_ok(client):
    _mock_probes()
    b = client.get("/api/status").json()
    assert b["all_ok"] is True and len(b["services"]) == 8
    names = [s["name"] for s in b["services"]]
    assert names[:3] == ["ULDK GUGiK", "NASA POWER", "Open-Meteo"] and "SoilGrids (ISRIC)" in names
    assert all(s["response_ms"] is not None and s["cache_entries"] >= 0 for s in b["services"])
    assert b["warmup_enabled"] is False and len(b["warmup"]) == 4


@respx.mock
def test_status_reports_failing_source(client):
    _mock_probes(fail=settings.soilgrids_url)
    b = client.get("/api/status").json()
    sg = next(s for s in b["services"] if s["name"] == "SoilGrids (ISRIC)")
    assert b["all_ok"] is False and sg["ok"] is False and "503" in sg["error"]


@respx.mock
def test_status_shows_cache_age(client):
    mock_all()
    client.get("/api/analysis", params=Q)
    _mock_probes()
    b = client.get("/api/status").json()
    nasa = next(s for s in b["services"] if s["name"] == "NASA POWER")
    assert nasa["cache_entries"] >= 1 and nasa["cache_newest_age_s"] is not None and nasa["cache_newest_age_s"] < 60


# ── odporność ULDK: przekierowanie = chwilowa niedostępność, nie „brak działki” ─────────────


@respx.mock
def test_uldk_redirect_is_retried():
    route = respx.get(settings.uldk_url)
    route.side_effect = [httpx.Response(302, headers={"location": "https://integracja01.gugik.gov.pl/resp/uldk.php"}),
                         httpx.Response(200, text=ULDK_ONE)]
    parcels = asyncio.run(uldk.by_id("201305_2.0038.6/1"))
    assert parcels[0].id == "201305_2.0038.6/1" and route.call_count == 2


@respx.mock
def test_uldk_persistent_redirect_is_source_error():
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(302, headers={"location": "https://x/resp/uldk.php"}))
    with pytest.raises(SourceError) as e:
        asyncio.run(uldk.by_id("201305_2.0038.6/1"))
    assert not isinstance(e.value, NotFoundError) and "ogranicza ruch" in e.value.message


# ── B5: raport PDF ──────────────────────────────────────────────────────────────────────────


def _pdf_text(pdf: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


@respx.mock
def test_report_pdf_with_polish_text(client):
    mock_all()
    ortho = respx.get(settings.ortho_wms_url).mock(
        return_value=httpx.Response(200, content=png_1x1(), headers={"content-type": "image/png"}))
    r = client.get("/api/report.pdf", params=Q)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert 'filename="paszport-wodny-201305_2.0038.6-1-2018-06-10.pdf"' in r.headers["content-disposition"]
    assert int(r.headers["x-generation-ms"]) < 10_000
    assert ortho.called
    text = _pdf_text(r.content)
    for phrase in ("Werdykt działki", "Woda na działce", "Co zrobić z wodą", "Skąd te dane", "Gleba, teren i skąd dane",
                   "Dlaczego?", "Raport ma charakter pomocniczy", "Zboża ozime", "glina lekka pylasta", "Na tle 10 lat"):
        assert phrase in text, phrase
    assert "ż" in text and "ą" in text and "ł" in text and "ę" in text  # polskie znaki w tekście PDF
    pages = len(PdfReader(io.BytesIO(r.content)).pages)
    assert 3 <= pages <= 5


@respx.mock
def test_report_pdf_without_orthophoto(client):
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    r = client.get("/api/report.pdf", params=Q)
    assert r.status_code == 200 and "Ortofotomapa niedostępna" in _pdf_text(r.content)


@respx.mock
def test_report_errors_like_analysis(client):
    r = client.get("/api/report.pdf", params={"parcel_id": "x", "crop": "banany"})
    assert r.status_code == 422 and "Nieznana uprawa" in r.json()["detail"]["message"]


@respx.mock
def test_report_html_sections_and_qr(client):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params=Q).json())
    html = render_html(a, ortho=None, report_type="full")
    for sec in ("Woda na działce", "Na tle 10 lat", "Dlaczego?", "Co zrobić z wodą", "Gleba, teren i skąd dane",
                "Skąd te dane", "Szczegóły techniczne"):
        assert sec in html
    assert "<svg" in html and "polygon" in html  # wykresy i obrys działki
    url = analysis_url(a)
    assert url.startswith(settings.public_url) and "dzialka=201305_2.0038.6%2F1" in url and "przedplon=zboza_ozime" in url
    assert filename(a).endswith(".pdf")
    for r in a.recommendations:  # każda rekomendacja z formalnościami i terminem
        assert r.permit_note in html and r.when_label in html
