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
    assert P.price("pszenica_ozima", "podlaskie", D2019) is None  # GUS w repo od 2021 r.
    zl, src = P.price("pszenica_ozima", "podlaskie", date(2024, 5, 1))
    assert src.endswith("2021–2023")
    f = tmp_path / "z.csv"
    f.write_text('crop_id,zl_t,week,date,source,url\nrzepak,2319,05.07.2026,2026-07-05,ZSRIR,\n', encoding="utf-8")
    monkeypatch.setattr(P, "ZSRIR_FILES", (f,))
    assert P.zsrir_price("rzepak", D2019) is None and P.price_now(D2019) is None
    assert P.zsrir_price("rzepak", date(2026, 7, 4)) is None and P.price_now(date(2026, 7, 5))[0].zl_t == 2319
    assert P.no_price_reason("pszenica_ozima", D2019, "podlaskie") == P.NO_PRICE_BEFORE
    assert P.no_price_reason("pszenica_ozima", date(2026, 11, 22), "podlaskie") is None


def test_analysis_2019_uses_no_yields_or_prices_from_2019_or_later():
    sug = S.build(weather(), D2019, ctx())
    gus_tags = [t.source for i in items(sug).values() for t in i.source_tags if t.source.startswith(S.GUS_SOURCE)]
    assert gus_tags and all("2019" not in t and "202" not in t for t in gus_tags), gus_tags
    sug = P.attach(sug, "podlaskie", D2019)
    for it in sug.groups[0].items:
        assert it.revenue is None and it.revenue_note is not None
        assert all(y.year <= 2018 for y in it.yields_by_year)


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
