"""A23 – NMT: dopytywanie tylko o brakujące punkty, uzupełnienie do 30% braków, komunikat dla rolnika powyżej 30%."""

import asyncio

import numpy as np
import pytest

from app.core.config import settings
from app.core.http import SourceError
from app.sources import nmt


def _grid(n):
    e = 600000.0 + np.arange(n) * 2.5
    return e, np.full(n, 500000.0)


def _fake_chunks(monkeypatch, drop_first: float, drop_always: float = 0.0):
    """Pierwsze zapytanie gubi `drop_first` punktów (NaN); `drop_always` punktów nie wraca nigdy."""
    calls = []
    monkeypatch.setattr(settings, "gugik_min_interval_s", 0.0)
    monkeypatch.setattr(settings, "nmt_parallel", 2)

    async def chunk(e, n):
        calls.append(len(e))
        h = 100.0 + (e - 600000.0) / 100.0
        idx = ((e - 600000.0) / 2.5).round().astype(int)
        if len(calls) == 1:
            h = np.where(idx % 100 < drop_first * 100, np.nan, h)
        return np.where(idx % 100 < drop_always * 100, np.nan, h)

    monkeypatch.setattr(nmt, "_chunk", chunk)
    return calls


def test_missing_points_are_refetched_only(monkeypatch):
    calls = _fake_chunks(monkeypatch, drop_first=0.5)
    e, n = _grid(800)
    h, info = asyncio.run(nmt._download(e, n))
    assert not np.isnan(h).any() and info["missing_share"] == 0 and info["refetched_points"] == 400
    assert calls == [800, 400]  # drugie zapytanie tylko o brakujące punkty


def test_up_to_30pct_missing_is_accepted_for_filling(monkeypatch):
    calls = _fake_chunks(monkeypatch, drop_first=0.3, drop_always=0.3)
    e, n = _grid(800)
    h, info = asyncio.run(nmt._download(e, n))
    assert info["missing_share"] == pytest.approx(0.3) and len(calls) == 1 + nmt.MISSING_RETRIES
    from app.analysis.terrain import fill_nans

    z = fill_nans(h.reshape(20, 40).copy())
    assert not np.isnan(z).any()  # braki uzupełnione z sąsiednich punktów


def test_more_than_30pct_missing_gives_farmer_message(monkeypatch):
    _fake_chunks(monkeypatch, drop_first=0.5, drop_always=0.5)
    e, n = _grid(800)
    with pytest.raises(SourceError) as exc:
        asyncio.run(nmt._download(e, n))
    msg = exc.value.message
    assert msg == "Dane o terenie przyszły niepełne – liczę ponownie, spróbuj za ok. 2 minuty."
    assert "%" not in msg and "wysokości w odpowiedzi" not in msg
