"""A21 – widełki wyniku rankingu (warianty opadu i pojemności gleby), data siewu rolnika."""

import asyncio
from dataclasses import replace
from datetime import date

import numpy as np
import pytest
import respx

from app.analysis import prices as P
from app.analysis import suggestions as S
from app.analysis import variants as V
from app.analysis.crops import ALL_CROPS, CROPS, SOWING_OUT_OF_RANGE, with_sowing
from test_a5b2 import ctx, items, long_weather, weather  # noqa: F401

D = date(2018, 11, 21)


def _ranges(w=None, c=None, main="imgw", factor=0.85):
    w = w or weather()
    c = c or ctx()
    raw = w.precip * 1.2
    return w, c, V._compute(w, raw, main, factor, D, c, 10)


def test_variant_specs():
    w, c = weather(), ctx()
    names = [n for n, _w, _c in V.specs(w, w.precip * 1.2, "imgw", 0.85, c)]
    assert names[0] == "opad_nasa" and "wod_dolna" in names and "wod_gorna" in names
    names_nasa = [n for n, _w, _c in V.specs(w, None, "nasa", None, c)]
    assert names_nasa[:2] == ["opad_minus", "opad_plus"]  # NASA główna → opad ±10%
    assert V.wod_bounds(3, 186.0) == (170.0, 202.5) and V.wod_bounds(2, 150.0) == (127.5, 169.9)
    assert V.wod_bounds(1, 100.0) == (80.0, 120.0) and V.wod_bounds(4, 220.0) == (176.0, 264.0)  # I i IV: ±20%


def test_base_numbers_unchanged_and_inside_range():
    w, c, rng = _ranges()
    base = items(S.build(w, D, c))
    full = items(S.build(w, D, c, ranges=rng))
    assert set(base) == set(full)
    for cid, b in base.items():
        f = full[cid]
        assert (f.yield_typical_t_ha, f.yield_weak_t_ha, f.drought_risk_years, f.category, f.rank, f.score) == \
               (b.yield_typical_t_ha, b.yield_weak_t_ha, b.drought_risk_years, b.category, b.rank, b.score)  # bazowe bez zmian
        assert b.yield_typical_range is None and b.drought_risk_range is None
        lo, hi = f.drought_risk_range
        assert lo <= f.drought_risk_years <= hi
        if f.yield_typical_t_ha is not None:
            assert f.yield_typical_range[0] <= f.yield_typical_t_ha <= f.yield_typical_range[1]
            assert f.yield_weak_range[0] <= f.yield_weak_t_ha <= f.yield_weak_range[1]


def test_range_texts_confidence_and_limitation():
    w, c, rng = _ranges()
    sug = S.build(w, D, c, ranges=rng)
    assert S.RANGE_LIMITATION in sug.limitations and S.RANGE_LIMITATION not in S.build(w, D, c).limitations
    crop = ALL_CROPS["pszenica_ozima"]
    rot = S.rotation(crop, [])
    txt = S.reason(crop, "polecane", "odpowiednia", 2, 10, 4.3, 3.5, 2018, 22, rot, False, "pył",
                   typ_range=(4.1, 4.4), risk_range=(1, 3))
    assert "typowo ok. 4,1–4,4 t/ha" in txt and "w 1–3 z 10 lat" in txt
    one = S.reason(crop, "polecane", "odpowiednia", 2, 10, 4.3, 3.5, 2018, 22, rot, False, "pył",
                   typ_range=(4.3, 4.3), risk_range=(2, 2))
    assert "typowo 4,3 t/ha" in one and "w 2 z 10 lat" in one and "ok." not in one  # min = max – jedna liczba
    wide = {cid: {**r, "risk": (0, 4)} for cid, r in rng.items()}
    it = items(S.build(w, D, c, ranges=wide))["pszenica_ozima"]
    assert it.confidence == "ograniczona" and "wynik zależy od danych o opadach i glebie" in it.confidence_note


def test_revenue_range_from_yield_range():
    r = P.revenue("pszenica_ozima", 4.2, 3.5, 0.58, "podlaskie", None, [4.0, 4.5])
    assert r.revenue_range[0] <= r.typical_zl <= r.revenue_range[1] and r.revenue_range[0] % 100 == 0
    assert P.revenue("pszenica_ozima", 4.2, 3.5, 0.58, "podlaskie").revenue_range is None


def test_ranges_async_wait_and_memo():
    w, c = weather(), ctx()

    async def run():
        first = await V.ranges(w, w.precip * 1.2, "imgw", 0.85, D, c, 10, wait_s=None)  # raport: do końca
        again = await V.ranges(w, w.precip * 1.2, "imgw", 0.85, D, c, 10, wait_s=0.0)   # z pamięci – od razu
        return first, again

    V.clear()
    first, again = asyncio.run(run())
    assert first and again == first


def test_sowing_date_shift_and_out_of_range():
    spring = CROPS["zboza_jare"]
    typ = date(2026, *spring.start)
    shifted, note = with_sowing(spring, date(2026, typ.month, typ.day).replace(day=min(28, typ.day + 10)))
    assert note is None and shifted.start != spring.start and shifted.id == spring.id and shifted.harvest == spring.harvest
    assert sum(shifted.phases) == (date(2001, *shifted.harvest) - date(2001, *shifted.start)).days + 1
    same, note2 = with_sowing(spring, date(2026, 7, 1))
    assert same is spring and note2 == SOWING_OUT_OF_RANGE
    winter = CROPS["zboza_ozime"]
    w2, n2 = with_sowing(winter, date(2025, 10, 5))
    assert n2 is None and w2.autumn_sowing == (10, 5) and w2.start == winter.start
    assert with_sowing(spring, None) == (spring, None)


@pytest.mark.parametrize("sowing,expect_note", [("2018-04-05", False), ("2018-08-01", True)])
@respx.mock
def test_api_ranges_and_sowing_date(monkeypatch, long_weather, sowing, expect_note):
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app
    from test_a5 import mock_all

    monkeypatch.setattr(settings, "ranking_variants", True)
    monkeypatch.setattr(settings, "ranking_variants_wait_s", 60.0)  # w teście czekamy do końca
    mock_all()
    with TestClient(app) as c:
        r = c.get("/api/analysis", params={"parcel_id": "201305_2.0038.6/1", "date": "2018-11-21",
                                           "crop": "zboza_jare", "sowing_date": sowing})
    assert r.status_code == 200, r.text
    a = r.json()
    sug = a["suggestions"]
    assert sug["ranges_pending"] is False and S.RANGE_LIMITATION in sug["limitations"]
    it = sug["groups"][0]["items"][0]
    assert it["drought_risk_range"][0] <= it["drought_risk_years"] <= it["drought_risk_range"][1]
    cs = a["crop_season"]
    if expect_note:
        assert cs["sowing_note"] == SOWING_OUT_OF_RANGE and cs["sowing_date"] is None
    else:
        assert cs["sowing_note"] is None and cs["sowing_date"] == sowing and cs["season_start"] == sowing
