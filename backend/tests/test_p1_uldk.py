"""P1 – odporność pobierania działki: bezpiecznik ULDK (5 błędów w 60 s, próba po 30 s), ponowienie po przekroczeniu
czasu z dłuższym limitem, log przyczyny 502, komunikat przy obszarze przybliżonym. Bez sieci (respx)."""

import asyncio
import logging
import time

import httpx
import pytest
import respx

from app.analysis import approx_area
from app.core.cache import BREAKERS, breaker, breaker_ok, trip
from app.core.config import settings
from app.core.http import SourceError, http_error
from app.sources import uldk
from test_a5 import ULDK_ONE

PID = "201305_2.0038.6/1"


def test_breaker_counts_failures_and_probes():
    for _ in range(4):
        trip("x", 30, "błąd", after=5, window_s=60)
    assert not breaker("x").open
    trip("x", 30, "błąd", after=5, window_s=60)
    b = breaker("x")
    assert b.open and b.probing
    b.until = time.time() - 1  # po 30 s – próba
    trip("x", 30, "znowu", after=5, window_s=60)  # próba nieudana → od razu znowu otwarty
    assert b.open and b.reason == "znowu"
    b.until = time.time() - 1
    breaker_ok("x")
    assert not b.probing and not b.failures
    BREAKERS.clear()


def test_old_failures_outside_window_do_not_count():
    b = breaker("y")
    b.failures = [time.time() - 120] * 4
    trip("y", 30, "błąd", after=5, window_s=60)
    assert not b.open and len(b.failures) == 1
    BREAKERS.clear()


@respx.mock
def test_uldk_timeout_one_retry_with_longer_limit(monkeypatch):
    seen = []

    def handler(request):
        seen.append(1)
        if len(seen) == 1:
            raise httpx.ReadTimeout("wolno", request=request)
        return httpx.Response(200, text=ULDK_ONE)

    respx.get(settings.uldk_url).mock(side_effect=handler)
    assert asyncio.run(uldk.by_id(PID))[0].id == PID and len(seen) == 2


@respx.mock
def test_uldk_two_timeouts_error_mentions_both_limits():
    respx.get(settings.uldk_url).mock(side_effect=httpx.ReadTimeout("wolno"))
    with pytest.raises(SourceError) as e:
        asyncio.run(uldk.by_id(PID))
    assert "15 s" in e.value.message and not breaker(uldk.SOURCE).open  # jeden błąd – bezpiecznik zamknięty


def test_502_logs_one_line_with_source_and_breaker(caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        exc = http_error(SourceError("ULDK GUGiK", "usługa nie odpowiada"))
    assert exc.status_code == 502
    lines = [r.getMessage() for r in caplog.records if "BŁĄD ŹRÓDŁA" in r.getMessage()]
    assert len(lines) == 1 and "źródło=ULDK GUGiK" in lines[0] and "bezpiecznik=" in lines[0] and "czas=" in lines[0]


def test_uldk_down_note_text():
    assert approx_area.ULDK_DOWN_NOTE == ("Ewidencja gruntów chwilowo nie odpowiada – pokazuję obszar ok. 1 ha. "
                                          "Spróbuj kliknąć ponownie za chwilę.")
