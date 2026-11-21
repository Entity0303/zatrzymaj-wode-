"""A3: uprawy (FAO-56) i model wody w glebie – bez sieci, dane syntetyczne + fikstury A1/A2."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import get_args

import httpx
import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis.crops import CROPS, get_crop
from app.analysis.et0 import DailyWeather
from app.analysis.water_balance import (
    HorizonDay,
    climatology_horizon,
    effective_precip,
    initial_depletion,
    ks_coefficient,
    risk_class,
    round_dose,
    simulate,
    soil_water_model,
    taw_from_wod,
    to_contract_indicators,
)
from app.core.config import settings
from app.main import app
from app.schemas.analysis import CropId
from app.sources import iung, kieg, uldk, weather_openmeteo, weather_power

FIX = Path(__file__).parent / "fixtures"
NASA = json.loads((FIX / "nasa_power_2017_2018.json").read_text(encoding="utf-8"))
WCS_201305 = (FIX / "iung_wcs_201305.txt").read_text(encoding="utf-8")
KIEG_CLASSES = (FIX / "kieg_201305_klasy.html").read_text(encoding="utf-8")
WKT_201305 = (
    "POLYGON((741326.598870282 582135.860610104,741196.719087438 582172.956309767,"
    "741196.080461016 582126.579753392,741319.716303976 582092.766677043,"
    "741323.823760127 582113.17232317,741326.598870282 582135.860610104))"
)
ULDK_ONE = f"0\nSRID=2180;{WKT_201305}|201305_2.0038.6/1|podlaskie|powiat wysokomazowiecki|Kobylin-Borzymy|Wnory-Wandy|6/1\n"
WHEAT = get_crop("zboza_ozime")
MAIZE = get_crop("kukurydza_ziarno")


@pytest.fixture(autouse=True)
def _clean():
    for m in (iung, kieg, uldk, weather_power):
        m.clear_cache()
    weather_openmeteo.clear_archive_cache()
    weather_openmeteo.clear_cache()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def synth(start: date, end: date, precip, et0) -> DailyWeather:
    """precip/et0: funkcje (lata, daty) -> tablica."""
    dates = np.arange(np.datetime64(start, "D"), np.datetime64(end, "D") + np.timedelta64(1, "D"), dtype="datetime64[D]")
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    n = len(dates)
    w = DailyWeather(
        dates=dates, precip=np.asarray(precip(years, dates), float), tmax=np.full(n, 20.0), tmin=np.full(n, 10.0),
        lat=52.9, lon=22.6, elevation_m=130.0, source="TEST", source_url="", resolution="",
    )
    w.et0 = np.asarray(et0(years, dates), float)
    w.et0_method = np.full(n, "PM")
    return w


# ── uprawy ──────────────────────────────────────────────────────────────────────────────────


def test_all_15_crops_match_contract():
    assert set(CROPS) == set(get_args(CropId))
    for c in CROPS.values():
        assert 0 < c.kc_ini <= 1.2 and 0 < c.kc_mid <= 1.25 and 0 < c.kc_end <= 1.2
        assert 0 < c.p < 1 and 0.2 <= c.root_depth_m <= 2.0 and c.source
    for cid in ("drzewa_owocowe", "krzewy_owocowe", "truskawki", "chmiel"):
        assert CROPS[cid].season(2024) == (date(2024, 4, 1), date(2024, 10, 31))
    assert CROPS["zboza_ozime"].start == (3, 1) and CROPS["rzepak"].start == (3, 1)
    assert CROPS["kukurydza_ziarno"].start == (5, 1) and CROPS["ziemniak"].start == (4, 20)
    assert CROPS["burak_cukrowy"].start == (4, 1) and CROPS["rzepak_jesien"].start == (8, 20)
    assert date(2024, 4, 1) <= date(2024, *CROPS["zboza_jare"].start) <= date(2024, 4, 15)


def test_kc_by_stage():
    c = WHEAT  # 20 / 60 / 50 / 30 dni; Kc 0,70 / 1,15 / 0,30
    assert c.kc(0) == 0.70 and c.kc(19) == 0.70 and c.stage(19) == "początkowa"
    assert c.kc(20) == pytest.approx(0.70 + 0.45 / 60) and c.stage(20) == "rozwoju"
    assert c.kc(79) == pytest.approx(1.15) and c.kc(80) == 1.15 and c.stage(100) == "pełni rozwoju"
    assert c.kc(159) == pytest.approx(0.30) and c.stage(159) == "dojrzewania"
    assert c.kc(160) is None and c.kc(-1) is None
    assert c.season(2018) == (date(2018, 3, 1), date(2018, 8, 7))


# ── TAW, RAW, Ks, opad efektywny ────────────────────────────────────────────────────────────


def test_taw_scaled_to_root_depth():
    assert taw_from_wod(150, 1.5) == 150  # korzenie głębsze niż 1 m – bez zwiększania
    assert taw_from_wod(150, 0.5) == 75  # ziemniak: połowa profilu
    assert taw_from_wod(150, 0.3) == pytest.approx(45)
    taw = taw_from_wod(150, MAIZE.root_depth_m)
    assert MAIZE.p * taw == pytest.approx(82.5)


def test_ks_fao56_eq84():
    assert ks_coefficient(50, 100, 50) == 1.0
    assert ks_coefficient(75, 100, 50) == 0.5
    assert ks_coefficient(100, 100, 50) == 0.0


def test_effective_precip_runoff():
    np.testing.assert_allclose(effective_precip(np.array([10.0, 30.0, 50.0])), [10.0, 28.0, 44.0])


# ── bilans dzienny ──────────────────────────────────────────────────────────────────────────


def test_drought_leads_to_stress_rain_does_not():
    n = 30
    dry = simulate(np.zeros(n), np.full(n, 5.0), np.ones(n), taw=100, raw=50, dr0=0)
    assert dry.dr[9] == pytest.approx(50)  # 10 dni × 5 mm
    assert dry.stress_days > 0 and (dry.ks[11:] < 1).all()
    assert (np.diff(dry.dr[10:]) < 5).all()  # Ks < 1 spowalnia przesuszanie
    assert dry.dr.max() <= 100
    wet = simulate(np.full(n, 10.0), np.full(n, 5.0), np.ones(n), taw=100, raw=50, dr0=0)
    assert wet.stress_days == 0 and wet.dr.max() == 0


def test_percolation_above_field_capacity():
    r = simulate(np.array([30.0, 0.0]), np.array([0.0, 2.0]), np.ones(2), taw=100, raw=50, dr0=10)
    assert r.dp[0] == pytest.approx(18.0)  # 30 − 20% z 10 mm = 28 mm efektywne; ubytek 10 → nadmiar 18
    assert r.dr[0] == 0 and r.dr[1] == pytest.approx(2.0)


def test_missing_day_keeps_state():
    r = simulate(np.array([0.0, np.nan, 0.0]), np.array([3.0, 3.0, 3.0]), np.ones(3), taw=100, raw=50, dr0=0)
    assert r.missing == 1 and list(r.dr) == [3.0, 3.0, 6.0]


def test_initial_depletion_from_winter_deficit():
    w = synth(date(2017, 11, 1), date(2018, 3, 31), lambda y, d: np.zeros(len(y)), lambda y, d: np.full(len(y), 0.5))
    dr0, bal, start = initial_depletion(w, date(2018, 3, 1), taw=150)
    assert start == date(2017, 11, 1)
    assert bal == pytest.approx(-0.5 * 120)  # 120 dni XI–II
    assert dr0 == pytest.approx(60)
    wet = synth(date(2017, 11, 1), date(2018, 3, 31), lambda y, d: np.full(len(y), 2.0), lambda y, d: np.full(len(y), 0.5))
    assert initial_depletion(wet, date(2018, 3, 1), taw=150)[0] == 0.0  # dodatni bilans → profil pełny


# ── model na datę analizy ───────────────────────────────────────────────────────────────────


def _dry_2018(years, dates):
    return np.where(years == 2018, 0.3, 3.0)  # 2018 sucho, wcześniej mokro


def _et0_3(years, dates):
    return np.full(len(years), 3.0)


def test_model_dry_year_stress_vs_previous_years():
    w = synth(date(2007, 11, 1), date(2018, 7, 14), _dry_2018, _et0_3)
    r = soil_water_model(w, WHEAT, 150, date(2018, 7, 15))
    assert r.season_status == "w_sezonie" and r.day_of_season == 137
    assert r.taw_mm == 150 and r.raw_mm == 82.5
    assert r.raw_exceeded and r.stress_days_season > 30
    assert len(r.stress_by_year) == 11 and r.stress_by_year[0][0] == 2018
    assert all(d == 0 for _, d in r.stress_by_year[1:])  # mokre lata – bez stresu
    assert r.mean_prev_stress_days == 0
    assert r.horizon_kind == "scenariusz" and r.days_to_stress == 0 and r.risk == "wysokie"
    assert r.irrigation.needed and r.irrigation.dose_mm % 5 == 0 and r.irrigation.when == date(2018, 7, 15)
    ind = to_contract_indicators(r, WHEAT, date(2018, 7, 15))
    assert ind.soil_water_pct.value == r.water_pct and ind.soil_water_pct.source_tag.kind == "szacunek_modelu"
    assert ind.risk_7d.source_tag.kind == "szacunek_modelu" and "scenariusz typowej pogody" in ind.risk_7d.note
    assert ind.stress_days_by_year[0].is_current and ind.irrigation.category == "nawadnianie"


def test_model_wet_year_no_stress_no_irrigation():
    w = synth(date(2007, 11, 1), date(2018, 7, 14), lambda y, d: np.full(len(y), 4.0), _et0_3)
    r = soil_water_model(w, WHEAT, 150, date(2018, 7, 15))
    assert r.stress_days_season == 0 and r.water_pct == 100 and not r.raw_exceeded
    assert r.risk == "niskie" and not r.irrigation.needed
    assert r.percolation_mm > 0


def test_model_winter_deficit_lowers_start():
    w = synth(date(2007, 11, 1), date(2018, 3, 20), lambda y, d: np.full(len(y), 0.2), lambda y, d: np.full(len(y), 0.8))
    r = soil_water_model(w, WHEAT, 150, date(2018, 3, 21))
    assert r.winter_balance_mm < 0 and r.dr0_mm > 0
    assert any("niepełnym zapasem" in x for x in r.limitations)


def test_forecast_used_for_today_and_fills_source_lag():
    analysis = date(2018, 7, 15)
    w = synth(date(2007, 11, 1), date(2018, 7, 11), lambda y, d: np.full(len(y), 4.0), _et0_3)  # opóźnienie 3 dni
    fc = [HorizonDay(analysis + timedelta(days=k), 0.0, 9.0) for k in range(-3, 16)]  # sucho i gorąco
    r = soil_water_model(w, WHEAT, 150, analysis, forecast=fc)
    assert r.horizon_kind == "prognoza"
    assert any("uzupełnione danymi modelu Open-Meteo" in x for x in r.limitations)
    assert r.days_to_stress is not None and r.days_to_stress > 0
    assert r.risk == risk_class(r.days_to_stress)
    ind = to_contract_indicators(r, WHEAT, analysis)
    assert ind.risk_7d.source_tag.kind == "prognoza" and ind.risk_7d.days_to_stress == r.days_to_stress


def test_climatology_scenario_is_median_of_previous_years():
    w = synth(
        date(2007, 11, 1), date(2018, 7, 31),
        lambda y, d: (2018 - y).astype(float),  # 2017 → 1 mm … 2008 → 10 mm
        lambda y, d: np.full(len(y), 2.0),
    )
    h = climatology_horizon(w, date(2018, 7, 15), 3)
    assert [x.precip for x in h] == [5.5, 5.5, 5.5] and h[0].et0 == 2.0


@pytest.mark.parametrize(("days", "cls"), [(0, "wysokie"), (3, "wysokie"), (4, "średnie"), (7, "średnie"), (8, "niskie"), (None, "niskie")])
def test_risk_classes(days, cls):
    assert risk_class(days) == cls


def test_irrigation_dose_rounding():
    assert round_dose(103) == 105 and round_dose(2) == 5 and round_dose(112.4) == 110


def test_before_season_no_invented_stress():
    w = synth(date(2006, 11, 1), date(2018, 4, 9), _dry_2018, _et0_3)
    r = soil_water_model(w, MAIZE, 150, date(2018, 4, 10))  # kukurydza od 1 V
    assert r.season_status == "przed_sezonem" and r.water_pct is None and r.stress_by_year == []
    ind = to_contract_indicators(r, MAIZE, date(2018, 4, 10))
    assert ind.soil_water_pct.value is None and ind.risk_7d.value is None
    assert "Poza sezonem wegetacji tej uprawy" in ind.soil_water_pct.note
    assert ind.soil_water_pct.source_tag.kind == "brak_danych"


def test_after_season_summary_only():
    w = synth(date(2007, 11, 1), date(2018, 9, 14), _dry_2018, _et0_3)
    r = soil_water_model(w, WHEAT, 150, date(2018, 9, 15))  # sezon do 7 VIII
    assert r.season_status == "po_sezonie" and r.water_pct is None and r.irrigation is None
    assert r.stress_by_year[0] == (2018, r.stress_days_season) and len(r.stress_by_year) == 11
    assert to_contract_indicators(r, WHEAT, date(2018, 9, 15)).soil_water_pct.value is None


# ── endpoint deweloperski ───────────────────────────────────────────────────────────────────


@respx.mock
def test_dev_water_endpoint(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=WCS_201305))
    respx.get(settings.kieg_url).mock(return_value=httpx.Response(200, text=KIEG_CLASSES))
    respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(200, json=NASA))
    r = client.get("/api/dev/water", params={"parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-07-15"})
    assert r.status_code == 200
    b = r.json()
    assert b["soil"]["dominant_code"] == 3 and b["soil"]["classes"] == ["RIIIb", "RIVa", "RIVb"]
    assert b["season"]["status"] == "w_sezonie" and b["model"]["taw_mm"] == pytest.approx(166.2, abs=0.2)
    assert b["soil_water_pct"]["source_tag"]["kind"] == "szacunek_modelu"
    assert b["risk_7d"]["source_tag"]["kind"] == "szacunek_modelu"  # data historyczna → scenariusz
    assert b["stress_days_by_year"][0]["year"] == 2018 and b["stress_days_by_year"][0]["is_current"]
    assert any("poprzednich lat" in x for x in b["limitations"])  # fikstura ma tylko 2017–2018


@respx.mock
def test_dev_water_non_agricultural_parcel(client):
    forest = WCS_201305.split("Band 0:")[0] + "Band 0:\n" + "\n".join(" ".join(["11"] * 26) for _ in range(16)) + "\n"
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=forest))
    respx.get(settings.kieg_url).mock(return_value=httpx.Response(200, text=KIEG_CLASSES))
    respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(200, json=NASA))
    b = client.get("/api/dev/water", params={"parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-07-15"}).json()
    assert b["non_agricultural"] is True and b["soil"]["non_agricultural_reason"] == "las"
    assert b["model"] is None and b["soil_water_pct"]["value"] is None
    assert "nie ma tu zastosowania" in b["soil_water_pct"]["note"]


# ── test na żywo (pytest -m live -s) ────────────────────────────────────────────────────────


@pytest.mark.live
def test_live_water_model_table():
    import time

    today = date.today().isoformat()
    rows = []
    with TestClient(app) as c:
        for pid in ("201305_2.0038.6/1", "061704_2.0011.383/2"):
            for crop in ("zboza_ozime", "kukurydza_ziarno"):
                for d in ("2018-07-15", "2021-07-15", today):
                    t0 = time.perf_counter()
                    r = c.get("/api/dev/water", params={"parcel_id": pid, "crop": crop, "date": d})
                    sec = time.perf_counter() - t0
                    assert r.status_code == 200, r.text
                    rows.append((pid, crop, d, r.json(), sec))
    print("\n| działka | uprawa | data | woda % | woda mm | dni stresu (sezon) | ten rok vs śr. 10 lat | ryzyko 7 dni | nawadnianie | czas s |")
    for pid, crop, d, b, sec in rows:
        m = b["model"] or {}
        cur = b["stress_days_by_year"][0]["stress_days"] if b["stress_days_by_year"] else None
        irr = (f"{b['irrigation']['description'].split(' –')[0]} ({m.get('irrigation_date')})" if b["irrigation"] else
               (m.get("irrigation_text") or "—"))
        print(f"| {pid} | {crop} | {d} | {b['soil_water_pct']['value']} | {b['soil_water_mm']['value']} | "
              f"{m.get('stress_days_season')} | {cur} vs {m.get('mean_prev_stress_days')} | "
              f"{b['risk_7d']['label']} ({b['risk_7d']['note']}) | {irr} | {sec:.2f} |")
        if b["season"] and b["season"]["status"] != "w_sezonie":
            print(f"|   ↳ {b['season']['status']}: {b['limitations'][1] if len(b['limitations']) > 1 else ''}")
