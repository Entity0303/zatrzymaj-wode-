"""A22 – SoilGrids z budżetem 5 s i dociąganiem w tle, opóźniona rozgrzewka z pomijaniem przykładów z cache,
pewność a widełki (rozrzut ryzyka ≥ 4 lata)."""

import asyncio
from datetime import date

import pytest

from app import demo
from app.analysis import suggestions as S
from app.core.config import settings
from app.core.http import SourceError
from app.sources import soilgrids
from test_a5b2 import ctx, items, weather


def test_soilgrids_budget_then_background_fill(monkeypatch):
    calls = []

    async def slow(lon, lat):
        calls.append(1)
        await asyncio.sleep(0.15)
        soilgrids._cache.set((round(lon, 4), round(lat, 4)), "wynik")
        return "wynik"

    monkeypatch.setattr(soilgrids, "texture_at", slow)
    from app.core import background

    monkeypatch.setattr(background, "GRACE_S", {"soilgrids": 0.001})

    async def run():
        with pytest.raises(SourceError) as e:
            await soilgrids.texture_budget(22.6, 53.05, wait_s=0.02)  # A23: SoilGrids w kolejce tła – od razu „w toku”
        assert e.value.message == soilgrids.PENDING_MESSAGE
        with pytest.raises(SourceError):
            await soilgrids.texture_budget(22.6, 53.05, wait_s=0.02)  # to samo pobieranie – bez drugiego zapytania
        await asyncio.sleep(0.3)  # pobieranie skończyło się w tle
        return await soilgrids.texture_budget(22.6, 53.05, wait_s=0.02)

    assert asyncio.run(run()) == "wynik" and len(calls) == 1
    assert settings.soilgrids_wait_s == 5.0 and settings.soilgrids_timeout_s == 12.0


def test_warmup_delay_setting_and_skip_cached(monkeypatch):
    from app.core.config import Settings

    assert Settings().demo_warmup_delay_s == 120.0
    done = []

    async def fake_run(parcel_id, crop, d, prev):
        done.append(parcel_id)

    import app.routers.analysis as RA

    monkeypatch.setattr(RA, "run_analysis", fake_run)
    exs = demo.examples()
    monkeypatch.setattr(demo, "cached_for_today", lambda ex: ex.id == exs[0].id)  # pierwszy przykład jest już w cache
    monkeypatch.setattr(settings, "demo_warmup", True)
    demo.reset_state()
    done.clear()
    state = asyncio.run(demo.warmup_once())
    assert exs[0].parcel_id not in done[:1] and len(done) == len(exs) - 1
    first = next(s for s in state if s.id == exs[0].id)
    assert first.state == "gotowe" and first.duration_ms == 0


def test_warmup_loop_waits_before_first_run(monkeypatch):
    order = []

    async def fake_sleep(s):
        order.append(("sleep", s))
        if len(order) > 2:
            raise asyncio.CancelledError

    async def fake_once():
        order.append(("warmup", 0))

    monkeypatch.setattr(settings, "demo_warmup_delay_s", 120.0)
    monkeypatch.setattr(demo.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(demo, "warmup_once", fake_once)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(demo.warmup_loop())
    assert order[0] == ("sleep", 120.0) and order[1] == ("warmup", 0)


def test_ranges_lower_confidence_only_from_spread_of_four_years():
    w, c, d = weather(), ctx(), date(2018, 11, 21)
    base = items(S.build(w, d, c))["pszenica_ozima"]
    three = items(S.build(w, d, c, ranges={"pszenica_ozima": {"risk": (1, 4)}}))["pszenica_ozima"]
    four = items(S.build(w, d, c, ranges={"pszenica_ozima": {"risk": (0, 4)}}))["pszenica_ozima"]
    assert three.confidence == base.confidence and three.confidence_note == base.confidence_note  # rozrzut 3 – bez zmian
    assert four.confidence == "ograniczona" and "wynik zależy od danych o opadach i glebie" in four.confidence_note
    assert S.config()["variants"]["wide_risk_years"] == 4
