"""A16 – tylko dane sprzed daty analizy w plonie i cenach, trend plonów GUS, flaga rozjazdu opadu IMGW / NASA."""

from datetime import date

import numpy as np
import pytest

from app.analysis import precip as PR
from app.analysis import prices as P
from app.analysis import suggestions as S
from test_a5b2 import ctx, items, weather

D2019 = date(2019, 7, 15)


def test_potential_uses_only_gus_years_before_analysis_year():
    old = S.potential("pszenica_ozima", "podlaskie", before_year=2019, target_year=2019)
    assert old.last_year == 2018 and old.years == 3 and not old.trend  # 2016–2018: < 5 lat – bez trendu
    now = S.potential("pszenica_ozima", "podlaskie", before_year=2026, target_year=2026)
    assert now.trend and now.last_year == 2025 and now.years == 10
    assert now.at(2016) < now.at(2025)  # plony GUS rosną – Ym 2016 niższy niż 2025
    assert abs(now.slope) <= 0.03 * now.mean_t_ha + 1e-9  # przycięcie ±3% / rok
    assert now.at(2010) == now.at(2016) and now.at(2030) == now.at(2026)  # bez ekstrapolacji poza dane
    assert S.potential("pszenica_ozima", "podlaskie", before_year=2016).scope == "brak"


def test_prices_only_before_analysis_date(tmp_path, monkeypatch):
    zl19, src19 = P.price("pszenica_ozima", "podlaskie", D2019)  # A16b: ceny GUS od 2013 r.
    assert src19 == "GUS – ceny skupu, woj. podlaskie, 2016–2018" and 600 < zl19 < 750
    assert P.price("pszenica_ozima", "podlaskie", date(2013, 6, 1)) is None  # brak lat sprzed 2013
    zl, src = P.price("pszenica_ozima", "podlaskie", date(2024, 5, 1))
    assert src.endswith("2021–2023")
    f = tmp_path / "z.csv"
    f.write_text('crop_id,zl_t,week,date,source,url\nrzepak,2319,05.07.2026,2026-07-05,ZSRIR,\n', encoding="utf-8")
    monkeypatch.setattr(P, "ZSRIR_FILES", (f,))
    assert P.zsrir_price("rzepak", D2019) is None and P.price_now(D2019) is None
    assert P.zsrir_price("rzepak", date(2026, 7, 4)) is None and P.price_now(date(2026, 7, 5))[0].zl_t == 2319
    assert P.no_price_reason("pszenica_ozima", date(2013, 6, 1), "podlaskie") == P.NO_PRICE_BEFORE
    assert P.no_price_reason("pszenica_ozima", date(2026, 11, 22), "podlaskie") is None


def test_analysis_2019_uses_no_yields_or_prices_from_2019_or_later():
    sug = S.build(weather(), D2019, ctx())
    gus_tags = [t.source for i in items(sug).values() for t in i.source_tags if t.source.startswith(S.GUS_SOURCE)]
    assert gus_tags and all("2019" not in t and "202" not in t for t in gus_tags), gus_tags
    sug = P.attach(sug, "podlaskie", D2019)
    for it in sug.groups[0].items:
        assert all(y.year <= 2018 for y in it.yields_by_year)
        if it.revenue is not None:  # ceny GUS tylko z 2016–2018; rzepak (ZSRIR 2026) – bez ceny
            assert it.revenue.price_source.endswith("2016–2018"), it.revenue.price_source
        else:
            assert it.revenue_note is not None
    assert next(i for i in sug.groups[0].items if i.crop_id == "rzepak").revenue is None


def test_season_disagreement_flag_and_sentence():
    dates = np.arange(np.datetime64("2021-01-01"), np.datetime64("2025-12-31"))
    nasa = np.full(len(dates), 2.0)
    yrs = dates.astype("datetime64[Y]").astype(int) + 1970
    station = np.where(np.isin(yrs, [2023, 2024]), 1.2, 1.9)  # −40% w 2023–2024, −5% w pozostałych
    d = PR.season_diffs(dates, station, nasa)
    assert d[2023] == pytest.approx(-40.0) and d[2021] == pytest.approx(-5.0)
    info = PR.PrecipInfo(main="imgw", season_diff_pct=d, disagreement_years=[2023, 2024])
    info.stations = [object()]
    assert PR.disagreement_sentence(info) == (" W latach 2023–2024 stacja IMGW pokazuje o ok. 40% mniej opadu niż dane "
                                              "satelitarne – wynik dla tych lat jest mniej pewny.")
    assert PR._years_text([2018, 2023, 2024]) == "latach 2018 i 2023–2024" and PR._years_text([2020]) == "2020 r."
    part = PR.season_diffs(dates[dates < np.datetime64("2025-06-01")], station[: (dates < np.datetime64("2025-06-01")).sum()],
                           nasa[: (dates < np.datetime64("2025-06-01")).sum()])
    assert 2025 not in part  # sezon IV–VII niezakończony przed datą analizy


def _info(sums: dict, neighbours: dict) -> PR.PrecipInfo:
    info = PR.PrecipInfo(main="imgw", season_sums=sums, neighbour_mm=neighbours)
    info.season_diff_pct = {y: round(100 * (a - b) / b, 1) for y, (a, b) in sums.items()}
    info.disagreement_years = [y for y, d in info.season_diff_pct.items() if abs(d) > 30]
    info.stations = [object()]
    PR.classify_disagreement(info)
    return info


SUMS = {2021: (356, 308), 2022: (324, 327), 2023: (160, 251), 2024: (132, 245), 2025: (268, 251)}  # Burzyn / NASA


def test_a16b_station_agrees_with_neighbours_nasa_overestimates():
    info = _info(SUMS, {2023: 149, 2024: 153})  # mediany sąsiednich stacji (Burzyn: +7%, −14%)
    assert info.disagreement_years == [2023, 2024] and info.disagreement_source == "nasa"
    assert not info.disagreement_lowers  # pewność bez zmian
    # NASA względem stacji: +57% i +86% → średnio ok. 70%
    assert PR.disagreement_sentence(info) == (" W latach 2023–2024 dane satelitarne NASA pokazują ok. 70% więcej opadu "
                                              "niż stacje IMGW w okolicy – przyjmujemy pomiar ze stacji.")


def test_a16b_station_outlier_lowers_confidence():
    info = _info(SUMS, {2023: 240, 2024: 230})  # sąsiedzi jak NASA – odstaje stacja
    assert info.disagreement_source == "station" and info.disagreement_lowers
    assert "wynik dla tych lat jest mniej pewny" in PR.disagreement_sentence(info)
    info2 = _info(SUMS, {})  # brak sąsiadów – nie wiadomo, jak dotąd (A16)
    assert info2.disagreement_source == "station" and info2.disagreement_lowers
