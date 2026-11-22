"""A26 – tło suszowe z Europejskiego Obserwatorium Suszy (EDO): kolory pikseli WMS → klasy, dekady, porównanie
z naszą oceną, błąd usługi. Bez sieci (atrapy odpowiedzi WMS)."""

import asyncio
import io
from datetime import date

import httpx
import pytest
import respx

from app.analysis import drought_context as DC
from app.core.http import SourceError
from app.sources import edo

T = (0, 0, 0, 0)            # przezroczysty – brak klasy w warstwie
WHITE = (255, 255, 255, 255)


def _png(rgba) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (1, 1), rgba).save(buf, format="PNG")
    return buf.getvalue()


def test_decades():
    assert DC.last_complete_decade(date(2018, 6, 30)) == date(2018, 6, 11)   # dekada 21–30.06 kończy się w dniu analizy
    assert DC.last_complete_decade(date(2018, 7, 1)) == date(2018, 6, 21)
    assert DC.last_complete_decade(date(2018, 7, 10)) == date(2018, 6, 21)
    assert DC.last_complete_decade(date(2026, 11, 22)) == date(2026, 11, 11)
    assert DC.last_complete_decade(date(2024, 3, 5)) == date(2024, 2, 21)
    assert DC.decade_end(date(2024, 2, 21)) == date(2024, 2, 29) and DC.decade_end(date(2018, 6, 11)) == date(2018, 6, 20)
    assert DC.decade_label(date(2018, 6, 11)) == "dekada 11–20.06.2018"


def test_colors_to_classes_and_sentence():
    ctx = DC.build(date(2018, 6, 11), (230, 159, 0, 255), T, (179, 88, 6, 255), (255, 205, 0, 255), date(2018, 6, 30), "danger")
    assert ctx.cdi.class_ == "ostrzeżenie" and ctx.cdi.label_pl == "ostrzeżenie przed suszą"
    assert ctx.soil_moisture_anomaly.label_pl == "bardzo sucho" and ctx.soil_moisture_anomaly.value == -2.5
    assert ctx.agri_risk.class_ == "srednie" and ctx.agrees is True
    assert ctx.sentence == ("Europejskie Obserwatorium Suszy dla tej okolicy: ostrzeżenie przed suszą "
                            "(dekada 11–20.06.2018) – zgodne z naszą oceną „Bardzo mało wody”.")
    d = ctx.model_dump(by_alias=True, mode="json")
    assert d["cdi"]["class"] == "ostrzeżenie" and d["cdi"]["date"] == "2018-06-11" and "siatka" in d["resolution_note"]
    assert d["source"] == "Copernicus European Drought Observatory (EDO), JRC" and d["unavailable"] is False

    none = DC.build(date(2026, 11, 11), T, WHITE, WHITE, T, date(2026, 11, 22), "Mało wody – mały zapas wody w glebie")
    assert none.cdi.class_ == "brak" and none.soil_moisture_anomaly.label_pl == "w normie" and none.agri_risk.class_ == "brak"
    assert none.agrees is False and "dotyczy tej jednej działki" in none.sentence and "brak suszy" in none.sentence
    rec = DC.build(date(2019, 9, 1), T, (204, 121, 167, 255), (200, 200, 200, 255), T, date(2019, 9, 15))
    assert rec.cdi.class_ == "regeneracja" and rec.soil_moisture_anomaly.label_pl == "brak danych" and rec.agrees is None
    assert rec.sentence.endswith("(dekada 1–10.09.2019).")
    assert edo.nearest((228, 160, 4), edo.CDI) == "ostrzeżenie" and edo.nearest((10, 200, 10), edo.CDI) is None


def test_our_level_from_key_or_headline():
    assert DC.our_level("danger") == "danger" and DC.our_level("Bardzo mało wody w glebie") == "danger"
    assert DC.our_level("Mało wody – rośliny odczuwają brak wody") == "risk" and DC.our_level("W normie – …") == "ok"
    assert DC.our_level(None) is None and DC.our_level("cokolwiek") is None


def test_context_steps_back_when_decade_missing_and_handles_errors(monkeypatch):
    calls = []

    async def fake_pixel(layer, lon, lat, time, today=None):
        calls.append((layer, time))
        if time == date(2026, 11, 11):
            return T  # dekada jeszcze nieopublikowana – wszystkie warstwy puste
        return {"cdiad": (220, 5, 12, 255), "cdirc": T, "smian": (254, 224, 182, 255), "rdria": (255, 0, 0, 255)}[layer]

    monkeypatch.setattr(edo, "pixel", fake_pixel)
    ctx = asyncio.run(DC.context(22.6, 53.05, date(2026, 11, 22), "ok"))
    assert ctx.cdi.class_ == "alarm" and ctx.cdi.date == date(2026, 11, 1) and ctx.agri_risk.class_ == "wysokie"
    assert ctx.soil_moisture_anomaly.label_pl == "sucho" and ctx.agrees is False and len(calls) == 8

    async def broken(layer, lon, lat, time, today=None):
        raise SourceError(edo.SOURCE, "usługa nie odpowiada")

    monkeypatch.setattr(edo, "pixel", broken)
    bad = asyncio.run(DC.context(22.6, 53.05, date(2026, 11, 22)))
    assert bad.unavailable and bad.note_pl == DC.UNAVAILABLE_NOTE and bad.cdi is None


@respx.mock
def test_pixel_reads_getmap_png_and_caches():
    route = respx.get(edo.WMS_URL).mock(return_value=httpx.Response(200, content=_png((230, 159, 0, 255)),
                                                                     headers={"content-type": "image/png"}))
    px = asyncio.run(edo.pixel("cdiad", 22.6021, 53.0501, date(2018, 6, 11)))
    assert px == (230, 159, 0, 255)
    q = route.calls.last.request.url.params
    assert q["REQUEST"] == "GetMap" and q["LAYERS"] == "cdiad" and q["TIME"] == "2018-06-11" and q["WIDTH"] == "3"
    asyncio.run(edo.pixel("cdiad", 22.6021, 53.0501, date(2018, 6, 11)))
    assert route.call_count == 1  # z cache
    respx.get(edo.WMS_URL).mock(return_value=httpx.Response(200, content=b"Invalid request type"))
    with pytest.raises(SourceError):
        asyncio.run(edo.pixel("smian", 21.0, 52.0, date(2018, 6, 11)))


@respx.mock
def test_pixel_out_of_range_decade_is_no_data_not_failure():
    """Dekada jeszcze nieopublikowana: HTTP 400 InvalidDimensionValue = brak danych (bez bezpiecznika); inne 400 = błąd."""
    body = (b'<ServiceExceptionReport version="1.1.1"><ServiceException code="InvalidDimensionValue">Requested date '
            b'2026-11-11 is outside the available coverage range</ServiceException></ServiceExceptionReport>')
    respx.get(edo.WMS_URL).mock(return_value=httpx.Response(400, content=body))
    for layer in ("cdiad", "cdirc", "smian", "rdria"):
        assert asyncio.run(edo.pixel(layer, 22.6, 53.05, date(2026, 11, 11))) == edo.NO_DATA
    respx.get(edo.WMS_URL).mock(return_value=httpx.Response(
        400, content=b'<ServiceException code="LayerNotDefined">Layer not found</ServiceException>'))
    with pytest.raises(SourceError):
        asyncio.run(edo.pixel("cdiad", 21.5, 52.5, date(2018, 6, 11)))


def test_endpoint_shape_and_unavailable(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    async def fake_pixel(layer, lon, lat, time, today=None):
        return {"cdiad": (230, 159, 0, 255), "cdirc": T, "smian": (179, 88, 6, 255), "rdria": (255, 205, 0, 255)}[layer]

    monkeypatch.setattr(edo, "pixel", fake_pixel)
    with TestClient(app) as client:
        geom = {"type": "Polygon", "coordinates": [[[22.60, 53.05], [22.602, 53.05], [22.602, 53.051], [22.60, 53.051], [22.60, 53.05]]]}
        r = client.post("/api/drought-context", json={"geometry": geom, "date": "2018-06-30", "our_status": "danger"})
        assert r.status_code == 200, r.text
        a = r.json()
        assert set(a) == {"unavailable", "note_pl", "cdi", "soil_moisture_anomaly", "agri_risk", "sentence", "agrees",
                          "resolution_note", "source", "source_url", "fetched_at", "analysis_date"}
        assert a["cdi"] == {"class": "ostrzeżenie", "label_pl": "ostrzeżenie przed suszą", "date": "2018-06-11",
                            "decade_label": "dekada 11–20.06.2018"}
        assert a["agri_risk"]["class"] == "srednie" and a["agrees"] is True and a["fetched_at"]
        assert client.post("/api/drought-context", json={"geometry": geom, "date": "2999-01-01"}).status_code == 422

        async def broken(layer, lon, lat, time, today=None):
            raise SourceError(edo.SOURCE, "usługa nie odpowiada")

        monkeypatch.setattr(edo, "pixel", broken)
        b = client.post("/api/drought-context", json={"geometry": geom}).json()
        assert b["unavailable"] is True and b["note_pl"] and b["cdi"] is None
