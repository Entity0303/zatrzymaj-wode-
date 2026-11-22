"""A27 – „Wody gruntowe i wsiąkanie”: progi wsiąkania (reguły YAML), okna 30 / 60 dni tylko sprzed daty analizy,
obszar podtopień PIG-PIB (atrapa usługi), `unavailable` przy błędzie PIG, kształt odpowiedzi endpointu. Bez sieci."""

import asyncio
from datetime import date

import httpx
import numpy as np
import pytest
import respx

from app.analysis import groundwater as GW
from app.core.http import SourceError
from app.sources import pig

D = date(2018, 6, 30)


def _series(precip_30: float, et0_30: float, precip_prev: float | None = None, et0_prev: float | None = None, days: int = 90,
            end: date = D):
    """Seria dobowa kończąca się dzień przed `end`: ostatnie 30 dni o zadanych sumach, wcześniejsze – `*_prev` na 30 dni."""
    dates = np.arange(np.datetime64(end, "D") - np.timedelta64(days, "D"), np.datetime64(end, "D"))
    p = np.full(days, (precip_prev if precip_prev is not None else precip_30) / 30.0)
    e = np.full(days, (et0_prev if et0_prev is not None else et0_30) / 30.0)
    p[-30:] = precip_30 / 30.0
    e[-30:] = et0_30 / 30.0
    return dates, p, e


def test_light_soil_and_little_rain_is_very_weak():
    inf = GW.infiltration(*_series(18, 42), D, soil_code=2)
    assert inf.level == "bardzo_slabe" and inf.label_pl == "bardzo słabe wsiąkanie"
    assert inf.sentence_pl == ("Lekka gleba i 18 mm opadu w 30 dni przy 42 mm parowania – woda szybko schodzi w głąb "
                               "albo paruje, mało zostaje dla roślin.")
    assert inf.short_pl == "Wsiąkanie: bardzo słabe (18 mm opadu w 30 dni przy 42 mm parowania)."
    assert inf.precip_30d_mm == 18.0 and inf.et0_30d_mm == 42.0 and inf.data_until == date(2018, 6, 29)


def test_heavy_soil_and_much_rain_is_good():
    inf = GW.infiltration(*_series(80, 40), D, soil_code=4)
    assert inf.level == "dobre" and "Ciężka gleba i 80 mm opadu" in inf.sentence_pl and inf.sentence_pl.endswith("uzupełnia zapas wody w glebie.")


def test_levels_follow_soil_slope_and_60_days():
    same = _series(30, 40)  # opad / parowanie = 0,75
    by_soil = [GW.infiltration(*same, D, soil_code=c).index for c in (1, 2, 3, 4)]
    assert by_soil == sorted(by_soil) and by_soil[0] < by_soil[-1]  # lżejsza gleba → mniej zostaje dla roślin
    assert GW.infiltration(*same, D, soil_code=2).level == "slabe" and GW.infiltration(*same, D, soil_code=4).level == "slabe"
    flat, steep = GW.infiltration(*same, D, 3, 1.0), GW.infiltration(*same, D, 3, 8.0)
    assert steep.index < flat.index and "część wody spływa po powierzchni" in steep.sentence_pl
    assert "spływa" not in flat.sentence_pl and flat.slope_mean_pct == 1.0
    wet_before = GW.infiltration(*_series(30, 40, precip_prev=120, et0_prev=40), D, 3)
    assert wet_before.index > GW.infiltration(*same, D, 3).index and wet_before.precip_60d_mm == 150.0
    winter = GW.infiltration(*_series(25, 0.5), D, 2)  # parowanie bliskie zera – stosunek obcięty, nie dzielimy przez zero
    assert winter.level == "dobre" and winter.index <= GW.cfg()["ratio_cap"]
    assert GW.infiltration(*same, D, soil_code=None).soil_code is None  # brak kategorii – liczymy z wartością „unknown”
    heavy_dry = GW.infiltration(*_series(10, 120), D, soil_code=4)
    assert heavy_dry.level == "bardzo_slabe" and "prawie cały opad wyparowuje" in heavy_dry.sentence_pl


def test_only_data_before_analysis_date_and_missing_data():
    dates, p, e = _series(18, 42, days=120, end=date(2018, 8, 30))  # seria sięga PO dacie analizy
    p[dates >= np.datetime64(D, "D")] = 50.0  # ulewy po dacie analizy nie mogą wpłynąć na wynik
    assert GW.infiltration(dates, p, e, D, 2).precip_30d_mm == GW.infiltration(*_series(18, 42), D, 2).precip_30d_mm
    dates, p, e = _series(18, 42)
    p[-12:] = np.nan  # mniej niż 80% ważnych dni w oknie 30 dni
    assert GW.infiltration(dates, p, e, D, 2) is None
    assert GW.dominant_soil({1: 0.25, 3: 0.75}) == 3 and GW.dominant_soil({11: 0.9, 2: 0.1}) == 2 and GW.dominant_soil({13: 1.0}) is None


def test_combine_with_pig_flood_zone():
    inf = GW.infiltration(*_series(80, 40), D, soil_code=4)
    zone = pig.FloodZone(True, "Obszary zagrożone powodzią od wód gruntowych", "Region dolnej Wisły")
    both = GW.combine(inf, zone, False, 40.0, D, pig.DEPTH_NOTE, pig.UNAVAILABLE_NOTE)
    assert both.flood_after_rain and both.may_reduce_drought and "ryzyko podtopień po ulewie" in both.interpretation_pl
    assert "susza może być mniejsza niż z bilansu" in both.interpretation_pl and both.flood_zone.water_region == "Region dolnej Wisły"
    assert both.depth_m is None and both.source_pig.note_pl == pig.DEPTH_NOTE and not both.source_pig.unavailable
    no_hollow = GW.combine(inf, zone, False, None, D, pig.DEPTH_NOTE, pig.UNAVAILABLE_NOTE)
    assert no_hollow.may_reduce_drought and not no_hollow.flood_after_rain
    outside = GW.combine(inf, pig.FloodZone(False), False, 40.0, D, pig.DEPTH_NOTE, pig.UNAVAILABLE_NOTE)
    assert not outside.flood_after_rain and not outside.may_reduce_drought and outside.flood_zone.in_zone is False
    # PIG nie odpowiada: samo wsiąkanie, bez zgadywania o podtopieniach
    pig_down = GW.combine(inf, None, True, 40.0, D, pig.DEPTH_NOTE, pig.UNAVAILABLE_NOTE)
    assert not pig_down.unavailable and pig_down.infiltration is not None and pig_down.flood_zone is None
    assert pig_down.source_pig.unavailable and pig_down.source_pig.note_pl == "usługa PIG niedostępna"
    assert pig_down.interpretation_pl is None and not pig_down.may_reduce_drought
    nothing = GW.combine(None, None, True, None, D, pig.DEPTH_NOTE, pig.UNAVAILABLE_NOTE)
    assert nothing.unavailable and nothing.note_pl == GW.UNAVAILABLE_NOTE and nothing.infiltration is None


@respx.mock
def test_pig_flood_zone_query_and_errors():
    hit = {"features": [{"attributes": {"OPIS": "Obszary zagrożone powodzią od wód gruntowych (podtopienia) - doliny rzeczne",
                                        "REG_WOD": "Region dolnej Wisły"}}]}
    route = respx.get(pig.QUERY_URL).mock(return_value=httpx.Response(200, json=hit))
    z = asyncio.run(pig.flood_zone(19.03, 54.11))
    assert z.in_zone and z.water_region == "Region dolnej Wisły"
    q = route.calls.last.request.url.params
    assert q["geometryType"] == "esriGeometryPoint" and q["inSR"] == "4326" and q["geometry"] == "19.030000,54.110000"
    asyncio.run(pig.flood_zone(19.03, 54.11))
    assert route.call_count == 1  # z cache
    respx.get(pig.QUERY_URL).mock(return_value=httpx.Response(200, json={"features": []}))
    assert asyncio.run(pig.flood_zone(22.6, 53.05)).in_zone is False
    respx.get(pig.QUERY_URL).mock(return_value=httpx.Response(200, json={"error": {"code": 400, "message": "Invalid"}}))
    with pytest.raises(SourceError):
        asyncio.run(pig.flood_zone(21.0, 52.0))
    respx.get(pig.QUERY_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceError):
        asyncio.run(pig.flood_zone(21.1, 52.1))


def test_endpoint_shape_and_pig_unavailable(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.analysis import terrain as terrain_mod
    from app.main import app
    from app.routers import analysis as analysis_router
    from app.sources import iung

    dates, p, e = _series(18, 42)

    async def fake_weather(lon, lat, analysis_date, season_start=None):
        return SimpleNamespace(weather=SimpleNamespace(dates=dates, precip=p, et0=e))

    async def fake_soil(geom):
        return SimpleNamespace(shares={2: 0.8, 3: 0.2})

    async def fake_terrain(geom, parcel_id=None):
        return SimpleNamespace(facts={"slope_mean_pct": 1.2, "zone_share_pct": {"mokry_dolek": 35.0}})

    async def in_zone(lon, lat):
        return pig.FloodZone(True, "podtopienia", "Region dolnej Wisły")

    async def pig_down(lon, lat):
        raise SourceError(pig.SOURCE, "usługa nie odpowiada (przekroczono 8 s)")

    monkeypatch.setattr(analysis_router, "load_weather_history", fake_weather)
    monkeypatch.setattr(iung, "soil_for_parcel", fake_soil)
    monkeypatch.setattr(terrain_mod, "cached_terrain", fake_terrain)
    monkeypatch.setattr(pig, "flood_zone", in_zone)
    geom = {"type": "Polygon", "coordinates": [[[19.03, 54.11], [19.032, 54.11], [19.032, 54.111], [19.03, 54.111], [19.03, 54.11]]]}
    with TestClient(app) as client:
        r = client.post("/api/groundwater", json={"geometry": geom, "date": "2018-06-30"})
        assert r.status_code == 200, r.text
        a = r.json()
        assert set(a) == {"unavailable", "note_pl", "infiltration", "flood_zone", "depth_m", "source_pig", "flood_after_rain",
                          "may_reduce_drought", "interpretation_pl", "limitation_pl", "source", "source_url", "fetched_at",
                          "analysis_date"}
        assert a["infiltration"]["level"] == "bardzo_slabe" and a["infiltration"]["soil_code"] == 2
        assert a["flood_after_rain"] is True and a["may_reduce_drought"] is True and a["depth_m"] is None
        assert client.post("/api/groundwater", json={"geometry": geom, "date": "2999-01-01"}).status_code == 422
        monkeypatch.setattr(pig, "flood_zone", pig_down)
        b = client.post("/api/groundwater", json={"geometry": geom, "date": "2018-06-30"}).json()
        assert b["unavailable"] is False and b["infiltration"]["level"] == "bardzo_slabe"  # wsiąkanie zostaje
        assert b["source_pig"] == {"unavailable": True, "note_pl": "usługa PIG niedostępna", "depth_available": False}
        assert b["flood_zone"] is None and b["flood_after_rain"] is False and b["interpretation_pl"] is None

        async def no_weather(lon, lat, analysis_date, season_start=None):
            raise SourceError("NASA POWER", "brak danych")

        monkeypatch.setattr(analysis_router, "load_weather_history", no_weather)
        c = client.post("/api/groundwater", json={"geometry": geom, "date": "2018-06-30"}).json()
        assert c["unavailable"] is True and c["note_pl"] and c["infiltration"] is None


# ── raport PDF: zdanie w punkcie „Gleba” (skrócony, nadal 2 strony) i sekcja w raporcie pełnym ──
from test_a5b2 import long_weather  # noqa: E402,F401 – fixture: pogoda z 12 lat
from test_a5e import PID, client, mock_all  # noqa: E402,F401 – fixture klienta i atrapy źródeł


def test_report_has_infiltration_sentence_and_section(client, long_weather):
    import io

    from pypdf import PdfReader

    from app.core.config import settings
    from app.report.builder import point_text, render_html, short_pdf
    from app.schemas.analysis import AnalysisResponse

    with respx.mock:
        mock_all()
        respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
        a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-11-21"}).json())
    inf = GW.infiltration(*_series(18, 42), D, soil_code=2)
    gw = GW.combine(inf, pig.FloodZone(True, "podtopienia", "Region dolnej Wisły"), False, 40.0, D, pig.DEPTH_NOTE,
                    pig.UNAVAILABLE_NOTE)
    soil_point = next(s for s in a.verdict.statements if s.kind == "gleba")
    assert point_text(soil_point, a, 150, gw).endswith(inf.short_pl) and point_text(soil_point, a, 150) == point_text(soil_point, a, 150, None)
    assert "Wsiąkanie:" not in render_html(a, ortho=None)  # bez danych raport jak dotąd
    short = render_html(a, ortho=None, gw=gw)
    assert inf.short_pl in short and "Wody gruntowe i wsiąkanie" not in short  # skrócony: jedno zdanie, bez sekcji i kafla
    assert 'class="tiles tiles5"' not in short
    full = render_html(a, ortho=None, report_type="full", gw=gw)
    assert "<h2>Wody gruntowe i wsiąkanie</h2>" in full and inf.sentence_pl in full and "ryzyko podtopień po ulewie" in full
    assert "PIG-PIB" in full and "progi orientacyjne" in full
    down = GW.combine(inf, None, True, None, D, pig.DEPTH_NOTE, pig.UNAVAILABLE_NOTE)
    assert "brak danych (usługa PIG niedostępna)" in render_html(a, ortho=None, report_type="full", gw=down)
    pdf = short_pdf(lambda level: render_html(a, None, None, "short", level, None, gw))
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2


def test_chart_ticks_do_not_fail_on_large_ranges():
    """Wykres „Ceny i pogoda” w raporcie pełnym: cena > 3000 zł/t (rzepak) wywracała raport (StopIteration → HTTP 500)."""
    from app.report.charts import _ticks

    assert _ticks(0, 2400, 3) and _ticks(0, 3600, 3)[-1] <= 3600 and len(_ticks(0, 3600, 3)) >= 2
    assert _ticks(0, 250000, 3) and _ticks(0, 9, 3)
