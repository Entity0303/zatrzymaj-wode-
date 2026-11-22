"""A3/A3b: uprawy (FAO-56, kalendarz PL) i ciągły model wody w glebie – bez sieci."""

import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path
from typing import get_args

import httpx
import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis.crops import CROPS, KC_BARE, KC_DORMANT, ZE_M, ZR_DORMANT_M, get_crop
from app.analysis.et0 import DailyWeather
from app.analysis.water_balance import (
    MAX_DOSE_MM,
    HorizonDay,
    State,
    _resize,
    climatology_horizon,
    effective_precip,
    initial_state,
    kr_coefficient,
    ks_coefficient,
    risk_class,
    run,
    soil_water_model,
    taw_from_wod,
    to_contract,
    window_start,
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
# pszenica „jak nawadniana” – do testów planu dawek (prawdziwych zbóż w PL się nie nawadnia, D48)
WHEAT_IRR = dataclasses.replace(WHEAT, irrigation_practice="common")
WOD = 150.0


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
    """precip/et0: funkcje (lata, miesiące, daty) -> tablica."""
    dates = np.arange(np.datetime64(start, "D"), np.datetime64(end, "D") + np.timedelta64(1, "D"), dtype="datetime64[D]")
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    months = dates.astype("datetime64[M]").astype(int) % 12 + 1
    n = len(dates)
    w = DailyWeather(
        dates=dates, precip=np.asarray(precip(years, months, dates), float), tmax=np.full(n, 20.0),
        tmin=np.full(n, 10.0), lat=52.9, lon=22.6, elevation_m=130.0, source="TEST", source_url="", resolution="",
    )
    w.et0 = np.asarray(et0(years, months, dates), float)
    w.et0_method = np.full(n, "PM")
    return w


def _et0_seasonal(years, months, dates):
    return np.select([np.isin(months, [11, 12, 1, 2]), np.isin(months, [3, 10]), np.isin(months, [4, 9])],
                     [0.5, 1.5, 2.5], default=4.0)


def _wet(years, months, dates):
    return np.full(len(years), 4.5)


def _dry_2018(years, months, dates):
    """Mokro przez wszystkie lata, w sezonie 2018 (od VIII 2017) prawie bez deszczu."""
    dry = dates >= np.datetime64("2017-08-01")
    return np.where(dry, 0.2, 4.5)


# ── uprawy ──────────────────────────────────────────────────────────────────────────────────


def test_all_15_crops_match_contract_and_calendar():
    assert set(CROPS) == set(get_args(CropId))
    for c in CROPS.values():
        assert c.length == (date(2001, *c.harvest) - date(2001, *c.start)).days + 1  # fazy przeskalowane
        assert 0 < c.p < 1 and c.source
    harvest = {"zboza_ozime": (7, 20), "zboza_jare": (8, 5), "rzepak": (7, 15), "kukurydza_ziarno": (10, 10),
               "kukurydza_kiszonka": (9, 15), "ziemniak": (9, 15), "burak_cukrowy": (10, 20)}
    for cid, h in harvest.items():
        assert CROPS[cid].harvest == h
    assert WHEAT.season(2018) == (date(2018, 3, 1), date(2018, 7, 20)) and WHEAT.length == 142


def test_kc_and_phases_scaled():
    a, b, c, d = WHEAT.phases  # proporcje 20/60/50/30 przeskalowane do 142 dni
    assert a + b + c + d == 142
    assert WHEAT.kc(0) == 0.70 and WHEAT.stage(0) == "poczatkowa"
    assert WHEAT.kc(a + b) == 1.15 and WHEAT.stage(a + b) == "pelnia"
    assert WHEAT.kc(141) == pytest.approx(0.30) and WHEAT.stage(141) == "dojrzewanie"
    assert WHEAT.kc(142) is None


def test_root_growth_linear_from_sowing():
    grow = MAIZE.phases[0] + MAIZE.phases[1]
    assert MAIZE.root_depth(0) == ZE_M
    assert MAIZE.root_depth(grow // 2) == pytest.approx(ZE_M + (MAIZE.root_depth_m - ZE_M) * (grow // 2) / grow)
    assert MAIZE.root_depth(grow) == MAIZE.root_depth_m
    assert WHEAT.root_depth(0) == ZR_DORMANT_M  # oziminy po zimie


@pytest.mark.parametrize(
    ("crop", "d", "phase", "sensitive"),
    [
        ("zboza_ozime", date(2018, 1, 15), "spoczynek_zimowy", False),
        ("zboza_ozime", date(2018, 4, 20), "rozwoj", True),
        ("zboza_ozime", date(2018, 7, 15), "dojrzewanie", False),
        ("zboza_ozime", date(2018, 8, 10), "po_zbiorze", False),
        ("zboza_ozime", date(2018, 10, 5), "wschody_jesienne", False),
        ("zboza_ozime", date(2018, 11, 21), "spoczynek_zimowy", False),
        ("kukurydza_ziarno", date(2018, 4, 10), "przed_siewem", False),
        ("kukurydza_ziarno", date(2018, 5, 5), "poczatkowa", True),
        ("kukurydza_ziarno", date(2018, 10, 20), "po_zbiorze", False),
        ("drzewa_owocowe", date(2018, 12, 1), "spoczynek_zimowy", False),
        ("rzepak_jesien", date(2018, 6, 1), "przed_siewem", False),
        ("rzepak_jesien", date(2018, 9, 1), "poczatkowa", True),
        ("rzepak_jesien", date(2019, 1, 10), "spoczynek_zimowy", False),
    ],
)
def test_crop_phase_calendar(crop, d, phase, sensitive):
    info = get_crop(crop).day_info(d)
    assert info.phase == phase and info.sensitive is sensitive
    if phase in ("przed_siewem", "po_zbiorze"):
        assert info.bare and info.kc == KC_BARE and info.zr == ZE_M
    if phase == "spoczynek_zimowy":
        assert info.kc == KC_DORMANT
    if crop == "zboza_ozime" and phase == "wschody_jesienne":
        assert info.season_year == d.year + 1  # wschody należą do następnego sezonu


# ── TAW, RAW, Ks, Kr, warstwy ───────────────────────────────────────────────────────────────


def test_taw_scaled_to_root_depth():
    assert taw_from_wod(150, 1.5) == 150 and taw_from_wod(150, 0.5) == 75


def test_ks_and_kr():
    assert ks_coefficient(50, 100, 50) == 1.0 and ks_coefficient(75, 100, 50) == 0.5
    assert kr_coefficient(5, 18, 9) == 1.0 and kr_coefficient(13.5, 18, 9) == 0.5 and kr_coefficient(18, 18, 9) == 0.0


def test_effective_precip_runoff():
    np.testing.assert_allclose(effective_precip(np.array([10.0, 30.0, 50.0])), [10.0, 28.0, 44.0])


def test_resize_keeps_total_depletion():
    st = State(d1=6.0, d2=44.0, zr=0.12)  # profil 1 m
    _resize(st, 0.56, WOD)  # korzenie rosną – plaster z warstwy dolnej
    assert st.total() == pytest.approx(50.0) and st.d1 == pytest.approx(6.0 + 44.0 * 0.44 / 0.88)
    _resize(st, ZE_M, WOD)  # zbiór – strefa maleje
    assert st.total() == pytest.approx(50.0) and st.zr == ZE_M


# ── ciągły bilans ───────────────────────────────────────────────────────────────────────────


def test_winter_recharge_refills_profile_with_percolation():
    days = [date(2017, 11, 1) + timedelta(days=k) for k in range(120)]
    st = State(d1=0.12 * WOD * 0.6, d2=0.88 * WOD * 0.6, zr=ZR_DORMANT_M)  # 60% ubytku po lecie
    st.zr = ZR_DORMANT_M
    tr = run(WHEAT, WOD, days, np.full(120, 3.0), np.full(120, 0.5), st)
    assert tr.dtot[0] > 80 and tr.dtot[-1] < 1.0  # zostaje tylko parowanie ostatniego dnia
    assert tr.dp.sum() > 0  # nadmiar przesiąka


def test_no_reset_at_sowing_dry_spring_maize_starts_with_deficit():
    w_dry = synth(date(2006, 8, 1), date(2018, 7, 14), _dry_2018, _et0_seasonal)
    st, bal = initial_state(w_dry, MAIZE, WOD, window_start(MAIZE, 2018))
    assert bal < 0 and st.total() > 0  # suche lato–jesień 2017 → profil niepełny na 1 XI
    days = [date(2017, 11, 1) + timedelta(days=k) for k in range((date(2018, 5, 1) - date(2017, 11, 1)).days)]
    i0 = int((np.datetime64("2017-11-01") - w_dry.dates[0]).astype(int))
    tr = run(MAIZE, WOD, days, w_dry.precip[i0 : i0 + len(days)], w_dry.et0[i0 : i0 + len(days)], st)
    assert tr.dtot[-1] > 0.3 * WOD  # 30 IV: deficyt nie zniknął
    r_dry = soil_water_model(w_dry, MAIZE, WOD, date(2018, 7, 15))
    w_wet = synth(date(2006, 8, 1), date(2018, 7, 14), _wet, _et0_seasonal)
    r_wet = soil_water_model(w_wet, MAIZE, WOD, date(2018, 7, 15))
    assert r_dry.stress_days_season > r_wet.stress_days_season == 0
    assert r_dry.stress_days_season > (r_dry.mean_prev_stress_days or 0)


# ── model na datę analizy ───────────────────────────────────────────────────────────────────


def test_ripening_no_alarm_no_irrigation():
    w = synth(date(2006, 8, 1), date(2018, 7, 14), _dry_2018, _et0_seasonal)
    r = soil_water_model(w, WHEAT_IRR, WOD, date(2018, 7, 15))
    assert r.phase == "dojrzewanie" and not r.sensitive and r.scope == "strefa_korzeni"
    assert r.irrigation.status == "nieuzasadnione_w_fazie" and r.days_to_stress is None
    assert r.stress_days_season > 0  # stres z faz wrażliwych sezonu policzony
    out = to_contract(r, WHEAT_IRR, date(2018, 7, 15))
    assert out.risk_7d.value is None and out.risk_7d.label == "Nie dotyczy"
    assert "poza fazą wrażliwą" in out.risk_7d.note
    assert out.irrigation.status == "nieuzasadnione_w_fazie" and out.irrigation_rec is None


def test_after_harvest_no_irrigation_but_water_state_and_season_summary():
    w = synth(date(2006, 8, 1), date(2018, 8, 9), _dry_2018, _et0_seasonal)
    r = soil_water_model(w, WHEAT_IRR, WOD, date(2018, 8, 10))
    assert r.phase == "po_zbiorze" and r.irrigation.status == "nieuzasadnione_w_fazie"
    assert r.water_pct is not None and r.scope == "profil" and r.season_complete
    out = to_contract(r, WHEAT_IRR, date(2018, 8, 10))
    assert out.soil_water.last_season.year == 2018 and out.soil_water.last_season.stress_days == r.stress_days_season


@pytest.mark.parametrize(("category", "dose"), [(1, 17.5), (2, 22.5), (3, 27.5), (4, 32.5), (None, 22.5)])
def test_irrigation_dose_by_soil_category(category, dose):
    w = synth(date(2006, 8, 1), date(2018, 6, 9), _dry_2018, _et0_seasonal)
    r = soil_water_model(w, WHEAT_IRR, WOD, date(2018, 6, 10), soil_category=category)
    assert r.sensitive and r.irrigation.status == "zalecane"
    assert r.irrigation.dose_mm == dose <= MAX_DOSE_MM
    assert r.irrigation.first_date == date(2018, 6, 10) and r.irrigation.total_7d_mm >= dose
    if r.irrigation.doses_7d > 1:
        assert r.irrigation.interval_days >= 2 and "powtórz za ok." in r.irrigation.message
    assert r.irrigation.message.startswith(f"{dose:g}".replace(".", ",") + " mm teraz")


def test_wet_season_irrigation_not_needed():
    w = synth(date(2006, 8, 1), date(2018, 6, 9), _wet, _et0_seasonal)
    r = soil_water_model(w, WHEAT_IRR, WOD, date(2018, 6, 10))
    assert r.irrigation.status == "niepotrzebne" and r.risk == "niskie" and r.stress_days_season == 0


def test_november_state_off_season():
    w = synth(date(2006, 8, 1), date(2018, 11, 20), _dry_2018, _et0_seasonal)
    r = soil_water_model(w, MAIZE, WOD, date(2018, 11, 21))
    assert r.phase == "po_zbiorze" and r.scope == "profil" and r.water_pct is not None
    assert r.description.startswith("poza sezonem") and "niedobór" in r.description
    assert r.rank_of == 10 and r.rank_lower == 0  # suchszy niż każdy z 10 lat
    out = to_contract(r, MAIZE, date(2018, 11, 21))
    assert out.soil_water_pct.value == r.water_pct and out.soil_water.scope == "profil"
    assert out.soil_water.last_season.year == 2018 and out.irrigation.status == "nieuzasadnione_w_fazie"


def test_winter_state_refilling_description():
    def autumn_rain(years, months, dates):
        return np.where(np.isin(months, [12, 1]), 3.0, _dry_2018(years, months, dates))  # doładowanie trwa

    w = synth(date(2006, 8, 1), date(2019, 1, 14), autumn_rain, _et0_seasonal)
    r = soil_water_model(w, WHEAT, WOD, date(2019, 1, 15))
    assert r.phase == "spoczynek_zimowy" and "odbudowuje zapas wody" in r.description


def test_forecast_used_for_today_and_fills_source_lag():
    analysis = date(2018, 6, 10)
    w = synth(date(2006, 8, 1), date(2018, 6, 6), _wet, _et0_seasonal)  # opóźnienie 3 dni
    fc = [HorizonDay(analysis + timedelta(days=k), 0.0, 8.0) for k in range(-3, 16)]
    r = soil_water_model(w, WHEAT, WOD, analysis, forecast=fc)
    assert r.horizon_kind == "prognoza"
    assert any("uzupełnione danymi modelu Open-Meteo" in x for x in r.limitations)
    assert r.days_to_stress is not None and r.risk == risk_class(r.days_to_stress)
    assert to_contract(r, WHEAT, analysis).risk_7d.source_tag.kind == "prognoza"


def test_climatology_scenario_is_median_of_previous_years():
    w = synth(date(2006, 8, 1), date(2018, 7, 31), lambda y, m, d: (2018 - y).astype(float), lambda y, m, d: np.full(len(y), 2.0))
    h = climatology_horizon(w, date(2018, 7, 15), 3)
    assert [x.precip for x in h] == [5.5, 5.5, 5.5] and h[0].et0 == 2.0


@pytest.mark.parametrize(("days", "cls"), [(0, "wysokie"), (3, "wysokie"), (4, "średnie"), (7, "średnie"), (8, "niskie"), (None, "niskie")])
def test_risk_classes(days, cls):
    assert risk_class(days) == cls


# ── endpoint deweloperski ───────────────────────────────────────────────────────────────────


@respx.mock
def test_dev_water_endpoint(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=WCS_201305))
    respx.get(settings.kieg_url).mock(return_value=httpx.Response(200, text=KIEG_CLASSES))
    respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(200, json=NASA))
    r = client.get("/api/dev/water", params={"parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-06-10"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["soil"]["dominant_code"] == 3 and b["crop_season"]["phase"] == "pelnia"
    assert b["soil_water_pct"]["value"] is not None and b["soil_water"]["scope"] == "strefa_korzeni"
    assert b["irrigation"]["status"] == "nie_praktykowane" and b["irrigation"]["dose_mm"] is None  # D48
    assert b["irrigation"]["message"].startswith("Zbóż w Polsce się nie nawadnia")
    assert b["stress_days_by_year"][0]["year"] == 2018


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
    assert b["irrigation"]["status"] == "brak_danych"


# ── test na żywo (pytest -m live -s) ────────────────────────────────────────────────────────


@pytest.mark.live
def test_live_water_model_table():
    import time

    today = __import__("app.core.clock", fromlist=["today_pl"]).today_pl().isoformat()
    rows = []
    with TestClient(app) as c:
        for pid in ("201305_2.0038.6/1", "061704_2.0011.383/2"):
            for crop in ("zboza_ozime", "kukurydza_ziarno"):
                for d in ("2018-07-15", "2021-07-15", today):
                    t0 = time.perf_counter()
                    r = c.get("/api/dev/water", params={"parcel_id": pid, "crop": crop, "date": d})
                    assert r.status_code == 200, r.text
                    rows.append((pid, crop, d, r.json(), time.perf_counter() - t0))
    print("\n| działka | uprawa | data | faza | woda % | woda mm | dni stresu | sezon vs śr. 10 lat | ryzyko 7 dni | nawadnianie | czas s |")
    for pid, crop, d, b, sec in rows:
        m = b["model"] or {}
        print(f"| {pid} | {crop} | {d} | {b['crop_season']['phase_label']} | {b['soil_water_pct']['value']} "
              f"({b['soil_water']['scope']}) | {b['soil_water_mm']['value']} | {m.get('stress_days_season')} | "
              f"{m.get('stress_days_season')} vs {m.get('mean_prev_stress_days')} | {b['risk_7d']['label']} | "
              f"{b['irrigation']['message']} | {sec:.2f} |")
        assert b["irrigation"]["dose_mm"] is None or b["irrigation"]["dose_mm"] <= 35
        assert b["soil_water_pct"]["value"] is not None
