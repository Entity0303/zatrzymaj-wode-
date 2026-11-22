"""A29 – czas polski: „dziś” (domyślna data analizy) i godzina w stopce raportu liczone w Europe/Warsaw, nie w UTC."""

import datetime as dt

import httpx
import respx

from app.core import clock
from test_a5b2 import long_weather  # noqa: F401 – fixture: pogoda z 12 lat
from test_a5e import PID, client, mock_all  # noqa: F401 – fixture klienta i atrapy źródeł

LATE_UTC = dt.datetime(2026, 11, 22, 23, 30, tzinfo=dt.timezone.utc)  # w Polsce: 23.11.2026 00:30 (czas zimowy)


def test_today_and_now_are_polish(monkeypatch):
    monkeypatch.setattr(clock, "utcnow", lambda: LATE_UTC)
    assert clock.now_pl().strftime("%d.%m.%Y %H:%M") == "23.11.2026 00:30"
    assert clock.today_pl() == dt.date(2026, 11, 23)  # w UTC byłby jeszcze 22.11
    summer = dt.datetime(2026, 7, 1, 22, 30, tzinfo=dt.timezone.utc)  # czas letni: +2 h
    monkeypatch.setattr(clock, "utcnow", lambda: summer)
    assert clock.now_pl().strftime("%d.%m.%Y %H:%M") == "02.07.2026 00:30" and clock.today_pl() == dt.date(2026, 7, 2)
    assert clock.to_pl(dt.datetime(2026, 11, 22, 23, 30)).strftime("%d.%m %H:%M") == "23.11 00:30"  # bez strefy = UTC


def test_no_server_local_today_left_in_app():
    """W kodzie aplikacji nie zostało czasu serwera (date-kropka-today) – „dziś” bierzemy tylko z `clock.today_pl()`."""
    import pathlib
    import re

    root = pathlib.Path(clock.__file__).parents[1]
    left = [str(p.relative_to(root)) for p in root.rglob("*.py")
            if p.name != "clock.py" and re.search(r"\bdate\.today\(\)", p.read_text(encoding="utf-8"))]
    assert left == []


def test_report_footer_and_default_date_use_polish_time(client, long_weather, monkeypatch):
    from app.core.config import settings
    from app.report.builder import date_pl, render_html
    from app.schemas.analysis import AnalysisResponse

    with respx.mock:
        mock_all()
        respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
        a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-11-21"}).json())
    monkeypatch.setattr(clock, "utcnow", lambda: LATE_UTC)
    html = render_html(a, ortho=None)
    assert "wygenerowano 23.11.2026 00:30" in html and "22.11.2026 23:30" not in html
    assert "wygenerowano 23.11.2026 00:30" in render_html(a, ortho=None, generated=LATE_UTC)
    assert date_pl(LATE_UTC) == "23.11.2026 00:30"
    # domyślna data analizy = data polska: 23.11 jest „dziś”, a nie „z przyszłości”
    with respx.mock:
        mock_all()
        respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
        assert client.get("/api/analysis", params={"parcel_id": PID, "date": "2026-11-24"}).status_code == 422
        geom = {"type": "Polygon", "coordinates": [[[22.60, 53.05], [22.602, 53.05], [22.602, 53.051], [22.60, 53.051], [22.60, 53.05]]]}
        assert client.post("/api/drought-context", json={"geometry": geom, "date": "2026-11-24"}).status_code == 422
