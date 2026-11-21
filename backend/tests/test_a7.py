"""A7 – opad ze stacji IMGW jako źródło główne (port testów osoby C z research/precip/test_precip.py + nowe).
Bez sieci: próbki formatów IMGW, syntetyczny magazyn w katalogu tymczasowym, mocki NASA."""

import io
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis import precip as P
from app.analysis import verdict as V
from app.core.config import settings
from app.main import app
from app.schemas.analysis import AnalysisResponse
from app.sources import imgw
from test_a5 import mock_all
from test_water_model import _et0_seasonal, synth

FIX = Path(__file__).parent / "fixtures" / "imgw"
PID = "201305_2.0038.6/1"
LON, LAT = 22.6009, 53.0500  # środek działki 201305


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── 1. parsowanie archiwum IMGW (próbki osoby C) ────────────────────────────────────────────


def test_parse_imgw_opad_statuses():
    rows = imgw.parse_daily_csv((FIX / "o_d_sample.csv").read_text(encoding="cp1250"), "opad")
    by_day = {r[2]: r for r in rows if r[0] == "252210290"}
    assert by_day[date(2018, 6, 1)][3] == pytest.approx(3.7)      # pomiar
    assert by_day[date(2018, 6, 2)][3] is None                     # status 8 – brak pomiaru
    assert by_day[date(2018, 6, 3)][3] == 0.0                      # status 9 – brak zjawiska
    assert by_day[date(2018, 6, 5)][4] == "Z"                      # opad zbiorczy – wartość zostaje
    assert by_day[date(2018, 6, 5)][3] == pytest.approx(12.4)
    assert by_day[date(2018, 6, 1)][1] == "RYBIENKO"               # cp1250 → nazwa


def test_parse_imgw_klimat_column():
    rows = imgw.parse_daily_csv((FIX / "k_d_sample.csv").read_text(encoding="cp1250"), "klimat")
    assert rows[0][3] == pytest.approx(5.2) and rows[1][3] == 0.0


def test_zip_reader_takes_daily_file_and_skips_term_file():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("s_d_250_2018.csv",
                   '"353180250","TORUŃ","2018","01","01",10.0,"",4.9,"",8.2,"",4.3,"",1.5,"",""\n'.encode("cp1250"))
        # plik terminowy: w 14. kolumnie wilgotność (77,1) – nie może trafić do opadu
        z.writestr("s_d_t_250_2018.csv",
                   '"353180250","TORUŃ","2018","01","01",6.0,"",3.1,"",8.2,"",8.4,"",77.1,"",992.9,""\n'.encode("cp1250"))
    rows = list(imgw.zip_rows(buf.getvalue(), "synop"))
    assert len(rows) == 1 and rows[0][3] == pytest.approx(1.5) and rows[0][1] == "TORUŃ"


def test_archive_urls():
    assert imgw.archive_url("opad", 2018, 6).endswith("/dobowe/opad/2018/2018_06_o.zip")
    assert imgw.archive_url("klimat", 2018, 6).endswith("/dobowe/klimat/2018/2018_06_k.zip")
    assert imgw.archive_url("synop", 2018, synop_id="250").endswith("/dobowe/synop/2018/2018_250_s.zip")
    assert "gugik" not in imgw.ARCHIVE_URL and "imgw.pl" in imgw.ARCHIVE_URL


def test_store_builder_missing_vs_absent_days_and_kind_priority():
    cat = {"111": {"lon": 20.0, "lat": 52.0}, "222": {"lon": 20.1, "lat": 52.0}}
    b = imgw.StoreBuilder(date(2018, 6, 1), date(2018, 7, 31), cat)
    b.add("opad", [("111", "A", date(2018, 6, 1), 3.0, ""), ("111", "A", date(2018, 6, 2), None, "8"),
                   ("111", "A", date(2018, 6, 10), 7.5, ""), ("999", "bez współrzędnych", date(2018, 6, 1), 1.0, "")])
    b.add("opad", [("222", "B", date(2018, 6, 1), 9.0, "")])
    b.add("klimat", [("222", "B", date(2018, 6, 1), 4.0, "")])  # lepszy rodzaj stacji wygrywa
    codes, data, index = b.finish()
    assert codes == ["111", "222"] and index["222"]["kind"] == "klimat"
    a = data[:, 0]
    assert a[0] == 30 and a[1] == imgw.MISSING   # pomiar (0,1 mm) i brak pomiaru
    assert a[2] == 0                               # dnia nie ma w pliku, ale miesiąc jest → brak zjawiska
    assert a[9] == 75 and data.shape[0] == 30      # lipiec bez danych – macierz kończy się na ostatnim dniu z pomiarem
    assert data[0, 1] == 40


def test_haversine_and_idw():
    assert imgw.haversine_km(21.0122, 52.2297, 19.9450, 50.0647) == pytest.approx(252, abs=3)
    v = imgw.idw([np.array([10.0, np.nan, 0.0]), np.array([0.0, 4.0, np.nan])], [1.0, 2.0])
    assert v[0] == pytest.approx(10 * 1 / (1 + 0.25))   # wagi 1/d² = 1 i 0,25
    assert v[1] == pytest.approx(4.0)                    # tylko stacja z pomiarem
    assert v[2] == pytest.approx(0.0)
    assert np.isnan(imgw.idw([np.array([np.nan])], [3.0])[0])
    assert imgw.weights([1.0, 2.0]) == [0.8, 0.2]
    assert imgw.nice_name("KOŁUDA WIELKA") == "Kołuda Wielka" and imgw.nice_name("LUBLIN-RADAWIEC") == "Lublin-Radawiec"


# ── 2. syntetyczny magazyn ──────────────────────────────────────────────────────────────────

START = date(2008, 1, 1)


def make_store(tmp_path, stations, days=3987, value=None):
    """stations: [(kod, nazwa, rodzaj, lon, lat, opad_mm_dziennie | tablica | None)]."""
    data = np.full((days, len(stations)), imgw.MISSING, dtype=np.int16)
    for j, s in enumerate(stations):
        v = s[5]
        if v is not None:
            data[:, j] = np.round(np.broadcast_to(np.asarray(v, dtype=float), (days,)) * 10)
    path = tmp_path / "opady.npz"
    imgw.save_store(path, [s[0] for s in stations], [s[1] for s in stations], [s[2] for s in stations],
                    [s[3] for s in stations], [s[4] for s in stations], START, data, "2018-12-01")
    settings.imgw_store, settings.imgw_enabled = str(path), True
    imgw.clear_cache()
    return path


def weather(end=date(2018, 11, 20), mm=2.0):
    return synth(date(2008, 1, 1), end, lambda y, m, d: np.full(len(d), mm), _et0_seasonal)


def deg_east(km: float) -> float:
    return km / (111.32 * np.cos(np.radians(LAT)))


def test_nearest_filters_distance_and_coverage(tmp_path):
    half = np.where(np.arange(3987) % 2 == 0, 1.0, -0.1)  # co drugi dzień brak (−1 po zaokrągleniu)
    make_store(tmp_path, [("1", "BLISKA", "opad", LON + deg_east(5), LAT, 1.0),
                          ("2", "DZIURAWA", "opad", LON + deg_east(8), LAT, half),
                          ("3", "DALEKA", "synop", LON + deg_east(40), LAT, 1.0),
                          ("4", "DRUGA", "klimat", LON + deg_east(20), LAT, 1.0)])
    st = imgw.store()
    w = weather()
    near = imgw.nearest(st, LON, LAT, w.dates, 3, 30.0)
    assert [p.code for p in near] == ["1", "4"]      # 2 – za mało dni z pomiarem, 3 – za daleko
    assert near[0].dist_km == pytest.approx(5.0, abs=0.2) and near[0].name == "Bliska"
    assert [p.code for p in imgw.nearest(st, LON, LAT, w.dates, 3, 50.0)] == ["1", "4", "3"]
    assert imgw.nearest(st, LON, LAT, w.dates[:0], 3, 30.0) == []


def test_apply_replaces_precip_and_keeps_et0(tmp_path):
    make_store(tmp_path, [("1", "BURZYN", "opad", LON + deg_east(27), LAT, 1.6)])
    w = weather(mm=2.0)                        # „NASA” pokazuje 2,0 mm/dzień, stacja 1,6
    w2, info = P.apply(w, LON, LAT, date(2018, 11, 21))
    assert info.main == "imgw" and [p.name for p, _ in info.stations] == ["Burzyn"] and info.stations[0][1] == 1.0
    assert np.nanmean(w2.precip) == pytest.approx(1.6, abs=0.01) and w.precip[0] == 2.0   # oryginał nietknięty
    assert np.array_equal(w2.et0, w.et0) and w2.source.startswith("IMGW-PIB (opad)")
    assert info.factor == pytest.approx(0.8, abs=0.005) and info.nasa_vs_imgw_pct == pytest.approx(25.0, abs=0.2)
    assert info.filled_days == 0 and info.agreement == "roznia_sie" and not info.confidence_lowered
    assert info.sentence == ("Opady liczymy ze stacji IMGW Burzyn (27 km). Dane satelitarno-modelowe NASA pokazują "
                             "o 25% więcej – przyjmujemy pomiar ze stacji.")
    assert {x.key for x in info.windows} == {"sezon", "ostatnie_30_dni", "wielolecie"}


def test_apply_fills_recent_days_with_corrected_nasa(tmp_path):
    make_store(tmp_path, [("1", "BURZYN", "opad", LON + deg_east(10), LAT, 1.6)], days=3987 - 50)  # magazyn kończy się wcześniej
    w = weather(mm=2.0)
    w2, info = P.apply(w, LON, LAT, date(2018, 11, 21))
    n = len(w.dates)
    assert info.filled_days == n - (3987 - 50) > 0
    assert info.filled_from == START + timedelta(days=3987 - 50)
    assert w2.precip[-1] == pytest.approx(2.0 * 0.8, abs=0.01)      # NASA × współczynnik stacji (IMGW / NASA)
    assert w2.precip[0] == pytest.approx(1.6)
    assert "to dane NASA przeliczone do poziomu stacji" in info.sentence and f"Ostatnie {info.filled_days} dni" in info.sentence
    season = next(x for x in info.windows if x.key == "sezon")
    assert season.end == info.filled_from - timedelta(days=1) and season.rating == "roznia_sie"  # okno kończy się na pomiarze


def test_apply_fallback_50km_lowers_confidence(tmp_path):
    make_store(tmp_path, [("3", "DALEKA", "synop", LON + deg_east(40), LAT, 2.0)])
    _w2, info = P.apply(weather(), LON, LAT, date(2018, 11, 21))
    assert info.main == "imgw_daleko" and info.confidence_lowered
    assert info.sentence.startswith("Najbliższe stacje IMGW są daleko (Daleka (40 km))")
    assert "zgodne z pomiarem" in info.sentence


def test_apply_no_station_uses_nasa(tmp_path):
    make_store(tmp_path, [("9", "BARDZO DALEKA", "opad", LON + deg_east(80), LAT, 2.0)])
    w = weather()
    w2, info = P.apply(w, LON, LAT, date(2018, 11, 21))
    assert w2 is w and info.main == "nasa" and info.stations == [] and info.agreement == "brak_danych"
    assert info.sentence.startswith("W promieniu 50 km nie ma stacji IMGW z danymi")
    settings.imgw_enabled = False
    _w3, off = P.apply(w, LON, LAT, date(2018, 11, 21))
    assert off.main == "nasa" and "niedostępne" in off.sentence


@pytest.mark.parametrize("station_mm,rating,lowered", [(1.95, "zgodne", False), (1.6, "roznia_sie", False),
                                                       (1.0, "mocno_sie_roznia", True)])
def test_agreement_thresholds_on_window_sums(tmp_path, station_mm, rating, lowered):
    make_store(tmp_path, [("1", "A", "opad", LON + deg_east(5), LAT, station_mm)])
    _w, info = P.apply(weather(mm=2.0), LON, LAT, date(2018, 11, 21))
    assert info.agreement == rating and info.confidence_lowered is lowered
    assert all(x.rating == rating for x in info.windows)
    if rating == "mocno_sie_roznia":
        assert "możliwe lokalne burze" in info.sentence


def test_agreement_small_sums_not_alarming_and_missing_data():
    assert P.rate(1.0, 3.0) == "zgodne"            # 1 mm vs 3 mm – rozrzut liczony względem 20 mm
    assert P.rate(100.0, 140.0) == "roznia_sie" and P.rate(100.0, 200.0) == "mocno_sie_roznia"
    dates = np.arange(np.datetime64("2018-06-01"), np.datetime64("2018-07-01"))
    w = P.window("ostatnie_30_dni", dates, np.full(30, np.nan), np.full(30, 1.0), date(2018, 6, 1), date(2018, 6, 30))
    assert w.rating == "brak_danych" and w.imgw_mm is None


def test_idw_two_stations_weights_in_result(tmp_path):
    make_store(tmp_path, [("1", "A", "opad", LON + deg_east(10), LAT, 1.0), ("2", "B", "klimat", LON + deg_east(20), LAT, 3.0)])
    w2, info = P.apply(weather(), LON, LAT, date(2018, 11, 21))
    wa, wb = info.stations[0][1], info.stations[1][1]
    assert wa == pytest.approx(0.8, abs=0.01) and wb == pytest.approx(0.2, abs=0.01)
    assert w2.precip[100] == pytest.approx(1.0 * wa + 3.0 * wb, abs=0.02)
    assert info.sentence.startswith("Opady liczymy ze stacji IMGW: A (10 km) i B (20 km).")


# ── 3. werdykt i API ────────────────────────────────────────────────────────────────────────


def test_verdict_compares_with_norm_only_for_station_data():
    st = {"years": 10, "year_mm": 543, "season_mm": 300, "deficit_years": 6, "deficit_list": [], "first": 2016, "last": 2025}
    measured = V.precip_statement(st, measured=True)
    assert "To mniej niż średnio w Polsce (ok. 600 mm na rok) – pomiar ze stacji IMGW." in measured.text
    assert measured.numbers["zrodlo_opadu"] == "IMGW"
    assert "Dla porównania" in V.precip_statement(st, measured=False).text
    same = V.precip_statement({**st, "year_mm": 613, "deficit_years": 1}, measured=True)
    assert "To tyle, co średnio w Polsce" in same.text


@respx.mock
def test_api_precip_sources_from_imgw_store(client, tmp_path):
    make_store(tmp_path, [("253220160", "BURZYN", "opad", LON + deg_east(27), LAT, 1.5)])
    mock_all()
    r = client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-06-10"})
    assert r.status_code == 200, r.text
    a = AnalysisResponse.model_validate(r.json())
    ps = a.precip_sources
    assert ps.main == "imgw" and ps.main_label.startswith("stacje IMGW")
    s = ps.stations[0]
    assert (s.name, s.kind, s.kind_label, s.weight) == ("Burzyn", "opad", "posterunek opadowy", 1.0)
    assert s.distance_km == pytest.approx(27.0, abs=0.3)
    assert ps.sentence.startswith("Opady liczymy ze stacji IMGW Burzyn (27 km).")
    assert ps.source_tag.kind == "pomiar" and ps.agreement_label
    names = [x.name for x in a.reliability.sources]
    assert "IMGW-PIB (stacje)" in names and any(n.startswith("IMGW-PIB (opad)") for n in names)
    assert any(lim.startswith("Opad ze stacji IMGW: Burzyn (27 km)") for lim in a.reliability.limitations)
    assert not any("Pogoda uśredniona" in lim for lim in a.reliability.limitations)


@respx.mock
def test_api_precip_sources_nasa_when_store_disabled(client):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-06-10"}).json())
    assert a.precip_sources.main == "nasa" and a.precip_sources.stations == []
    assert a.precip_sources.source_tag.kind == "szacunek_modelu"
    assert any("Pogoda uśredniona" in lim for lim in a.reliability.limitations)  # jak przed A7


# ── 4. magazyn w repo ───────────────────────────────────────────────────────────────────────


def test_committed_store_is_small_and_knows_burzyn():
    assert imgw.STORE_FILE.exists() and imgw.STORE_FILE.stat().st_size < 15_000_000  # < 15 MB → w repo (D82)
    st = imgw.read_store(imgw.STORE_FILE)
    assert len(st.codes) > 300 and str(st.start) == "2016-01-01" and st.days > 3600
    dates = np.arange(np.datetime64("2016-01-01"), np.datetime64("2026-01-01"))
    near = imgw.nearest(st, LON, LAT, dates, 3, 30.0)
    assert near and near[0].name == "Burzyn" and near[0].dist_km == pytest.approx(27, abs=1)
    year = st.series(near[0].idx, dates)
    assert 500 < np.nansum(year) / 10 < 700   # średnio ok. 613 mm na rok (raport osoby C)
    assert set(str(k) for k in np.unique(st.kinds)) <= {"synop", "klimat", "opad"}
