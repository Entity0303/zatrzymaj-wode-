"""A17 – okres: dni między końcem pomiarów a końcem okresu uzupełniane z Open-Meteo; pola requested_to, data_until,
filled_days, note. Dla dat historycznych (bez prognozy) – bez zmian."""

from dataclasses import replace
from datetime import date, timedelta

import numpy as np

from app.analysis import period as PR
from app.analysis.water_balance import HorizonDay
from test_a5b2 import weather


def _gap_weather(gap_days: int):
    w = weather()
    p, e = w.precip.copy(), w.et0.copy()
    p[-gap_days:] = np.nan
    e[-gap_days:] = np.nan
    return replace(w, precip=p, et0=e), w.dates[-1].astype(object)


def test_gap_filled_from_open_meteo():
    w, last = _gap_weather(3)
    win = PR.Window("30d", last - timedelta(days=29), last)
    fc = [HorizonDay(last - timedelta(days=k), 2.0, 1.0) for k in range(6, -1, -1)]  # 7 ostatnich dni z modelu
    s = PR.build(w, win, forecast=fc)
    assert s.to == last and s.requested_to == last and s.data_until == last - timedelta(days=3) and s.filled_days == 3
    assert s.note.startswith("Ostatnie 3 dni (") and "Open-Meteo" in s.note
    assert [d.precip_mm for d in s.daily[-3:]] == [2.0, 2.0, 2.0] and len(s.daily) == 30
    assert np.isnan(w.precip[-1])  # seria wejściowa bez zmian


def test_without_forecast_period_is_cut_as_before():
    w, last = _gap_weather(3)
    win = PR.Window("custom", last - timedelta(days=19), last)
    s = PR.build(w, win)  # data historyczna / brak prognozy
    assert s.to == last - timedelta(days=3) and s.requested_to == last and s.data_until == s.to and s.filled_days == 0
    assert s.note.startswith("Dane pogodowe są dostępne do ")


def test_complete_data_has_no_note():
    w = weather()
    last = w.dates[-1].astype(object)
    s = PR.build(w, PR.Window("30d", last - timedelta(days=29), last), forecast=[HorizonDay(last, 9.0, 9.0)])
    assert s.note is None and s.filled_days == 0 and s.data_until == last == s.to and s.daily[-1].precip_mm != 9.0


def test_partial_forecast_fills_only_contiguous_days():
    w, last = _gap_weather(4)
    win = PR.Window("custom", last - timedelta(days=19), last)
    fc = [HorizonDay(last - timedelta(days=3), 1.0, 1.0), HorizonDay(last - timedelta(days=2), 1.0, 1.0),
          HorizonDay(last, 1.0, 1.0)]  # brak przedostatniego dnia
    s = PR.build(w, win, forecast=fc)
    assert s.to == last - timedelta(days=2) and s.filled_days == 2 and s.note.startswith("Dane pogodowe są dostępne do ")
