"""Testy rdzenia analizy terenu na sztucznych powierzchniach (bez sieci) – przeniesione bez zmian z prototypu
osoby C (research/terrain/test_terrain.py, gałąź c/research), A6."""

import math

import numpy as np
import pytest

import app.analysis.terrain as T

STEP = 5.0
H = W = 61  # 300 m × 300 m


def square_parcel(i0=20, i1=40, j0=20, j1=40):
    m = np.zeros((H, W), dtype=bool)
    m[i0:i1 + 1, j0:j1 + 1] = True
    return m


def xy():
    jj, ii = np.meshgrid(np.arange(W), np.arange(H))
    return jj * STEP, -ii * STEP  # x = wschód, y = północ (wiersz 0 = północ)


def grid_and_polygon(inside):
    g = T.Grid(e0=500000.0, n0=500000.0, step=STEP, nrows=H, ncols=W)
    ii, jj = np.nonzero(inside)
    e0, e1 = g.e0 + (jj.min() - 0.5) * STEP, g.e0 + (jj.max() + 0.5) * STEP
    n0, n1 = g.n0 - (ii.max() + 0.5) * STEP, g.n0 - (ii.min() - 0.5) * STEP
    ring = np.array([[e0, n0], [e1, n0], [e1, n1], [e0, n1], [e0, n0]])
    return g, [[ring]]


def run(z, inside, **params):
    g, poly = grid_and_polygon(inside)
    return T.analyze_surface(z, STEP, inside, grid=g, params=params, polygons=poly)


# ---------------------------------------------------------------- płaszczyzna nachylona

def test_inclined_plane_single_direction_and_outlet_on_low_side():
    x, y = xy()
    z = 200.0 - 0.05 * x  # 5 % w dół na WSCHÓD
    inside = square_parcel()
    res = run(z, inside)
    f, r = res.facts, res.rasters

    # jeden kierunek spływu D8 w całej działce: na wschód
    recv = r["recv"]
    ii, jj = np.nonzero(inside)
    di = recv[ii, jj] // W - ii
    dj = recv[ii, jj] % W - jj
    assert np.all(di == 0) and np.all(dj == 1)

    assert f["slope_mean_pct"] == pytest.approx(5.0, abs=0.05)
    assert f["main_flow_direction_short"] == "E"
    assert f["flow_consistency"] > 0.99
    # jedno wyjście wody, po niższej (wschodniej) stronie, odprowadza całą działkę
    assert f["n_outlets"] == 1
    out = f["outlets"][0]
    assert out["direction_short"] == "E"
    assert out["share_of_parcel_pct"] == pytest.approx(100.0, abs=0.1)
    oi, oj = r["outlets"][0]["cell"]
    assert oj == 40  # wschodnia krawędź działki
    assert f["n_depressions"] == 0
    assert f["n_hills"] == 0
    # spadek 5 % → stok; pas buforowy w poprzek (linia N–S)
    assert f["zone_share_pct"]["stok"] == pytest.approx(100.0)
    strips = [p for p in f["proposals"] if p["type"] == "pas_buforowy"]
    assert len(strips) == 1
    (lon0, lat0), (lon1, lat1) = strips[0]["line_lonlat"]
    assert abs(lat1 - lat0) > 5 * abs(lon1 - lon0) * math.cos(math.radians(lat0))


def test_accumulation_grows_downslope():
    x, y = xy()
    z = 200.0 - 0.05 * x
    res = run(z, square_parcel())
    acc = res.rasters["acc_m2"]
    row = acc[30, 1:-1]
    assert np.all(np.diff(row) > 0)
    # ostatnia kolumna zbiera cały wiersz siatki
    assert acc[30, -1] == pytest.approx(W * STEP * STEP)


# ---------------------------------------------------------------- misa

def test_bowl_single_depression_in_center():
    x, y = xy()
    cx, cy = 150.0, -150.0
    r2 = (x - cx) ** 2 + (y - cy) ** 2
    z = 100.0 - 0.01 * x - 2.0 * np.exp(-r2 / (2 * 30.0**2))  # misa 2 m na lekkim stoku 1 %
    inside = square_parcel(10, 50, 10, 50)
    res = run(z, inside)
    f, r = res.facts, res.rasters

    assert f["n_depressions"] == 1
    dep = f["largest_depression"]
    assert dep["max_depth_m"] > 1.0
    assert dep["volume_m3"] > 1000
    di, dj = np.unravel_index(np.argmax(r["depth"]), r["depth"].shape)
    assert abs(di - 30) <= 1 and abs(dj - 30) <= 1
    assert r["zones"][30, 30] == T.ZONE_WET

    pond = [p for p in f["proposals"] if p["type"] == "oczko_w_zaglebieniu"]
    assert len(pond) == 1
    assert pond[0]["inflow_gross_m3"] == pytest.approx(pond[0]["catchment_m2"] * 0.020, rel=1e-6)
    assert pond[0]["inflow_runoff_m3"] == pytest.approx(pond[0]["inflow_gross_m3"] * 0.3, rel=1e-6)
    # część działki spływa do misy
    assert f["parcel_share_draining_to_depressions_pct"] > 20


def test_priority_flood_fills_to_spill_level():
    z = np.full((7, 7), 10.0)
    z[3, 3] = 8.0
    z[0, 3] = 9.5  # przelew na krawędzi
    filled, order, parent = T.priority_flood(z)
    assert filled[3, 3] == pytest.approx(10.0)
    assert np.all(filled >= z)
    # porządek: niemalejące wysokości wypełnione
    assert np.all(np.diff(filled.ravel()[order]) >= -1e-12)


# ---------------------------------------------------------------- dwa wzgórza

def test_two_hills_give_two_hilltops():
    x, y = xy()
    g1 = np.exp(-((x - 90) ** 2 + (y + 150) ** 2) / (2 * 25.0**2))
    g2 = np.exp(-((x - 210) ** 2 + (y + 150) ** 2) / (2 * 25.0**2))
    z = 100.0 + 3.0 * g1 + 3.0 * g2
    inside = square_parcel(10, 50, 5, 55)
    res = run(z, inside)
    f = res.facts
    assert f["n_hills"] == 2
    tops = sorted(h["location_lonlat"][0] for h in f["hills"])
    assert tops[0] < tops[1]
    # szczyty blisko (90, -150) i (210, -150)
    tcells = sorted(h["top_cell"] for h in res.rasters["hills"])
    assert {abs(c[1] - 18) <= 1 or abs(c[1] - 42) <= 1 for c in tcells} == {True}
    assert f["zone_share_pct"]["sucha_gorka"] > 0


# ---------------------------------------------------------------- narzędzia

def test_projection_matches_uldk_4326():
    # ten sam wierzchołek działki 201305_2.0038.6/1 z ULDK w srid=2180 i srid=4326
    lon, lat = T.puwg1992_to_wgs84(741326.598870282, 582135.860610104)
    assert float(lon) == pytest.approx(22.6018656335681, abs=1e-7)
    assert float(lat) == pytest.approx(53.0500166295298, abs=1e-7)


def test_parse_wkt_polygon_and_multipolygon():
    p = T.parse_wkt("SRID=2180;POLYGON((0 0,10 0,10 10,0 10,0 0),(2 2,4 2,4 4,2 4,2 2))")
    assert len(p) == 1 and len(p[0]) == 2
    assert T.polygons_area(p) == pytest.approx(96.0)
    mp = T.parse_wkt("MULTIPOLYGON(((0 0,1 0,1 1,0 1,0 0)),((5 5,7 5,7 7,5 7,5 5)))")
    assert len(mp) == 2 and T.polygons_area(mp) == pytest.approx(5.0)
    ins = T.points_in_polygons(np.array([1, 3, 6, 20]), np.array([1, 3, 6, 20]), p)
    assert ins.tolist() == [True, False, True, False]  # (3,3) w dziurze, (20,20) poza


def test_mask_to_rings_area_and_holes():
    m = np.zeros((8, 8), dtype=bool)
    m[1:7, 1:7] = True
    m[3:5, 3:5] = False      # dziura
    m[0, 7] = True           # osobna komórka stykająca się tylko narożnikiem
    polys = T.mask_to_rings(m)

    def area(r):
        x = np.array([p[1] for p in r], float)
        y = -np.array([p[0] for p in r], float)
        return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(y[:-1], x[1:]))

    total = sum(area(pl[0]) + sum(area(h) for h in pl[1:]) for pl in polys)
    assert total == pytest.approx(m.sum())
    assert len(polys) == 2
    assert sorted(len(pl) for pl in polys) == [1, 2]


def test_choose_step_scales_with_area():
    p = T.DEFAULT_PARAMS
    s1 = T.choose_step(1e4, 300, 300, p)
    s20 = T.choose_step(20e4, 650, 650, p)
    assert 4 <= s1 <= 6
    assert 12 <= s20 <= 17
    # limit punktów
    s = T.choose_step(1e4, 2000, 2000, p)
    assert (2000 // s + 1) ** 2 <= p["max_points"] * 1.05


def test_geojson_is_wgs84_featurecollection():
    x, y = xy()
    res = run(200.0 - 0.05 * x, square_parcel())
    gj = res.geojson
    assert gj["type"] == "FeatureCollection"
    layers = {f["properties"]["layer"] for f in gj["features"]}
    assert {"parcel", "zone", "flow_arrow", "outlet", "proposal"} <= layers
    lon, lat = gj["features"][0]["geometry"]["coordinates"][0][0][0]
    assert 14 < lon < 25 and 48 < lat < 55
