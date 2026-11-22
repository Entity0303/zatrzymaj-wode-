"""A12 – ceny skupu GUS i przychód z pola; A9b – okres / zakres dat. Bez sieci (pliki z repo, syntetyczna pogoda)."""

import pytest

from app.analysis import prices as P


def test_price_voivodeship_last_three_years_and_national_fallback():
    zl, src = P.price("pszenica_ozima", "podlaskie")
    assert 500 < zl < 1500 and src.startswith("GUS – ceny skupu, woj. podlaskie, ") and src.endswith("2023–2025")
    zl2, src2 = P.price("pszenica_ozima", "nieistniejące")
    assert src2.startswith("GUS – ceny skupu, Polska,") and "brak danych dla woj. nieistniejące" in src2
    assert P.price("rzepak", "podlaskie") is None and P.price("burak_cukrowy", "podlaskie") is None  # GUS tylko do 2018


def test_revenue_rounded_to_100_and_none_without_price():
    r = P.revenue("pszenica_ozima", 4.2, 3.5, 0.58, "podlaskie")
    zl = P.price("pszenica_ozima", "podlaskie")[0]
    assert r.typical_zl == round(4.2 * 0.58 * zl, -2) and r.weak_year_zl == round(3.5 * 0.58 * zl, -2)
    assert r.typical_zl % 100 == 0 and r.for_area_ha == 0.58 and r.price_zl_t == zl
    assert P.revenue("burak_cukrowy", 64.7, 44.1, 0.58, "podlaskie") is None  # A12b: rzepak ma cenę ZSRIR
    assert P.revenue("pszenica_ozima", None, None, 0.58, "podlaskie") is None


def test_price_now_only_from_file(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "ZSRIR_FILES", (tmp_path / "nie-ma.csv",))
    assert P.price_now() is None
    f = tmp_path / "prices_zsrir_latest.csv"
    f.write_text("crop_id,zl_t,week,url\npszenica_ozima,850,10–16.11.2026,https://www.gov.pl/zsrir\n", encoding="utf-8")
    monkeypatch.setattr(P, "ZSRIR_FILES", (f,))
    pn = P.price_now()
    assert pn[0].crop_id == "pszenica_ozima" and pn[0].zl_t == 850 and pn[0].source == "ZSRIR MRiRW"


@pytest.mark.parametrize("crop", ["pszenica_ozima", "zyto", "jeczmien_ozimy", "owies", "pszenzyto_ozime",
                                  "kukurydza_ziarno", "ziemniak"])
def test_all_priced_crops_have_price_in_every_voivodeship(crop):
    for woj in ("podlaskie", "wielkopolskie", "lubelskie", "mazowieckie"):
        assert P.price(crop, woj) is not None


# ── A9b: okres / zakres dat ────────────────────────────────────────────────────────────────

from datetime import date  # noqa: E402

import numpy as np  # noqa: E402

from app.analysis import period as PR  # noqa: E402
from app.analysis.crops import CROPS  # noqa: E402
from test_water_model import synth  # noqa: E402


def _rain(years, months, dates):
    """2 mm/dzień; w 2026 tylko 0,5 mm (sucho) – reszta lat taka sama."""
    return np.where(years == 2026, 0.5, 2.0)


def _et0(years, months, dates):
    return np.full(len(years), 2.5)


W = synth(date(2015, 1, 1), date(2026, 11, 18), _rain, _et0)


def test_resolve_presets_and_validation():
    d = date(2026, 11, 22)
    assert PR.resolve(None, None, None, d, None) is None
    w = PR.resolve("season", None, None, d, None)
    assert (w.start, w.end) == (date(2026, 4, 1), date(2026, 9, 30))
    w = PR.resolve("30d", None, None, d, None)
    assert w.end == date(2026, 11, 21) and (w.end - w.start).days == 29
    with pytest.raises(PR.PeriodError):
        PR.resolve("since_sowing", None, None, d, None)  # bez uprawy
    with pytest.raises(PR.PeriodError):
        PR.resolve(None, date(2026, 5, 1), date(2026, 12, 1), d, None)  # koniec po dacie analizy
    with pytest.raises(PR.PeriodError):
        PR.resolve(None, date(2026, 6, 1), date(2026, 5, 1), d, None)
    with pytest.raises(PR.PeriodError):
        PR.resolve("30d", date(2026, 5, 1), date(2026, 6, 1), d, None)


def test_sowing_date_autumn_for_winter_crops_spring_for_others():
    d = date(2026, 11, 22)
    assert PR.sowing_date(CROPS["zboza_ozime"], d) == date(2026, 9, 25)
    assert PR.sowing_date(CROPS["zboza_ozime"], date(2026, 6, 1)) == date(2025, 9, 25)
    assert PR.sowing_date(CROPS["kukurydza_ziarno"], d).year == 2026


def test_build_sums_normal_percentile_sentence_and_daily():
    win = PR.resolve(None, date(2026, 5, 1), date(2026, 6, 30), date(2026, 11, 22), None)
    p = PR.build(W, win, years=10, stress_dates=[date(2026, 6, 1), date(2026, 8, 1)], has_crop=True)
    days = 61
    assert p.precip_mm == round(0.5 * days) and p.et0_mm == round(2.5 * days) and p.balance_mm == round(-2.0 * days)
    assert p.normal_balance_mm == round(-0.5 * days) and p.percentile == 0  # żaden z 10 lat nie był suszy
    assert p.stress_days == 1 and len(p.daily) == days and p.daily[-1].balance_cum_mm == round(-2.0 * days, 1)
    assert "zostało o 92 mm mniej niż zwykle" in p.sentence and "Tak sucho nie było w żadnym z 10 ostatnich lat." in p.sentence
    assert p.label == "01.05–30.06.2026" and p.model_dump(by_alias=True)["from"] == date(2026, 5, 1)


def test_30d_window_ends_at_last_data_day():
    win = PR.resolve("30d", None, None, date(2026, 11, 22), None)
    p = PR.build(W, win)
    assert p.to == date(2026, 11, 18) and len(p.daily) == 30 and p.label.startswith("Ostatnie 30 dni (20.10–18.11.2026")


# ── A12b: cena ZSRIR przy braku GUS, powód braku ceny; A9b: okres najwyżej rok ──────────────


def test_zsrir_fallback_for_rapeseed_and_no_price_reasons(tmp_path, monkeypatch):
    f = tmp_path / "prices_zsrir_latest.csv"
    f.write_text('crop_id,zl_t,week,date,source,url\nrzepak,2319,05.07.2026,2026-07-05,"ZSRIR MRiRW, biuletyn",\n',
                 encoding="utf-8")
    monkeypatch.setattr(P, "ZSRIR_FILES", (f,))
    r = P.revenue("rzepak", 3.3, 2.6, 0.58, "podlaskie")
    assert r.price_zl_t == 2319 and r.price_source == "ZSRIR, lipiec 2026 (notowanie 05.07.2026)"
    assert r.typical_zl == round(3.3 * 0.58 * 2319, -2)
    g = P.revenue("pszenica_ozima", 4.2, 3.5, 0.58, "podlaskie")  # GUS jest – bez zmian
    assert g.price_source.startswith("GUS – ceny skupu, woj. podlaskie")
    assert P.price_now()[0].source == "ZSRIR MRiRW, biuletyn"
    assert P.no_price_reason("kukurydza_kiszonka") == "pasza na własne potrzeby, brak ceny skupu"
    assert P.no_price_reason("burak_cukrowy") == "cena z umowy z cukrownią"
    assert P.no_price_reason("lubin") == "brak ceny skupu w danych publicznych"


def test_custom_period_max_one_year():
    with pytest.raises(PR.PeriodError, match="Wybierz okres nie dłuższy niż rok"):
        PR.resolve(None, date(2024, 1, 1), date(2026, 6, 30), date(2026, 11, 22), None)
    assert PR.resolve(None, date(2025, 7, 1), date(2026, 6, 30), date(2026, 11, 22), None) is not None  # 365 dni
