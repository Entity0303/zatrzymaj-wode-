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
    assert P.revenue("rzepak", 3.3, 2.6, 0.58, "podlaskie") is None
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
