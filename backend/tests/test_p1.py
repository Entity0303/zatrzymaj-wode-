"""P1 – szybsze przeliczanie: pamięć wyniku rankingu, wycinek zapisanej serii pogody (te same liczby)."""

from dataclasses import replace
from datetime import date

import numpy as np

from app.analysis import suggestions as S
from app.sources import weather_power as WP
from test_a5b2 import ctx, weather


def test_ranking_memo_same_result_and_no_recompute(monkeypatch):
    w = weather()
    first = S.build(w, date(2018, 11, 21), ctx())
    calls = []
    monkeypatch.setattr(S, "_build", lambda *a, **k: calls.append(1))
    again = S.build(w, date(2018, 11, 21), ctx())
    assert not calls and again.model_dump() == first.model_dump() and again is not first  # kopia, nie ten sam obiekt
    S.build(w, date(2018, 11, 21), ctx(wod_mm=106.3))  # inna gleba → nowe liczenie
    S.build(replace(w, precip=w.precip * 0.9), date(2018, 11, 21), ctx())  # inny opad (wariant) → nowe liczenie
    assert len(calls) == 2


def test_weather_key_depends_on_precip():
    w = weather()
    assert S.weather_key(w) == S.weather_key(replace(w))
    assert S.weather_key(w) != S.weather_key(replace(w, precip=w.precip + 0.1))


def test_slice_weather_equals_sub_range():
    w = weather()
    s, e = (w.dates[100].astype(object), w.dates[500].astype(object))
    cut = WP.slice_weather(w, s, e)
    m = (w.dates >= w.dates[100]) & (w.dates <= w.dates[500])
    assert len(cut.dates) == 401 and np.array_equal(cut.precip, w.precip[m], equal_nan=True)
    assert np.array_equal(cut.et0, w.et0[m], equal_nan=True) and cut.lat == w.lat
    assert WP.slice_weather(w, w.dates[0].astype(object) - __import__("datetime").timedelta(days=1), e) is None
