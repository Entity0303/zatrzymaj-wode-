"""A28: „Ceny i pogoda na tle lat” – porównanie regionalne (województwo / Polska): dane syntetyczne + pliki z repo."""
import numpy as np
from fastapi.testclient import TestClient

from app.analysis import price_weather as PW
from app.main import app
from app.sources import imgw


def synth(years=range(2013, 2025), dry=(2015, 2018, 2019)):
    """12 lat z TRENDEM: plon rośnie o 0,1 t/ha rocznie (od 4,0), cena o 20 zł/t (od 800). W suchych latach opad 250 mm
    (inaczej 400), plon o 20% poniżej trendu, cena o 10% powyżej."""
    prices = {("pszenica", "podlaskie"): {y: round((800 + 20 * (y - 2013)) * (1.10 if y in dry else 1.0), 1) for y in years}}
    yields = {("pszenica_ozima", "podlaskie"): {y: round((4.0 + 0.1 * (y - 2013)) * (0.80 if y in dry else 1.0), 3) for y in years}}
    precip = {y: (250.0 if y in dry else 400.0, 12) for y in years}
    return prices, yields, precip


def test_summary_compares_deviations_from_trend_not_raw_values():
    prices, yields, precip = synth()
    r = PW.build("podlaskie", "pszenica_ozima", 2025, prices=prices, yields=yields, precip=precip)
    assert r["region_label"] == "woj. podlaskie" and r["crop_label"] == "Pszenica" and r["unavailable"] is False
    assert [x["year"] for x in r["years"]] == list(range(2013, 2025))
    y2015 = r["years"][2]
    assert y2015["year"] == 2015 and y2015["precip_mm"] == 250.0 and set(y2015) == {
        "year", "precip_mm", "price_pln_t", "yield_t_ha", "yield_dev_pct", "price_dev_pct"}
    assert -21 < y2015["yield_dev_pct"] < -19 and 9 < y2015["price_dev_pct"] < 11
    assert abs(r["years"][0]["yield_dev_pct"]) < 0.5 and abs(r["years"][-1]["price_dev_pct"]) < 0.5  # zwykłe lata na trendzie
    assert r["dry_years"] == [2015, 2018, 2019]  # dolne 25% z 12 lat = 3 lata
    assert r["summary_pl"] == ("W najsuchszych latach (2015, 2018, 2019) plon pszenicy w województwie podlaskim był średnio "
                               "o 20% niższy od typowego dla tamtych lat, a cena skupu o 10% wyższa.")
    assert r["note_pl"].startswith(PW.NOTE) and "2022" in r["note_pl"] and len(r["sources"]) == 3


def test_rising_yields_do_not_hide_drought_loss():
    """Suche lata na KOŃCU szeregu rosnących plonów: surowo plon w suchych latach jest wyższy niż średnia pozostałych,
    ale względem trendu – niższy (to był błąd pierwszej wersji wniosku)."""
    years = range(2014, 2026)
    dry = (2023, 2024, 2025)
    yields = {("pszenica_ozima", "podlaskie"): {y: round((3.0 + 0.2 * (y - 2014)) * (0.9 if y in dry else 1.0), 3) for y in years}}
    prices = {("pszenica", "podlaskie"): {y: 800.0 + 10 * (y - 2014) for y in years}}
    precip = {y: (240.0 if y in dry else 420.0, 10) for y in years}
    r = PW.build("podlaskie", "pszenica", 2026, prices=prices, yields=yields, precip=precip)
    raw_dry = sum(yields[("pszenica_ozima", "podlaskie")][y] for y in dry) / 3
    raw_rest = sum(v for y, v in yields[("pszenica_ozima", "podlaskie")].items() if y not in dry) / 9
    assert raw_dry > raw_rest and r["dry_years"] == [2023, 2024, 2025]
    assert "niższy od typowego dla tamtych lat" in r["summary_pl"] and "cena skupu podobna" in r["summary_pl"]
    assert PW.theil_sen([(1, 1.0), (2, 2.0), (3, 3.0), (4, 40.0), (5, 5.0)])[0] == 1.0 and PW.theil_sen([(1, 1.0)]) is None


def test_only_years_before_to_year_and_no_summary_below_six_full_years():
    prices, yields, precip = synth()
    r = PW.build("podlaskie", "pszenica", 2018, prices=prices, yields=yields, precip=precip)
    assert [x["year"] for x in r["years"]] == [2013, 2014, 2015, 2016, 2017]
    assert r["summary_pl"] is None and r["dry_years"] == []
    # brak opadu w części lat = te lata nie wchodzą do wniosku (dane zostają z null)
    few = {y: v for y, v in precip.items() if y >= 2020}
    r = PW.build("podlaskie", "pszenica", 2025, prices=prices, yields=yields, precip=few)
    assert r["years"][0]["precip_mm"] is None and r["years"][0]["price_pln_t"] == 800.0 and r["summary_pl"] is None


def test_crop_without_gus_price_is_unavailable_and_region_names():
    r = PW.build("podlaskie", "truskawki", 2025, prices={}, yields={}, precip={})
    assert r["unavailable"] is True and r["note_pl"] == "brak cen skupu GUS dla tej uprawy" and r["years"] == []
    assert PW.region_key("PL") == "PL" and PW.region_key("polska") == "PL"
    assert PW.region_key("Podlaskie") == "podlaskie" and PW.region_key("lodzkie") == "łódzkie" and PW.region_key("20") == "podlaskie"
    assert PW.region_key("mars") is None
    assert PW.region_phrase("kujawsko-pomorskie")[1] == "w województwie kujawsko-pomorskim" and PW.region_phrase("PL")[1] == "w Polsce"
    assert PW.product_for("zboza_ozime") == "pszenica" and PW.product_for("ziemniak") == "ziemniaki" and PW.product_for("chmiel") is None


def test_season_precip_needs_90_pct_of_season_days():
    start = np.datetime64("2020-01-01", "D")
    days = 366 + 365
    data = np.full((days, 3), 10, dtype=np.int16)  # 1,0 mm dziennie
    a = (np.datetime64("2020-04-01", "D") - start).astype(int)
    data[a:a + 10, 1] = -1    # stacja 1: 10 dni braku z 183 (95% dni) – liczy się, suma uzupełniona do pełnego sezonu
    data[a:a + 60, 2] = -1    # stacja 2: 60 dni braku (67% dni) – odpada
    st = imgw.Store(codes=np.array(["a", "b", "c"]), names=np.array(["A", "B", "C"]), kinds=np.array(["opad"] * 3),
                    lon=np.array([22.9, 23.0, 23.1]), lat=np.array([53.2, 53.3, 53.4]), start=start, data=data)
    out = PW.season_precip(st, np.array([0, 1, 2]), range(2019, 2023))
    assert out[2020] == (183.0, 2) and out[2021] == (183.0, 3)
    assert 2019 not in out and 2022 not in out  # sezon poza magazynem


def test_real_data_podlaskie_and_poland_wheat():
    from app.core.config import settings

    settings.imgw_enabled = True  # magazyn opadów z repo (conftest przywraca ustawienie po teście)
    PW.clear_cache()
    c = TestClient(app)
    r = c.get("/api/price-weather", params={"region": "podlaskie", "crop": "pszenica_ozima", "to_year": 2026})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["region_label"] == "woj. podlaskie" and [y["year"] for y in b["years"]] == list(range(2013, 2026))
    full = [y for y in b["years"] if None not in (y["precip_mm"], y["price_pln_t"], y["yield_t_ha"])]
    assert len(full) >= 6 and all(150 < y["precip_mm"] < 800 and 400 < y["price_pln_t"] < 2500 and 1 < y["yield_t_ha"] < 10 for y in full)
    assert b["summary_pl"].startswith("W najsuchszych latach (") and "w województwie podlaskim" in b["summary_pl"]
    assert set(b["dry_years"]) <= {y["year"] for y in full}
    pl = c.get("/api/price-weather", params={"region": "PL", "crop": "pszenica", "to_year": 2026}).json()
    assert pl["region_label"] == "Polska" and "w Polsce" in pl["summary_pl"] and b["years"] != pl["years"]
    assert c.get("/api/price-weather", params={"region": "PL", "crop": "truskawki"}).json()["unavailable"] is True
    assert c.get("/api/price-weather", params={"region": "atlantyda", "crop": "pszenica"}).status_code == 422
