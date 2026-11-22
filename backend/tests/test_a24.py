"""A24 – okresy bez opadu, upał i próchnica (informacyjnie; dane syntetyczne)."""

from dataclasses import replace
from datetime import date, timedelta

import numpy as np

from app.analysis import extremes as X
from app.analysis.causes import build_causes
from app.analysis.crops import CROPS
from test_a5b2 import weather
from test_analysis import facts


def test_longest_dry_run_and_long_spells():
    p = np.array([5, 0, 0.5, 0.9, 1.0, 0, 0, np.nan, 0, 0] + [0.0] * 12 + [3.0] + [0.2] * 10)
    n, i0, long_runs = X.longest_dry_run(p)
    assert (n, i0) == (14, 8) and long_runs == 2  # 14 dni od indeksu 8 (NaN przerywa ciąg) i 10 dni na końcu
    assert X.longest_dry_run(np.array([2.0, 3.0])) == (0, 0, 0)


def _weather_with(year_spell: dict[int, int], hot: dict[int, int]):
    """Każdy dzień 2 mm deszczu i 20°C; w podanych latach od 10 maja ciąg dni bez opadu / dni upalnych."""
    w = weather()
    yrs = w.dates.astype("datetime64[Y]").astype(int) + 1970
    precip, tmax = np.full(len(w.dates), 2.0), np.full(len(w.dates), 20.0)
    for y, n in year_spell.items():
        i = int((np.datetime64(date(y, 5, 10)) - w.dates[0]).astype(int))
        precip[i:i + n] = 0.0
    for y, n in hot.items():
        i = int((np.datetime64(date(y, 6, 1)) - w.dates[0]).astype(int))
        tmax[i:i + n] = 32.0
        tmax[i + n:i + n + 5] = 26.0
    return replace(w, precip=precip, tmax=tmax), int(yrs.max())


def test_dry_spell_vs_previous_years():
    w, last_year = _weather_with({2018: 23, 2017: 12, 2016: 30, 2015: 5}, {})
    d = X.dry_spell(w, date(2018, 3, 1), date(2018, 6, 30))
    assert d.longest_days == 23 and d.longest_from == date(2018, 5, 10) and d.longest_to == date(2018, 6, 1)
    assert d.spells_10d == 1 and d.longer_in_years == 1 and d.of_years >= 8 and d.usual_days == 0
    assert d.sentence.startswith("Najdłuższy okres bez deszczu: 23 dni (10.05–01.06), zwykle 0 – dłuższy był tylko w 1 z ")
    assert X.season_window(date(2018, 6, 30)) == (date(2018, 3, 1), date(2018, 6, 30))
    assert X.season_window(date(2026, 11, 21)) == (date(2026, 3, 1), date(2026, 10, 31))
    assert X.season_window(date(2019, 2, 10)) == (date(2018, 3, 1), date(2018, 10, 31))


def test_heat_days_and_sensitive_phase():
    w, _ = _weather_with({}, {2018: 9, 2017: 3, 2016: 3})
    crop = CROPS["zboza_ozime"]
    h = X.heat(w, date(2018, 3, 1), date(2018, 6, 30), crop=crop, crop_label=crop.label)
    assert h.days_30 == 9 and h.days_25 == 14 and h.usual_days_30 == 0 and h.of_years >= 8
    assert h.sensitive_days_30 == sum(crop.day_info(date(2018, 6, 1) + timedelta(days=k)).sensitive for k in range(9))
    assert h.sentence.startswith("Upał: 9 dni powyżej 30°C (zwykle 0)") and "dni powyżej 25°C: 14" in h.sentence
    cool = X.heat(w, date(2015, 3, 1), date(2015, 6, 30))
    assert cool.days_30 == 0 and cool.sentence.startswith("Upał: bez dni powyżej 30°C") and cool.sensitive_days_30 is None


def test_humus_classes_from_soilgrids_carbon():
    assert X.organic_matter(None) is None
    for soc, pct, key in ((5.0, 0.9, "bardzo_niska"), (9.3, 1.6, "niska"), (15.0, 2.6, "srednia"), (25.0, 4.3, "wysoka")):
        om = X.organic_matter(soc)
        assert om.value_pct == pct and om.class_key == key, (soc, om)
    assert X.organic_matter(9.3).sentence == "Próchnica: ok. 1,6% (niska) – szacunek SoilGrids, siatka ok. 250 m."
    low = X.rule_facts(None, None, X.organic_matter(9.3))
    assert low["humus_class"] == "niska" and low["humus_cause"].startswith("Gleba uboga w próchnicę słabiej trzyma wodę.")
    assert X.rule_facts(None, None, X.organic_matter(25.0))["humus_cause"] is None


def test_informational_causes_have_no_share():
    w, _ = _weather_with({2018: 23}, {2018: 9})
    d = X.dry_spell(w, date(2018, 3, 1), date(2018, 6, 30))
    h = X.heat(w, date(2018, 3, 1), date(2018, 6, 30))
    f = facts()
    base = build_causes(f)
    f.values.update(X.rule_facts(d, h, X.organic_matter(9.3)))
    causes = build_causes(f)
    info = [c for c in causes if c.informational]
    assert {c.title for c in info} >= {"Okres bez deszczu", "Upał", "Mało próchnicy"} and all(c.share == 0 for c in info)
    assert [(c.title, c.share) for c in causes if not c.informational] == [(c.title, c.share) for c in base if not c.informational]
    assert abs(sum(c.share for c in causes) - 1.0) < 1e-9  # udziały przyczyn bilansu bez zmian
