"""A1: historia pogody 10 lat, ET0 FAO-56, bilans wody – bez sieci (fikstury w tests/fixtures/).

Fikstury są SYNTETYCZNE (tests/fixtures/make_weather_fixtures.py) – mają tylko kształt odpowiedzi API.
"""

import asyncio
import json
import time
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis.et0 import DailyWeather, apply_et0, et0_penman_monteith
from app.analysis.water_balance import build_history, default_season_start, history_range, longest_run
from app.core.config import settings
from app.core.http import SourceError, close_client
from app.main import app
from app.routers.analysis import load_weather_history
from app.sources import weather_openmeteo, weather_power

FIX = Path(__file__).parent / "fixtures"
NASA = json.loads((FIX / "nasa_power_2017_2018.json").read_text(encoding="utf-8"))
OM = json.loads((FIX / "open_meteo_archive_2017_2018.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clean():
    weather_power.clear_cache()
    weather_openmeteo.clear_archive_cache()
    yield
    weather_power.clear_cache()
    weather_openmeteo.clear_archive_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def synth(start: date, end: date, precip, et0) -> DailyWeather:
    """Seria syntetyczna: precip/et0 = funkcje tablicy lat (np.ndarray[int]) -> np.ndarray."""
    dates = np.arange(np.datetime64(start, "D"), np.datetime64(end, "D") + np.timedelta64(1, "D"), dtype="datetime64[D]")
    years = dates.astype("datetime64[Y]").astype(int) + 1970
    n = len(dates)
    w = DailyWeather(
        dates=dates,
        precip=np.asarray(precip(years, dates), dtype=float),
        tmax=np.full(n, 20.0),
        tmin=np.full(n, 10.0),
        lat=52.9,
        lon=22.6,
        elevation_m=130.0,
        source="TEST",
        source_url="",
        resolution="",
    )
    w.et0 = np.asarray(et0(years, dates), dtype=float)
    w.et0_method = np.where(np.isnan(w.et0), "", "PM")
    return w


# Bieżący sezon 2018: opad 1, ET0 3 → KBW −2/dzień. Rok 2017−j (j=0..9): opad 2+0,1·j → KBW −1+0,1·j.
def _precip(years, dates):
    return np.where(years == 2018, 1.0, 2.0 + 0.1 * (2017 - years))


def _et0(years, dates):
    return np.full(len(years), 3.0)


SEASON_DAYS = 136  # 1.03–14.07.2018


# ── parsowanie źródeł ───────────────────────────────────────────────────────────────────────


def test_nasa_parse_nan_elevation_and_methods():
    w = weather_power.parse_response(NASA)
    assert w.dates[0] == np.datetime64("2017-01-01") and w.dates[-1] == np.datetime64("2018-07-14")
    assert w.elevation_m == pytest.approx(132.5)
    i = int((np.datetime64("2018-04-02") - w.dates[0]).astype(int))
    assert np.isnan(w.precip[i])  # -999 -> NaN
    assert np.isnan(w.precip[-3:]).all()  # opóźnienie źródła
    j = int((np.datetime64("2017-05-10") - w.dates[0]).astype(int))
    assert w.et0_method[j] == "HG"  # brak RH -> Hargreaves
    assert (w.et0_method[:j] == "PM").all()
    assert w.method_counts()["HG"] == 1


def test_open_meteo_archive_parse_uses_source_et0():
    w = weather_openmeteo.parse_archive(OM)
    assert w.source == weather_openmeteo.ARCHIVE_SOURCE_SHORT
    assert (w.et0_method[:-2] == "OM").all()  # brak promieniowania/RH/wiatru -> ET0 ze źródła
    assert np.isnan(w.et0[-2:]).all() and np.isnan(w.precip[-2:]).all()
    assert np.isnan(w.rh).all()


def test_nasa_parse_bad_payload():
    with pytest.raises(SourceError):
        weather_power.parse_response({"properties": {}})


# ── ET0 ─────────────────────────────────────────────────────────────────────────────────────


def test_et0_fao56_example18_brussels():
    # FAO-56, przykład 18: Bruksela, 6 lipca, 50°48'N, 100 m – ET0 ≈ 3,9 mm/dzień
    et0 = et0_penman_monteith(
        tmax=np.array([21.5]), tmin=np.array([12.3]), rh_mean=np.array([73.5]),
        u2=np.array([2.078]), rs=np.array([22.07]), lat_deg=50.8, elev_m=100, doy=np.array([187.0]),
    )
    assert et0[0] == pytest.approx(3.9, abs=0.3)


def test_apply_et0_order_pm_om_hg():
    dates = np.array(["2018-07-01", "2018-07-02", "2018-07-03", "2018-07-04"], dtype="datetime64[D]")
    w = DailyWeather(
        dates=dates,
        precip=np.zeros(4),
        tmax=np.array([25.0, 25.0, 25.0, np.nan]),
        tmin=np.array([14.0, 14.0, 14.0, np.nan]),
        rh=np.array([70.0, np.nan, np.nan, np.nan]),
        wind2m=np.array([2.0, 2.0, np.nan, np.nan]),
        radiation=np.array([22.0, 22.0, np.nan, np.nan]),
        et0_provided=np.array([np.nan, 4.4, np.nan, np.nan]),
        lat=52.9, lon=22.6, elevation_m=130, source="T", source_url="", resolution="",
    )
    apply_et0(w)
    assert list(w.et0_method) == ["PM", "OM", "HG", ""]
    assert w.et0[1] == 4.4
    assert 2 < w.et0[2] < 7  # Hargreaves w lipcu – realny zakres
    assert np.isnan(w.et0[3])


# ── sezon i zakres dat ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("analysis", "season"),
    [
        (date(2018, 7, 15), date(2018, 3, 1)),
        (date(2018, 2, 10), date(2017, 3, 1)),  # przed 1 marca -> sezon z poprzedniego roku
        (date(2018, 3, 1), date(2017, 3, 1)),  # ostatni dzień z danymi = 28.02
        (date(2018, 3, 2), date(2018, 3, 1)),
    ],
)
def test_default_season_start(analysis, season):
    assert default_season_start(analysis) == season


def test_history_range_only_before_analysis_date():
    # od 1 XI przed najstarszym sezonem porównawczym (okno zimowe modelu FAO-56, D28)
    # od 1 VIII (rok − 12): ciągły bilans najstarszego sezonu porównawczego + stan początkowy (D28, D30)
    assert history_range(date(2018, 7, 15)) == (date(2006, 8, 1), date(2018, 7, 14))
    assert history_range(date(2018, 2, 10)) == (date(2006, 8, 1), date(2018, 2, 9))


# ── bilans narastająco i pasmo ──────────────────────────────────────────────────────────────


def test_cumulative_balance_and_band():
    w = synth(date(2008, 1, 1), date(2018, 7, 14), _precip, _et0)
    r = build_history(w, date(2018, 7, 15))
    h = r.history
    assert h.season_start == date(2018, 3, 1)
    assert len(h.balance_cumulative) == SEASON_DAYS
    assert h.balance_cumulative[0].value == -2.0
    assert h.balance_cumulative[-1].date == date(2018, 7, 14)
    assert h.balance_cumulative[-1].value == pytest.approx(-2.0 * SEASON_DAYS)
    last = h.balance_band[-1]
    assert last.min == pytest.approx(-1.0 * SEASON_DAYS)  # 2017
    assert last.max == pytest.approx(-0.1 * SEASON_DAYS)  # 2008
    assert last.mean == pytest.approx(-0.55 * SEASON_DAYS)
    assert r.band_years == list(range(2017, 2007, -1))
    assert r.deviation_mm == pytest.approx(-2.0 * SEASON_DAYS + 0.55 * SEASON_DAYS, abs=0.1)
    assert r.lower_years == 0 and r.percentile == 0.0
    assert h.stress_days_by_year == []  # wypełni model wody w glebie (A3)
    # pola dodane do kontraktu (contract-changes 2026-11-21)
    assert h.balance_deviation_mm == pytest.approx(-1.45 * SEASON_DAYS, abs=0.1)
    assert (h.balance_rank.lower_years, h.balance_rank.of_years) == (0, 10)
    assert h.longest_dry_spell.days == 0 and h.longest_dry_spell.end_date is None
    assert h.band_years == list(range(2017, 2007, -1))
    assert h.source_tag.kind == "obliczenia" and h.source_tag.date == date(2018, 7, 14)
    assert "Niższy bilans był w 0 z 10 lat" in h.summary
    assert r.limitations == []


def test_monthly_precip_vs_long_term_mean():
    w = synth(date(2008, 1, 1), date(2018, 7, 14), _precip, _et0)
    months = {m.month: m for m in build_history(w, date(2018, 7, 15)).history.monthly_precip}
    assert sorted(months) == [3, 4, 5, 6, 7]
    assert months[3].current_mm == 31.0 and months[3].mean_mm == pytest.approx(31 * 2.45, abs=0.1)
    # lipiec niepełny: porównanie tych samych dni (1–14)
    assert months[7].current_mm == 14.0 and months[7].mean_mm == pytest.approx(14 * 2.45, abs=0.1)


def test_season_before_march_uses_previous_year():
    w = synth(date(2007, 1, 1), date(2018, 2, 9), _precip, _et0)
    r = build_history(w, date(2018, 2, 10))
    assert r.season_start == date(2017, 3, 1)
    assert r.history.balance_cumulative[-1].date == date(2018, 2, 9)
    assert len(r.band_years) == 10 and r.band_years[0] == 2016


def test_longest_dry_spell():
    def precip(years, dates):
        p = _precip(years, dates)
        dry = (dates >= np.datetime64("2018-05-01")) & (dates <= np.datetime64("2018-05-20"))
        return np.where(dry, 0.0, p)

    r = build_history(synth(date(2008, 1, 1), date(2018, 7, 14), precip, _et0), date(2018, 7, 15))
    assert r.longest_dry_spell_days == 20
    assert r.longest_dry_spell_end == date(2018, 5, 20)
    assert r.history.longest_dry_spell.days == 20 and r.history.longest_dry_spell.end_date == date(2018, 5, 20)
    assert longest_run(np.array([True, True, False, True, True, True])) == (3, 5)


def test_missing_days_and_source_lag_are_reported():
    def precip(years, dates):
        p = _precip(years, dates).astype(float)
        p[dates == np.datetime64("2018-04-10")] = np.nan  # dziura w sezonie
        p[dates >= np.datetime64("2018-07-10")] = np.nan  # opóźnienie źródła
        p[(years == 2012) & (dates.astype("datetime64[M]") == np.datetime64("2012-05"))] = np.nan  # 31 dni
        return p

    r = build_history(synth(date(2008, 1, 1), date(2018, 7, 14), precip, _et0), date(2018, 7, 15))
    assert r.data_until == date(2018, 7, 9)
    assert r.missing_days_season == 1
    assert 2012 in r.excluded_years and 2012 not in r.band_years
    text = " ".join(r.limitations)
    assert "Dane pogodowe do dnia 09.07.2018" in text
    assert "1 dni bez danych" in text
    assert "2012" in text
    assert r.history.period_end == date(2018, 7, 9)


def test_no_data_in_season_gives_empty_history():
    w = synth(date(2008, 1, 1), date(2018, 7, 14), lambda y, d: np.full(len(y), np.nan), _et0)
    r = build_history(w, date(2018, 7, 15))
    assert r.history.balance_cumulative == [] and r.history.source_tag.kind == "brak_danych"
    assert r.current_balance_mm is None and r.limitations


# ── źródła: retry, cache, przełączenie na Open-Meteo ────────────────────────────────────────


def _run(coro):
    async def go():
        try:
            return await coro
        finally:
            await close_client()

    return asyncio.run(go())


@respx.mock
def test_fallback_to_open_meteo_when_nasa_fails():
    nasa = respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(503))
    respx.get(settings.open_meteo_archive_url).mock(return_value=httpx.Response(200, json=OM))
    load = _run(load_weather_history(22.6, 52.9, date(2018, 7, 15)))
    assert load.fallback_used and load.weather.source == weather_openmeteo.ARCHIVE_SOURCE_SHORT
    assert nasa.call_count == 2  # 1 ponowna próba przy 5xx
    assert "NASA POWER niedostępne" in load.notes[0]


@respx.mock
def test_nasa_429_no_retry_then_fallback():
    nasa = respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(429))
    respx.get(settings.open_meteo_archive_url).mock(return_value=httpx.Response(200, json=OM))
    load = _run(load_weather_history(22.6, 52.9, date(2018, 7, 15)))
    assert nasa.call_count == 1 and load.fallback_used


@respx.mock
def test_nasa_retry_once_then_ok_and_cache():
    nasa = respx.get(settings.nasa_power_url).mock(
        side_effect=[httpx.ConnectError("dns"), httpx.Response(200, json=NASA)]
    )
    load = _run(load_weather_history(22.6, 52.9, date(2018, 7, 15)))
    assert not load.fallback_used and nasa.call_count == 2
    # ta sama okolica (zaokrąglenie 0,1°) – z cache, bez nowego zapytania
    _run(load_weather_history(22.62, 52.93, date(2018, 7, 15)))
    assert nasa.call_count == 2
    sent = nasa.calls.last.request.url.params
    assert sent["start"] == "20060801" and sent["end"] == "20180714"


@respx.mock
def test_both_sources_fail_raises():
    respx.get(settings.nasa_power_url).mock(side_effect=httpx.ReadTimeout("slow"))
    respx.get(settings.open_meteo_archive_url).mock(return_value=httpx.Response(429))
    with pytest.raises(SourceError) as e:
        _run(load_weather_history(22.6, 52.9, date(2018, 7, 15)))
    assert "429" in e.value.message and "nie odpowiada" in e.value.message


# ── endpoint deweloperski ───────────────────────────────────────────────────────────────────


@respx.mock
def test_dev_endpoint_nasa(client):
    respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(200, json=NASA))
    r = client.get("/api/dev/weather-history", params={"lat": 52.9, "lon": 22.6, "date": "2018-07-15"})
    assert r.status_code == 200
    b = r.json()
    assert b["source"]["name"] == "NASA POWER" and b["source"]["resolution"] == "ok. 50 km"
    assert b["source"]["data_until"] == "2018-07-11"
    assert b["source"]["et0_methods"]["HG"] == 1
    assert b["history"]["stress_days_by_year"] == []
    assert b["metrics"]["band_years"] == [2017]  # fikstura ma tylko 2017–2018
    assert b["metrics"]["missing_days_season"] == 1
    lim = " ".join(b["limitations"])
    assert "ok. 50 km" in lim and "Dane pogodowe do dnia 11.07.2018" in lim and "2016" in lim


@respx.mock
def test_dev_endpoint_fallback_and_errors(client):
    respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(500))
    om = respx.get(settings.open_meteo_archive_url).mock(return_value=httpx.Response(200, json=OM))
    r = client.get("/api/dev/weather-history", params={"lat": 52.9, "lon": 22.6, "date": "2018-07-15"})
    assert r.status_code == 200 and r.json()["source"]["fallback_used"] is True
    assert r.json()["source"]["et0_methods_season"]["OM"] > 100
    om.mock(return_value=httpx.Response(429))
    weather_openmeteo.clear_archive_cache()
    assert client.get("/api/dev/weather-history", params={"lat": 52.9, "lon": 22.6, "date": "2018-07-15"}).status_code == 502
    assert client.get("/api/dev/weather-history", params={"lat": 48.8, "lon": 2.3}).status_code == 404
    assert client.get("/api/dev/weather-history", params={"lat": 52.9, "lon": 22.6, "date": "2999-01-01"}).status_code == 422


# ── test na żywo (pytest -m live -s) ────────────────────────────────────────────────────────


@pytest.mark.live
def test_live_2018_drought_below_average():
    """Działka 201305_2.0038.6/1 (ok. 52,9 N, 22,6 E), 15.07.2018 – sezon 2018 poniżej średniej."""
    t0 = time.perf_counter()
    load = _run(load_weather_history(22.6, 52.9, date(2018, 7, 15)))
    elapsed = time.perf_counter() - t0
    r = build_history(load.weather, date(2018, 7, 15))
    print(
        f"\n[LIVE] źródło={load.weather.source} zapasowe={load.fallback_used} pobieranie={elapsed:.2f} s"
        f"\n[LIVE] bilans 1.03–{r.data_until}: {r.current_balance_mm} mm; średnia {r.band_years[-1]}–{r.band_years[0]}:"
        f" {r.mean_balance_mm} mm; odchylenie {r.deviation_mm} mm; niższy w {r.lower_years}/{len(r.band_years)} lat"
        f"\n[LIVE] najdłużej bez opadu: {r.longest_dry_spell_days} dni (do {r.longest_dry_spell_end});"
        f" ET0 sezon: {r.et0_methods_season}; ograniczenia: {r.limitations}"
        f"\n[LIVE] opady miesięczne: {[(m.month, m.current_mm, m.mean_mm) for m in r.history.monthly_precip]}"
    )
    assert r.data_until == date(2018, 7, 14)
    assert len(r.band_years) == 10
    assert r.deviation_mm < 0, "sezon 2018 (rok suszy) powinien wyjść poniżej średniej"
