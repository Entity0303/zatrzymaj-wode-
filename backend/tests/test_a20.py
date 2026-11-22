"""A20 – spójne stopnie braku wody (z uprawą i bez), daty źródeł przy dacie historycznej, zdanie źródeł opadu."""

import pytest
import respx

from app.analysis import scoring as SC
from app.analysis.facts import Facts
from test_analysis import SOIL_OK, facts


@pytest.mark.parametrize("pct,rank,level", [
    (4, None, "danger"), (15, None, "danger"), (16, None, "risk"), (35, None, "risk"), (36, None, "warn"),
    (50, None, "warn"), (51, None, "ok"), (22, 0, "danger"), (40, 1, "risk"), (40, 0, "danger"), (60, 0, "warn"),
    (95, 0, "ok"), (22, 3, "risk"),
])
def test_one_threshold_function(pct, rank, level):
    assert SC.drought_level(pct, rank) == level


@pytest.mark.parametrize("pct,lower", [(4, 0), (11, 2), (15, 0), (22, 3), (28, 2), (64, 9), (95, 2)])
def test_same_water_same_level_with_and_without_crop(pct, lower):
    """Ten sam zapas i ta sama pozycja wśród lat → ten sam stopień w sezonie z uprawą (także dojrzewanie, po zbiorze)
    i bez uprawy (Pożarowo 10.07.2018: 4% – dawniej „Ryzyko” z uprawą i „Susza” bez)."""
    common = dict(water_pct=float(pct), water_rank_lower=lower, water_rank_of=10, water_rank_pct=10.0 * lower)
    no_crop = SC.overall_status(Facts({"has_crop": False, **common}), SOIL_OK).level
    for phase, sensitive in (("kwitnienie", True), ("dojrzewanie", False), ("po_zbiorze", False)):
        with_crop = SC.overall_status(facts(phase=phase, phase_label=phase, sensitive=sensitive, days_to_stress=5,
                                            **common), SOIL_OK).level
        assert with_crop == no_crop == SC.drought_level(pct, lower), (pct, lower, phase)


def test_level_names_from_dictionary():
    heads = list(SC.HEADLINES_FIELD.values()) + list(SC.HEADLINES_SENSITIVE.values()) + list(SC.HEADLINES_OTHER.values())
    assert not any(h.startswith(("Susza", "Ryzyko", "Dobrze")) for h in heads)
    assert SC.status_cfg()["labels"] == {"ok": "W normie", "warn": "Uwaga", "risk": "Mało wody", "danger": "Bardzo mało wody"}


def test_source_dates_never_after_analysis_date():
    from datetime import date

    from app.analysis.confidence import cap_source_dates
    from app.schemas.analysis import SourceStatus

    d = date(2018, 6, 30)
    src = [SourceStatus(name="ULDK GUGiK", used_for="x", data_date=date(2026, 11, 21), status="ok"),
           SourceStatus(name="IMGW-PIB (stacje)", used_for="x", data_date=date(2026, 10, 31), status="ok"),
           SourceStatus(name="NASA POWER", used_for="x", data_date=date(2018, 6, 29), status="ok")]
    out = cap_source_dates(src, d)
    assert all(s.data_date <= d for s in out)
    assert out[0].data_date == d and out[0].fetched_at == date(2026, 11, 21)
    assert out[1].data_date == date(2018, 6, 29) and out[1].fetched_at == date(2026, 10, 31)
    assert out[2].fetched_at is None and out[2].data_date == date(2018, 6, 29)


def test_precip_sentence_at_most_two_sentences():
    from app.analysis import precip as PR

    assert PR._span(49) == "Ostatnie 7 tygodni" and PR._span(3) == "Ostatnie 3 dni" and PR._span(14) == "Ostatnie 2 tygodnie"
    assert PR._span(1) == "Ostatni dzień"


@pytest.mark.parametrize("crop", [None, "zboza_ozime"])
@respx.mock
def test_analysis_2018_has_no_source_date_after_2018(crop):
    from fastapi.testclient import TestClient

    from app.main import app
    from test_a5 import mock_all

    mock_all()
    with TestClient(app) as c:
        params = {"parcel_id": "201305_2.0038.6/1", "date": "2018-06-10", **({"crop": crop} if crop else {})}
        a = c.get("/api/analysis", params=params).json()
    dates = [s["data_date"] for s in a["reliability"]["sources"] if s["data_date"]]
    assert dates and all(d <= "2018-06-10" for d in dates), dates
    assert any(s.get("fetched_at") for s in a["reliability"]["sources"])  # granice działki pobrane później
    assert all(r["when_label"] != "teraz" for r in a["recommendations"])  # „w dniu analizy”
    assert "z ostatnich 30 dni" not in " ".join(r["description"] for r in a["recommendations"])
