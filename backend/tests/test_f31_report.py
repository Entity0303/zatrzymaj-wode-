"""F31 – raport PDF: kafel i zdanie „Tło suszowe (EDO)”, okres bez deszczu w punkcie „Opady”, upał w raporcie pełnym,
próchnica ukryta (przyczyna, reguła, wartość). Bez sieci."""
import io
from datetime import date

import httpx
import respx
from pypdf import PdfReader

from app.analysis import drought_context as DC
from app.analysis import extremes
from app.core.config import settings
from app.report.builder import DRY_MARK, HUMUS_RULE, farmer_view, point_text, render_html, short_pdf, tiles
from app.schemas.analysis import AnalysisResponse, Cause
from test_a5b2 import long_weather  # noqa: F401 – fixture: pogoda z 12 lat
from test_a5e import PID, client, mock_all  # noqa: F401 – fixture klienta i atrapy źródeł

T = (0, 0, 0, 0)


def _analysis(client) -> AnalysisResponse:
    with respx.mock:
        mock_all()
        respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
        return AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-11-21"}).json())


def _edo(status: str = "danger"):
    return DC.build(date(2018, 6, 11), (230, 159, 0, 255), T, (179, 88, 6, 255), (255, 205, 0, 255), date(2018, 6, 30), status)


def test_report_shows_edo_tile_and_sentence(client, long_weather):
    a = _analysis(client)
    edo = _edo()
    assert len(tiles(a)) == 4 and len(tiles(a, edo)) == 5
    tile = tiles(a, edo)[-1]
    assert tile["title"] == "Tło suszowe w okolicy (EDO)" and tile["value"] == "ostrzeżenie" and "dekada 11–20.06.2018" in tile["sub"]
    plain = render_html(a, ortho=None)
    assert "Tło suszowe w okolicy" not in plain and 'class="tiles tiles5"' not in plain  # bez danych EDO raport jak dotąd
    short = render_html(a, ortho=None, edo=edo)
    assert 'class="tiles tiles5"' in short and "Tło suszowe w okolicy (EDO)" in short
    assert "zgodne z naszą oceną „Bardzo mało wody”" in short and "✓ Europejskie Obserwatorium Suszy" in short
    full = render_html(a, ortho=None, report_type="full", edo=edo)
    assert "Tło suszowe w okolicy (Europejskie Obserwatorium Suszy)" in full and "Ryzyko skutków suszy dla rolnictwa" in full
    assert "Copernicus European Drought Observatory (EDO), JRC" in full and "siatka ok. 5–10 km" in full
    # raport skrócony z piątym kaflem nadal ma 2 strony
    pdf = short_pdf(lambda level: render_html(a, None, None, "short", level, edo))
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2


def test_report_dry_spell_in_precip_point_and_heat_in_full(client, long_weather):
    a = _analysis(client)
    dry = extremes.DrySpellStats.model_validate({
        "window_from": "2018-03-01", "window_to": "2018-10-31", "longest_days": 23, "longest_from": "2018-04-02",
        "longest_to": "2018-04-24", "spells_10d": 3, "usual_days": 14, "longer_in_years": 1, "of_years": 10,
        "sentence": "Najdłuższy okres bez deszczu: 23 dni (02.04–24.04), zwykle 14 – dłuższy był tylko w 1 z 10 lat.",
        "source_tag": a.history.source_tag.model_dump()})
    long_text = "Opady za niskie wiosną – w 5 z 10 lat w maju–czerwcu brakowało wody. " * 4
    v = a.verdict.model_copy(update={"statements": [
        st.model_copy(update={"text": long_text.strip() + DRY_MARK + " 23 dni (02.04–24.04)."}) if st.kind == "opady" else st
        for st in a.verdict.statements]})
    a2 = a.model_copy(update={"verdict": v, "dry_spell": dry})
    st = next(s for s in a2.verdict.statements if s.kind == "opady")
    txt = point_text(st, a2, 150)
    assert txt.endswith("Najdłużej bez deszczu: 23 dni (02.04–24.04), zwykle 14.") and len(txt) < 240  # zdanie nie jest ucinane
    assert point_text(st, a2).count("bez deszczu") == 1
    full = render_html(a2, ortho=None, report_type="full")
    assert "Okresy bez deszczu w sezonie" in full and "Okresów bez deszczu trwających 10 dni i dłużej: 3." in full
    if a.heat is not None:
        assert "Upał w sezonie" in full and "podajemy oba progi" in full


def test_report_hides_humus(client, long_weather):
    a = _analysis(client)
    om = extremes.organic_matter(8.0)  # 1,4% – klasa niska
    assert om is not None and om.class_key == "niska"
    rec = a.recommendations[0].model_copy(update={"id": HUMUS_RULE, "title": "Zwiększaj próchnicę w glebie"}) if a.recommendations else None
    a2 = a.model_copy(update={
        "soil": a.soil.model_copy(update={"organic_matter": om}),
        "causes": [*a.causes, Cause(factor="gleba", title="Mało próchnicy", share=0.0, informational=True,
                                    description=extremes.HUMUS_CAUSE, source_tag=a.history.source_tag)],
        "recommendations": [*a.recommendations, *([rec] if rec else [])]})
    fv = farmer_view(a2)
    assert fv.soil.organic_matter is None and all(c.title != "Mało próchnicy" for c in fv.causes)
    assert all(r.id != HUMUS_RULE for r in fv.recommendations) and farmer_view(a) is a
    for kind in ("short", "full"):
        html = render_html(a2, ortho=None, report_type=kind)
        assert "Mało próchnicy" not in html and extremes.HUMUS_CAUSE not in html and "Zwiększaj próchnicę w glebie" not in html
    assert all("Próchnica to szacunek" not in l for l in a.reliability.limitations)  # ograniczenie tylko w trybie Doradca (UI)
