from datetime import date

import numpy as np
import pytest

from app.analysis.et0 import et0_hargreaves, et0_penman_monteith
from app.core.geo import parse_wkt, sample_points
from app.core.http import SourceError
from app.sources import iung, uldk, weather_power

ULDK_OK = (
    "0\n"
    "SRID=2180;POLYGON((741196 582092,741326 582092,741326 582172,741196 582172,741196 582092))"
    "|201305_2.0038.6/1|podlaskie|powiat wysokomazowiecki|Kobylin-Borzymy|WNORY-WANDY|6/1\n"
)


def test_uldk_parse_ok():
    [p] = uldk.parse_response(ULDK_OK)
    assert p.id == "201305_2.0038.6/1"
    assert p.number == "6/1"
    assert p.teryt_commune == "2013052"
    assert p.area_ha == pytest.approx(1.04, abs=0.01)  # 130 m × 80 m
    lon, lat = p.geom_4326.centroid.x, p.geom_4326.centroid.y
    assert 22 < lon < 23.5 and 52.5 < lat < 53.5  # okolice Wysokiego Mazowieckiego


def test_uldk_not_found():
    with pytest.raises(SourceError):
        uldk.parse_response("-1 brak wyników\nbłędny format odpowiedzi XML")


def test_sample_points_inside():
    geom = parse_wkt("POLYGON((0 0,100 0,100 50,0 50,0 0))")
    pts = sample_points(geom, 9)
    assert 1 <= len(pts) <= 9
    assert all(geom.contains(p) for p in pts)


def test_et0_fao56_example18():
    # FAO-56, przykład 18 (Bruksela, 6 lipca): ET0 ≈ 3.9 mm/dzień
    doy = np.array([187.0])
    et0 = et0_penman_monteith(
        tmax=np.array([21.5]), tmin=np.array([12.3]), rh_mean=np.array([73.5]),
        u2=np.array([2.078]), rs=np.array([22.07]), lat_deg=50.8, elev_m=100, doy=doy,
    )
    assert 3.6 < et0[0] < 4.1


def test_et0_hargreaves_reasonable():
    et0 = et0_hargreaves(np.array([25.0]), np.array([12.0]), 52.0, np.array([180.0]))
    assert 3 < et0[0] < 6


def _power_payload():
    days = {"20260701": 0, "20260702": 1, "20260703": 2}
    def block(vals):
        return {k: v for k, v in zip(days, vals)}
    return {
        "geometry": {"coordinates": [20.35, 52.25, 95.0]},
        "properties": {"parameter": {
            "PRECTOTCORR": block([0.0, 12.4, -999]),
            "T2M_MAX": block([28.0, 22.0, 24.0]),
            "T2M_MIN": block([15.0, 13.0, 12.0]),
            "RH2M": block([60.0, 85.0, -999]),
            "WS2M": block([2.0, 3.0, 2.5]),
            "ALLSKY_SFC_SW_DWN": block([25.0, 12.0, -999]),
        }},
    }


def test_power_parse_and_et0():
    w = weather_power.parse_response(_power_payload())
    assert w.dates == [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]
    assert np.isnan(w.precip[2])
    assert list(w.et0_method) == ["PM", "PM", "HG"]  # brak promieniowania -> Hargreaves
    assert w.et0[0] > w.et0[1]  # dzień słoneczny paruje więcej niż pochmurny
    kbw = w.climatic_water_balance
    assert kbw[0] < 0 < kbw[1]


def test_soil_shares_and_wod():
    res = iung.SoilResult([
        iung.SoilSample(0, 0, 2), iung.SoilSample(0, 0, 2), iung.SoilSample(0, 0, 3),
        iung.SoilSample(0, 0, 11), iung.SoilSample(0, 0, None),
    ])
    assert res.dominant == 2
    assert res.shares[2] == 0.5
    assert res.agricultural_share == 0.75
    assert res.wod_mm == pytest.approx((2 * 148.7 + 186.2) / 3, abs=0.1)
