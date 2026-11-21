"""Testy offline (bez sieci) – na zapisanych próbkach formatów IMGW, ERA5-Land i NASA POWER.

    python -m pytest research/precip/test_precip.py -q
"""

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import precip as P  # noqa: E402

SAMPLES = HERE / "test_samples"


def test_parse_imgw_opad_statuses():
    text = (SAMPLES / "o_d_sample.csv").read_text(encoding="cp1250")
    rows = P.parse_daily_csv(text, "opad")
    by_day = {r[2]: r for r in rows if r[0] == "252210290"}
    assert by_day[date(2018, 6, 1)][3] == pytest.approx(3.7)      # pomiar
    assert by_day[date(2018, 6, 2)][3] is None                     # status 8 – brak pomiaru
    assert by_day[date(2018, 6, 3)][3] == 0.0                      # status 9 – brak zjawiska
    assert by_day[date(2018, 6, 5)][4] == "Z"                      # opad zbiorczy – wartość zostaje
    assert by_day[date(2018, 6, 5)][3] == pytest.approx(12.4)
    assert by_day[date(2018, 6, 1)][1] == "RYBIENKO"               # cp1250 → nazwa


def test_parse_imgw_klimat_column():
    text = (SAMPLES / "k_d_sample.csv").read_text(encoding="cp1250")
    rows = P.parse_daily_csv(text, "klimat")
    assert rows[0][3] == pytest.approx(5.2)
    assert rows[1][3] == 0.0


def _write_station(tmp_path, code, rows):
    (tmp_path / "imgw").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "imgw" / f"{code}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data", "opad_mm", "status"])
        w.writerows(rows)


def test_imgw_daily_missing_vs_absent_days(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "DATA", tmp_path)
    _write_station(tmp_path, "111", [("2018-06-01", 3.0, ""), ("2018-06-02", "", "8"), ("2018-06-10", 7.5, "")])
    s = P.Station("111", "A", "opad", 20.0, 52.0, 5.0)
    out = P.imgw_daily([s], date(2018, 6, 1), date(2018, 7, 2))["111"]
    assert out[0] == 3.0
    assert np.isnan(out[1])           # brak pomiaru
    assert out[2] == 0.0              # dnia nie ma w pliku, ale miesiąc jest → brak zjawiska
    assert out[9] == 7.5
    assert np.isnan(out[30])          # lipiec – stacja nie ma danych w tym miesiącu


def test_idw_weights_and_missing_station():
    s1 = P.Station("a", "A", "opad", 0, 0, 1.0)
    s2 = P.Station("b", "B", "opad", 0, 0, 2.0)
    series = {"a": np.array([10.0, np.nan, 0.0]), "b": np.array([0.0, 4.0, np.nan])}
    v = P.idw(series, [s1, s2])
    assert v[0] == pytest.approx(10 * 1 / (1 + 0.25))   # wagi 1/d² = 1 i 0,25
    assert v[1] == pytest.approx(4.0)                    # tylko stacja z danymi
    assert v[2] == pytest.approx(0.0)


def test_haversine_warsaw_krakow():
    assert P.haversine_km(21.0122, 52.2297, 19.9450, 50.0647) == pytest.approx(252, abs=3)


def test_nearest_stations_filters_distance_and_coverage():
    catalog = {"1": {"lon": 20.0, "lat": 52.0}, "2": {"lon": 20.1, "lat": 52.0},
               "3": {"lon": 21.0, "lat": 52.0}, "4": {"lon": 20.05, "lat": 52.0}}
    index = {"1": {"kind": "opad", "name": "A", "months": 120}, "2": {"kind": "klimat", "name": "B", "months": 120},
             "3": {"kind": "opad", "name": "C", "months": 120}, "4": {"kind": "opad", "name": "D", "months": 10},
             "5": {"kind": "opad", "name": "bez współrzędnych", "months": 120}}
    st = P.nearest_stations(20.0, 52.0, n=3, max_km=30, start=date(2016, 1, 1), end=date(2025, 12, 31),
                            catalog=catalog, index=index)
    assert [s.code for s in st] == ["1", "2"]   # 3 – za daleko (~68 km), 4 – za mało miesięcy, 5 – bez współrzędnych
    assert st[1].dist_km == pytest.approx(6.85, abs=0.1)


def test_parse_era5_and_nasa_samples():
    e = json.loads((SAMPLES / "era5_sample.json").read_text(encoding="utf-8"))
    n = json.loads((SAMPLES / "nasa_sample.json").read_text(encoding="utf-8"))
    a, b = date(2018, 6, 1), date(2018, 6, 3)
    assert P.parse_era5(e, a, b).tolist()[:2] == [1.5, 0.0]
    assert np.isnan(P.parse_era5(e, a, b)[2])
    nv = P.parse_nasa(n, a, b)
    assert nv[0] == pytest.approx(2.1) and np.isnan(nv[1]) and nv[2] == pytest.approx(0.4)


def _days(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


@pytest.mark.parametrize("factor, label", [(1.05, "zgodne"), (1.3, "różnią się"), (2.0, "mocno się różnią")])
def test_agreement_labels(factor, label):
    days = _days(date(2018, 4, 1), date(2018, 6, 30))
    base = np.full(len(days), 2.0)
    series = {"imgw_idw": base, "era5_land": base * factor, "nasa_power": base}
    agr = P.agreement(days, series, date(2018, 6, 30))
    assert agr["sezon"]["ocena"] == label
    assert agr["ostatnie_30_dni"]["ocena"] == label
    assert isinstance(P.sentence(agr), str) and "mm" in P.sentence(agr)


def test_agreement_small_sums_not_alarming():
    days = _days(date(2018, 6, 1), date(2018, 6, 30))
    series = {"imgw_idw": np.full(30, 0.03), "nasa_power": np.full(30, 0.1)}   # 1 mm vs 3 mm
    assert P.agreement(days, series, date(2018, 6, 30))["ostatnie_30_dni"]["ocena"] == "zgodne"


def test_agreement_missing_data():
    days = _days(date(2018, 6, 1), date(2018, 6, 30))
    series = {"imgw_idw": np.full(30, np.nan), "nasa_power": np.full(30, 1.0)}
    assert P.agreement(days, series, date(2018, 6, 30))["ostatnie_30_dni"]["ocena"] == "brak danych"


def test_archive_reader_skips_term_files(tmp_path):
    import zipfile
    zp = tmp_path / "2018_250_s.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("s_d_250_2018.csv",
                   '"353180250","TORUŃ","2018","01","01",10.0,"",4.9,"",8.2,"",4.3,"",1.5,"",""\n'.encode("cp1250"))
        # plik terminowy: w 14. kolumnie wilgotność (77,1) – nie może trafić do opadu
        z.writestr("s_d_t_250_2018.csv",
                   '"353180250","TORUŃ","2018","01","01",6.0,"",3.1,"",8.2,"",8.4,"",77.1,"",992.9,""\n'.encode("cp1250"))
    rows = list(P.iter_archive_rows("synop", [zp]))
    assert len(rows) == 1 and rows[0][3] == pytest.approx(1.5)


def test_http_get_never_follows_redirects():
    """GUGiK przy limicie: 302 + ogromny plik. Nie podążamy za przekierowaniem i nie czytamy treści."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    hits = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if self.path.startswith("/start"):
                self.send_response(302)
                self.send_header("Location", "/big")
                self.send_header("Content-Length", str(10_000_000))
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x" * 1000)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        with pytest.raises(RuntimeError, match="302"):
            P.http_get(f"http://127.0.0.1:{srv.server_port}/start", timeout=5, retries=1)
        assert hits == ["/start"]  # /big nigdy nie został pobrany
    finally:
        srv.shutdown()


def test_era5_cache_only_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "DATA", tmp_path)
    monkeypatch.setattr(P, "ERA5_NETWORK", False)
    with pytest.raises(RuntimeError, match="pobieranie wyłączone"):
        P.era5_land(20.0, 52.0, date(2018, 1, 1), date(2018, 1, 2), "x")
