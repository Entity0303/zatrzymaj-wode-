"""A14 – spójny nagłówek werdyktu, aktualność stacji opadowych, format liczb, objętość zagłębienia, bez nazw
technicznych w uzasadnieniach."""

from datetime import date

import numpy as np
import pytest

from app.analysis import verdict as V
from app.core.format import MINUS, NBSP, date_pl, num, rain_area_ha, volume_m3


@pytest.mark.parametrize("x, nd, out", [
    (0.858, None, "0,86"), (4.5, None, "4,5"), (22183, None, f"22{NBSP}183"), (-0.24, 2, f"{MINUS}0,24"),
    (166.2, 0, "166"), (1550, None, "1550"), (0.0, 2, "0,00"), (None, None, "–"), (-0.001, 2, "0,00"),
])
def test_num_polish_format(x, nd, out):
    assert num(x, nd) == out


def test_volume_and_dates():
    assert volume_m3(22183) == "22 tys. m³" and volume_m3(1546) == f"1{NBSP}500 m³" and volume_m3(384) == "380 m³"
    assert round(rain_area_ha(22183)) == 111  # 20 mm na 1 ha = 200 m³
    assert date_pl(date(2026, 11, 1)) == "01.11.2026" and date_pl("2024-10-31") == "31.10.2024"


def _lv(**kw):
    return {"gleba": "ok", "opady": "ok", "teren": "ok", "uprawy": "ok", **kw}


def _headline(lv, wet=0.0, dry=0.0):
    return next(h["text"] for h in V.cfg()["headlines"] if V._match(h["if"], lv, wet, dry))


def test_headline_never_weak_when_ranking_recommends_everything():
    # Mrągowo (A14): gleba lekka wg mapy, ale ranking nic nie odradza → nie „Słaba, piaszczysta…”
    assert not _headline(_lv(gleba="bad", opady="warn", uprawy="ok")).startswith("Słaba")
    assert _headline(_lv(gleba="bad", opady="bad", uprawy="bad")).startswith("Słaba, sucha")
    assert _headline(_lv(gleba="warn", opady="bad", uprawy="warn")).startswith("Trudna działka")


def test_soil_level_follows_wod_used_in_model():
    from app.analysis.soil_label import Part, SoilProfile

    prof = SoilProfile("lekka", 1.78, [Part(0.67, "piasek słabogliniasty", 1), Part(0.33, "glina lekka", 3)], "mapa")
    assert V.soil_statement(prof, 173.0).level == "warn"   # WOD jak w modelu i rankingu – przeciętnie
    assert V.soil_statement(prof, 120.0).level == "bad"
    assert "173" in V.soil_statement(prof, 173.0).text


def test_station_without_recent_data_is_skipped():
    from app.sources import imgw

    days = 3000
    start = np.datetime64("2018-01-01")
    data = np.full((days, 2), -1, dtype=np.int16)
    data[:, 1] = 10                  # stacja 1 (dalej) – aktualna
    data[: days - 400, 0] = 10       # stacja 0 (bliżej) – brak danych w ostatnim ponad roku (jak Dynów)
    st = imgw.Store(codes=np.array(["0", "1"]), names=np.array(["BLISKO", "DALEJ"]), kinds=np.array(["opad", "opad"]),
                    lon=np.array([20.0, 20.1]), lat=np.array([50.0, 50.0]), start=start, data=data)
    dates = start + np.arange(days)
    picks = imgw.nearest(st, 20.0, 50.0, dates, 3, 30.0)
    assert [p.name for p in picks] == ["Dalej"]
    assert imgw.nearest(st, 20.0, 50.0, dates, 3, 30.0, min_recent=0.0)[0].name == "Blisko"
