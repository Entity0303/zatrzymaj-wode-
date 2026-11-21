"""Testy offline Sentinel-2 (bez sieci): odczyt okna z kafelkowanego GeoTIFF, wskaźniki, maska SCL,
UTM, zdania. Próbka = mały plik GeoTIFF zapisany przez tifffile w katalogu tymczasowym."""

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest
import tifffile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sentinel as S  # noqa: E402


@pytest.fixture
def tiled_tif(tmp_path):
    a = (np.arange(64 * 64, dtype=np.uint16).reshape(64, 64))
    p = tmp_path / "b.tif"
    tifffile.imwrite(p, a, tile=(16, 16), compression="zlib", predictor=2)
    return p, a


def test_read_window_assembles_tiles(tiled_tif):
    p, a = tiled_tif
    w, st = S.read_window(p, (10, 40), (5, 37))      # okno przecina 3 × 3 kafle
    assert np.array_equal(w, a[10:40, 5:37])
    w2, _ = S.read_window(p, (60, 70), (60, 70))      # okno wychodzi poza obraz – reszta = 0 (nodata)
    assert np.array_equal(w2[:4, :4], a[60:64, 60:64]) and (w2[4:, :] == 0).all()


def test_pixel_window_and_upsample():
    t = [10, 0, 499980, 0, -10, 5900040]
    r0, r1, c0, c1 = S.pixel_window(t, (500005, 5899900, 500095, 5900000))
    assert (r0, r1, c0, c1) == (4, 14, 2, 12)
    u = S.upsample2(np.array([[1, 2], [3, 4]]), 0, 0, (4, 4))
    assert u.tolist() == [[1, 1, 2, 2], [1, 1, 2, 2], [3, 3, 4, 4], [3, 3, 4, 4]]


def test_utm_roundtrip_and_central_meridian():
    x, y = S.lonlat_to_utm(21.0, 52.0, 32634)          # południk środkowy strefy 34 = 21°E
    assert float(x) == pytest.approx(500000.0, abs=1e-6)
    assert float(y) == pytest.approx(5_761_038, abs=2)  # łuk południka do 52°N (~5 763 344 m) × 0,9996
    lon, lat = S.utm_to_lonlat(*S.lonlat_to_utm(22.6018, 53.0500, 32634), 32634)
    assert float(lon) == pytest.approx(22.6018, abs=1e-8) and float(lat) == pytest.approx(53.05, abs=1e-8)


def test_indices_and_scl_mask():
    red = np.array([[0.05, 0.05], [0.10, 0.20]])
    nir = np.array([[0.45, 0.45], [0.30, 0.20]])
    swir = np.array([[0.20, 0.25], [0.30, 0.25]])
    scl = np.array([[4, 9], [5, 3]])                   # roślinność, chmura, gleba, cień chmury
    ndvi, ndmi, valid, sh = S.indices(red, nir, swir, scl)
    assert ndvi[0, 0] == pytest.approx(0.8)
    assert ndmi[0, 0] == pytest.approx(0.25 / 0.65)
    assert valid.tolist() == [[True, False], [True, False]]
    assert sh["cloud_pct"] == pytest.approx(50.0) and sh["valid_pct"] == pytest.approx(50.0)


def test_reflectance_offset_and_nodata():
    r = S.reflectance(np.array([0, 1000, 3000], dtype=np.uint16), 0.0001, -0.1)
    assert np.isnan(r[0]) and r[1] == pytest.approx(0.0) and r[2] == pytest.approx(0.2)


def test_points_in_ring_and_square():
    ring = np.array([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], float)
    m = S.points_in_ring(np.array([5, 15]), np.array([5, 5]), ring)
    assert m.tolist() == [True, False]
    sq = S.square_around(21.0, 52.0, 150)
    assert len(sq) == 5 and sq[0] == sq[-1]


@pytest.mark.parametrize("now, prev, month, frag", [
    ({"ndvi": 0.55, "ndmi": 0.1}, {"ndvi": 0.70, "ndmi": 0.25}, 6, "Słabsza zieleń"),
    ({"ndvi": 0.70, "ndmi": 0.2}, {"ndvi": 0.68, "ndmi": 0.2}, 6, "podobna"),
    ({"ndvi": 0.80, "ndmi": 0.3}, {"ndvi": 0.60, "ndmi": 0.2}, 6, "lepsza"),
    ({"ndvi": 0.25, "ndmi": 0.0}, {"ndvi": 0.27, "ndmi": 0.0}, 11, "Poza sezonem"),
    ({"ndvi": None, "ndmi": None}, None, 6, "Brak bezchmurnego"),
    ({"ndvi": 0.5, "ndmi": 0.1}, None, 6, "brak zdjęcia"),
])
def test_compare_sentence(now, prev, month, frag):
    assert frag in S.compare_sentence(now, prev, month)


def test_last_year_match():
    pts = [{"date": "2025-06-01", "ndvi": 0.6}, {"date": "2025-06-25", "ndvi": 0.7}, {"date": "2025-05-01", "ndvi": None}]
    m = S.last_year_match(pts, date(2026, 6, 20))
    assert m["date"] == "2025-06-25"
    assert S.last_year_match(pts, date(2026, 9, 1)) is None


def test_no_redirects():
    """Opener nie podąża za przekierowaniem (GUGiK przy limicie: 302 → plik ~126 MB)."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    hits = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/big")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        rf = S.RangeFile(f"http://127.0.0.1:{srv.server_port}/x.tif")
        with pytest.raises(RuntimeError, match="302"):
            rf.read_exact(0, 10)
        assert hits == ["/x.tif"]
    finally:
        srv.shutdown()
