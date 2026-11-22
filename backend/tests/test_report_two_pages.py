"""Raport skrócony zawsze mieści się na 2 stronach: przy nadmiarze tekstu kolejne stopnie skracają listy (nie czcionkę)."""
import io

from pypdf import PdfReader

from app.report.builder import COMPACT, short_pdf
from test_a5b2 import long_weather  # noqa: F401 – fixture: pogoda z 12 lat
from test_a5e import PID, client, mock_all  # noqa: F401 – fixture klienta i atrapy źródeł


def test_short_pdf_escalates_until_two_pages():
    levels = []

    def render(level: int) -> str:
        levels.append(level)
        pages = 4 if level < 2 else 2  # dwa pierwsze układy za długie
        return "".join('<p style="break-after: page">strona</p>' for _ in range(pages - 1)) + "<p>koniec</p>"

    pdf = short_pdf(render)
    assert levels == [0, 1, 2]
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2


def test_compact_levels_only_shorten():
    for prev, nxt in zip(COMPACT, COMPACT[1:]):
        assert all(nxt[k] <= prev[k] for k in prev)
    assert COMPACT[0] == {"pt_clip": 150, "pt_n": 4, "avoid_crops": 3, "avoid_groups": 2, "act_clip": 125, "act_n": 3, "rank_n": 5}


def test_report_says_terrain_is_still_computing(client, long_weather):
    """Teren „pending” w analizie → w raporcie dopisek „Teren w trakcie liczenia…”, nie „Brak danych o terenie”."""
    import httpx
    import respx

    from app.core.config import settings
    from app.report.builder import TERRAIN_PENDING_NOTE, render_html
    from app.routers.reports import _no_pending
    from app.schemas.analysis import AnalysisResponse, TerrainPending

    with respx.mock:
        mock_all()
        respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
        a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-11-21"}).json())
    pending = _no_pending(a.model_copy(update={"terrain": TerrainPending(), "terrain_note": None}))
    assert pending.terrain is None and pending.terrain_note == TERRAIN_PENDING_NOTE
    for kind in ("short", "full"):
        html = render_html(pending, ortho=None, report_type=kind)
        assert TERRAIN_PENDING_NOTE in html and "Brak danych o terenie dla tej działki" not in html
    plain = render_html(a.model_copy(update={"terrain": None, "terrain_note": "NMT GUGiK nie odpowiada"}), ortho=None)
    assert "Brak danych o terenie dla tej działki" in plain and TERRAIN_PENDING_NOTE not in plain
