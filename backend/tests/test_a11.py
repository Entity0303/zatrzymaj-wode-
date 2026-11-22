"""A11 – satelita Sentinel-2 (port testów osoby C z research/satellite/test_sentinel.py + nowe). Bez sieci:
kafelkowany GeoTIFF zapisany przez tifffile, sztuczne sceny i pasma, mock compute_live dla endpointów."""

import asyncio
import base64
import functools
import struct
import zlib
from datetime import date, timedelta

import numpy as np
import pytest
import respx
import tifffile
from fastapi.testclient import TestClient
from pyproj import Transformer
from shapely.geometry import box

from app.analysis import satellite as SM
from app.analysis import verdict as V
from app.core.config import settings
from app.main import app
from app.schemas.analysis import AnalysisResponse, Satellite
from app.sources import sentinel as S
from test_a5 import mock_all

PID = "201305_2.0038.6/1"
D = "2018-06-10"  # analiza historyczna – bez prognozy (mock_all)


def sync(fn):
    """Testy asynchroniczne bez pytest-asyncio."""
    @functools.wraps(fn)
    def w(*a, **k):
        return asyncio.run(fn(*a, **k))
    return w


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean():
    S.clear_cache()
    SM.clear_cache()
    yield
    S.clear_cache()
    SM.clear_cache()


# ── 1. odczyt okna z kafelkowanego COG (HTTP Range podmieniony na plik lokalny) ─────────────


@pytest.fixture
def tiled_tif(tmp_path, monkeypatch):
    a = np.arange(64 * 64, dtype=np.uint16).reshape(64, 64)
    p = tmp_path / "b.tif"
    tifffile.imwrite(p, a, tile=(16, 16), compression="zlib", predictor=2)
    raw = p.read_bytes()
    calls = []

    async def fake_range(url, lo, hi, stats):
        calls.append((lo, hi))
        chunk = raw[lo: hi + 1]
        stats.bytes += len(chunk)
        stats.requests += 1
        return chunk, len(raw)

    monkeypatch.setattr(S, "_range", fake_range)
    return a, calls


@sync
async def test_read_window_assembles_tiles(tiled_tif):
    a, calls = tiled_tif
    st = S.Stats()
    w = await S.read_window("mem://b.tif", (10, 40), (5, 37), st)  # okno przecina 3 × 3 kafle
    assert np.array_equal(w, a[10:40, 5:37])
    assert len(calls) == 1 + 9 and st.requests == 10            # nagłówek + tylko potrzebne kafle
    w2 = await S.read_window("mem://b.tif", (60, 70), (60, 70), st)  # poza obrazem – 0 (brak danych)
    assert np.array_equal(w2[:4, :4], a[60:64, 60:64]) and (w2[4:, :] == 0).all()
    assert len(calls) == 11                                       # nagłówek z pamięci, jeden kafel


def test_pixel_window_and_upsample():
    t = [10, 0, 499980, 0, -10, 5900040]
    assert S.pixel_window(t, (500005, 5899900, 500095, 5900000)) == (4, 14, 2, 12)
    u = S.upsample2(np.array([[1, 2], [3, 4]]), (4, 3))
    assert u.tolist() == [[1, 1, 2], [1, 1, 2], [3, 3, 4], [3, 3, 4]]


def test_indices_scl_shares_and_reflectance():
    red = np.array([[0.05, 0.05], [0.10, -0.01]])
    nir = np.array([[0.45, 0.45], [0.30, 0.20]])
    swir = np.array([[0.20, 0.25], [0.30, 0.25]])
    ndvi, ndmi = S.indices(red, nir, swir)
    assert ndvi[0, 0] == pytest.approx(0.8) and ndmi[0, 0] == pytest.approx(0.25 / 0.65)
    assert np.isnan(ndvi[1, 1])  # odbicie ≤ 0 (offset −0,1, niskie słońce) = brak, nie NDVI 1,0
    _, ndmi_no = S.indices(red, nir, None)
    assert np.isnan(ndmi_no).all()
    scl = np.array([[4, 9], [5, 3]])  # roślinność, chmura, gleba, cień chmury
    sh = S.scl_shares(scl, np.ones((2, 2), bool))
    assert sh["valid_pct"] == pytest.approx(50.0) and sh["cloud_pct"] == pytest.approx(50.0)
    r = S.reflectance(np.array([0, 1000, 3000], dtype=np.uint16), 0.0001, -0.1)
    assert np.isnan(r[0]) and r[1] == pytest.approx(0.0) and r[2] == pytest.approx(0.2)
    assert S.median_in(ndvi, np.isfinite(ndvi)) == pytest.approx(0.8)


def test_stac_feature_and_unique_by_date():
    def feat(i, d, cloud):
        a = {"href": f"https://x/{i}.tif", "proj:transform": [10, 0, 0, 0, -10, 0], "proj:shape": [10980, 10980],
             "raster:bands": [{"scale": 0.0001, "offset": -0.1}]}
        return {"id": i, "properties": {"datetime": f"{d}T10:00:00Z", "eo:cloud_cover": cloud, "proj:code": "EPSG:32634"},
                "assets": {k: a for k in S.ASSETS}}
    sc = [S.scene_from_feature(f) for f in (feat("A", "2026-11-16", 30), feat("B", "2026-11-16", 5),
                                            feat("C", "2026-11-09", 50))]
    assert sc[0].epsg == 32634 and sc[0].assets["red"].offset == -0.1
    u = S.unique_by_date(sc)
    assert [s.id for s in u] == ["B", "C"]  # jedna scena na datę (mniej chmur), od najnowszej


# ── 2. scena → NDVI / NDMI w obrysie (sztuczne pasma, prawdziwa siatka UTM) ─────────────────

LON0, LAT0 = 21.0, 52.0
TR = Transformer.from_crs(4326, 32634, always_xy=True)
X0, Y0 = TR.transform(LON0, LAT0)


def scene(sid="S2A_TEST", d=date(2026, 11, 16), cloud=5.0) -> S.Scene:
    t10 = [10.0, 0.0, float(int(X0) - 5000), 0.0, -10.0, float(int(Y0) + 5000)]
    t20 = [20.0, 0.0, t10[2], 0.0, -20.0, t10[5]]
    mk = lambda name, t: S.Asset(f"mem://{sid}/{name}", t, [10980, 10980], 0.0001, -0.1)  # noqa: E731
    return S.Scene(sid, d, cloud, 32634, {"red": mk("red", t10), "nir": mk("nir", t10), "swir16": mk("swir16", t20),
                                           "scl": mk("scl", t20)})


PARCEL = box(LON0, LAT0, LON0 + 0.003, LAT0 + 0.002)  # ok. 200 × 220 m


def fake_bands(monkeypatch, values: dict, scl_value=4, cloudy_half=False):
    """read_window zwraca stałe DN pasma (scale 0,0001, offset −0,1); `cloudy_half` – połowa okna SCL = chmura."""
    reads = []

    async def rw(url, rows, cols, stats):
        name = url.rsplit("/", 1)[-1]
        reads.append(name)
        stats.bytes += 100_000
        stats.requests += 1
        shape = (rows[1] - rows[0], cols[1] - cols[0])
        if name == "scl":
            out = np.full(shape, scl_value, np.uint8)
            if cloudy_half:
                out[:, : shape[1] // 2 + 1] = 9
            return out
        return np.full(shape, values[name], np.uint16)

    monkeypatch.setattr(S, "read_window", rw)
    return reads


@sync
async def test_scene_point_ndvi_ndmi_and_mask(monkeypatch):
    reads = fake_bands(monkeypatch, {"red": 1500, "nir": 5500, "swir16": 3000})  # odbicie 0,05 / 0,45 / 0,20
    st = S.Stats()
    p = await SM.scene_point(scene(), PARCEL, st, bands=False)
    assert p.valid_pct == 100.0 and p.ndvi is None and reads == ["scl"]  # najpierw tylko SCL
    p = await SM.scene_point(scene(), PARCEL, st, bands=True)
    assert p.ndvi == pytest.approx(0.8) and p.ndmi == pytest.approx(0.25 / 0.65, abs=1e-3)
    assert p.arrays["inside"].sum() > 300 and p.grid.bbox_4326[0] < LON0 < p.grid.bbox_4326[2]


@sync
async def test_scene_point_dark_pixels_skip_nir(monkeypatch):
    reads = fake_bands(monkeypatch, {"red": 900, "nir": 5500, "swir16": 3000})  # odbicie czerwone −0,01
    p = await SM.scene_point(scene(), PARCEL, S.Stats(), bands=True, min_red_pct=20)
    assert p.ndvi is None and p.valid_pct == 0.0 and "nir" not in reads  # zbyt ciemne – NIR / B11 nie pobierane


# ── 3. wybór sceny w budżecie ───────────────────────────────────────────────────────────────


def fake_points(monkeypatch, table: dict):
    """scene_point na sztucznych wynikach: {scene_id: (valid_pct, ndvi)}; liczy wywołania."""
    calls = []

    async def sp(sc, geom, stats, bands, swir=True, min_red_pct=None):
        calls.append((sc.id, bands))
        stats.bytes += 30_000 if not bands else 400_000
        valid, ndvi = table[sc.id]
        p = SM.Point(sc, valid, 100 - valid, 0.0)
        if bands:
            p.ndvi, p.ndmi = ndvi, -0.2
        return p

    monkeypatch.setattr(SM, "scene_point", sp)
    return calls


@sync
async def test_pick_stops_at_first_clear_scene(monkeypatch):
    calls = fake_points(monkeypatch, {"a": (10, 0.8), "b": (95, 0.7), "c": (100, 0.9)})
    scs = [scene("a", date(2026, 11, 18)), scene("b", date(2026, 11, 10)), scene("c", date(2026, 11, 1))]
    p, warn = await SM.pick(SM.order_candidates(scs), PARCEL, S.Stats(), 6, allow_fallback=True)
    assert p.scene.id == "b" and warn is None
    assert calls == [("a", False), ("b", False), ("b", True)]  # "c" w ogóle nie czytana, pasma tylko dla czystej


@sync
async def test_pick_fallback_partial_with_warning_and_none(monkeypatch):
    fake_points(monkeypatch, {"a": (35, 0.8), "b": (10, 0.7)})
    scs = [scene("a", date(2026, 11, 18)), scene("b", date(2026, 11, 10))]
    p, warn = await SM.pick(scs, PARCEL, S.Stats(), 6, allow_fallback=True)
    assert p.scene.id == "a" and "18.11.2026" in warn and "35%" in warn
    assert await SM.pick(scs, PARCEL, S.Stats(), 6, allow_fallback=False) == (None, None)
    fake_points(monkeypatch, {"a": (5, 0.8), "b": (10, 0.7)})
    assert await SM.pick(scs, PARCEL, S.Stats(), 6, allow_fallback=True) == (None, None)


@sync
async def test_pick_respects_byte_budget(monkeypatch):
    fake_points(monkeypatch, {f"s{i}": (10, 0.5) for i in range(6)})
    monkeypatch.setattr(settings, "sentinel_budget_mb", 0.05)  # 50 kB – po 2 maskach SCL koniec
    st = S.Stats()
    await SM.pick([scene(f"s{i}") for i in range(6)], PARCEL, st, 6, allow_fallback=False)
    assert st.mb <= 0.07


def test_order_candidates_newest_moderate_cloud_first():
    scs = [scene("old_clear", date(2026, 10, 1), 2), scene("new_cloudy", date(2026, 11, 18), 75),
           scene("new_ok", date(2026, 11, 12), 30), scene("mid", date(2026, 11, 1), 50)]
    assert [s.id for s in SM.order_candidates(scs)] == ["new_ok", "old_clear", "mid", "new_cloudy"]


@sync
async def test_compute_live_no_scene_gives_brak_danych(monkeypatch):
    async def search(*a, **k):
        return []
    monkeypatch.setattr(S, "search", search)
    res = await SM.compute_live(PARCEL, date(2026, 11, 20))
    sat = SM.to_contract(res)
    assert sat.status == "brak_danych" and "60 dni" in sat.sentence and sat.ndvi is None


@sync
async def test_compute_live_with_last_year(monkeypatch):
    now_sc, ly_sc = scene("now", date(2026, 11, 16)), scene("ly", date(2025, 11, 4))

    async def search(bbox, start, end, stats, **k):
        return [now_sc] if start.year == 2026 else [ly_sc, scene("ly_far", date(2025, 9, 1))]
    monkeypatch.setattr(S, "search", search)
    fake_points(monkeypatch, {"now": (100, 0.86), "ly": (90, 0.83), "ly_far": (100, 0.2)})
    sat = SM.to_contract(await SM.compute_live(PARCEL, date(2026, 11, 20)))
    assert sat.status == "ok" and sat.last_year.scene_id == "ly" and sat.trend == "podobnie"
    assert sat.sentence.startswith("Zdjęcie satelitarne z 16.11.2026: pole zielone")


# ── 4. zdania i poziom z wartości ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("ndvi, ndmi, ly, d, frag, level", [
    (0.9, -0.25, 0.88, date(2026, 11, 16), "pole zielone – prawdopodobnie wzeszło zboże ozime", "info"),
    (0.55, -0.2, 0.75, date(2026, 7, 10), "Rośliny słabsze niż rok temu i mają mało wody w liściach – możliwy stres "
                                          "wodny.", "bad"),
    (0.75, 0.3, 0.74, date(2026, 6, 10), "gęsta zieleń", "ok"),
    (0.6, 0.0, 0.75, date(2026, 6, 10), "Rośliny słabsze niż rok temu.", "warn"),
    (0.2, 0.0, None, date(2026, 6, 10), "Brak bezchmurnego zdjęcia z tej samej pory rok temu", "warn"),
    (0.3, -0.1, 0.8, date(2026, 12, 2), "to może być też inna uprawa", "warn"),
    (0.2, -0.1, 0.25, date(2026, 10, 20), "goła gleba albo ściernisko", "info"),
])
def test_describe_sentences(ndvi, ndmi, ly, d, frag, level):
    r = SM.describe(ndvi, ndmi, ly, d)
    assert frag in r["sentence"] and r["level"] == level
    assert r["sentence"].startswith(f"Zdjęcie satelitarne z {d:%d.%m.%Y}: ")


def test_describe_ndmi_only_in_season_with_dense_canopy():
    assert SM.describe(0.9, -0.3, 0.9, date(2026, 11, 16))["ndmi_class"] is None  # listopad – NDMI nie oceniamy
    assert SM.describe(0.4, -0.3, 0.4, date(2026, 6, 16))["ndmi_class"] is None   # rzadki łan
    assert SM.describe(0.8, -0.3, 0.8, date(2026, 6, 16))["ndmi_class"] == "sucho"
    assert SM.describe(None, None, None, None)["sentence"] is None


def test_plants_statement_only_with_data():
    assert V.plants_statement(SM.pending()) is None
    sat = Satellite(status="ok", date=date(2026, 11, 16), ndvi=0.86, ndmi=-0.24, level="info", sentence="Zdjęcie …",
                    source_tag={"kind": "pomiar", "source": S.SOURCE})
    st = V.plants_statement(sat)
    assert st.kind == "rosliny" and st.level == "info" and st.text == "Zdjęcie …"


# ── 5. PNG warstwy ──────────────────────────────────────────────────────────────────────────


def test_png_encoder_and_layer_png():
    rgba = np.zeros((2, 3, 4), np.uint8)
    rgba[0, 0] = (255, 0, 0, 255)
    png = SM.png_rgba(rgba)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", png[16:24])
    assert (w, h) == (3, 2)
    idat_len = struct.unpack(">I", png[33:37])[0]
    raw = zlib.decompress(png[41: 41 + idat_len])
    assert raw[:5] == b"\x00\xff\x00\x00\xff"  # filtr 0 + pierwszy piksel RGBA
    vals = np.array([[0.0, 0.9], [0.5, np.nan]])
    inside = np.array([[True, True], [True, False]])
    valid = np.array([[True, True], [False, False]])
    lp = SM.layer_png(vals, valid, inside, "kondycja", scale=2)
    raw = zlib.decompress(lp[41: 41 + struct.unpack(">I", lp[33:37])[0]])
    row0 = np.frombuffer(raw[1: 1 + 4 * 4], np.uint8).reshape(4, 4)
    assert tuple(row0[0]) == (0xC0, 0x47, 0x3C, 235) and tuple(row0[2][:3]) == (0x1F, 0x42, 0x30)
    row2 = np.frombuffer(raw[2 * (1 + 16) + 1: 2 * (1 + 16) + 17], np.uint8).reshape(4, 4)
    assert tuple(row2[0]) == (255, 255, 255, 200) and row2[3][3] == 0  # chmura biała, poza obrysem przezroczyste


# ── 6. endpointy: /api/satellite, analiza (pending / z cache), warstwy ──────────────────────


def fake_live(monkeypatch, counter: list):
    async def compute_live(geom, on):
        counter.append(on)
        sc = scene("S2A_FAKE", date(2026, 11, 16))
        gr = SM.grid_for(geom, sc)
        shape = gr.mask.shape
        nd = np.full(shape, 0.86)
        p = SM.Point(sc, 100.0, 0.0, 0.0, ndvi=0.86, ndmi=-0.24, grid=gr,
                     arrays={"ndvi": nd, "ndmi": np.full(shape, -0.24), "valid": gr.mask.copy(), "inside": gr.mask})
        ly = SM.Point(scene("S2A_LY", date(2025, 11, 4)), 95.0, 5.0, 0.0, ndvi=0.83)
        return SM.LiveResult(p, ly, None, S.Stats(bytes=8_400_000, requests=18), 12)

    monkeypatch.setattr(SM, "compute_live", compute_live)
    monkeypatch.setattr(settings, "sentinel_enabled", True)


@respx.mock
def test_api_satellite_live_then_cached_and_analysis_uses_cache(client, monkeypatch):
    mock_all()
    n = []
    fake_live(monkeypatch, n)
    r = client.get("/api/satellite", params={"parcel_id": PID, "date": D})
    assert r.status_code == 200, r.text
    s = Satellite.model_validate(r.json())
    assert s.status == "ok" and s.ndvi == 0.86 and s.date == date(2026, 11, 16) and not s.cached
    assert s.last_year.ndvi == 0.83 and s.downloaded_mb == 8.4 and s.layers == ["kondycja", "wilgotnosc"]
    s2 = Satellite.model_validate(client.get("/api/satellite", params={"parcel_id": PID, "date": D}).json())
    assert s2.cached and len(n) == 1  # drugi raz z cache
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": D}).json())
    assert a.satellite.status == "ok" and a.satellite.cached
    assert [st.kind for st in a.verdict.statements].count("rosliny") == 1
    assert a.indicators.crop_health.value == 86.0 and "16.11.2026" in a.indicators.crop_health.note
    src = [x for x in a.reliability.sources if x.name.startswith("Sentinel-2")][0]
    # A20: data danych nigdy po dacie analizy (sztuczna scena z 2026 r. w analizie z 2018 r. → „pobrano”)
    assert src.status == "ok" and src.data_date == date(2018, 6, 10) and src.fetched_at == date(2026, 11, 16)


@respx.mock
def test_api_analysis_satellite_pending_without_cache(client, monkeypatch):
    mock_all()
    n = []
    fake_live(monkeypatch, n)  # tło wyłączone w testach – analiza nie liczy satelity
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-06-10"}).json())
    assert a.satellite.status == "pending" and a.satellite.sentence == "Pobieram zdjęcie satelitarne…"
    assert n == [] and "rosliny" not in [st.kind for st in a.verdict.statements]
    assert a.indicators.crop_health.value is None


@respx.mock
def test_api_satellite_source_error_is_brak_danych(client, monkeypatch):
    mock_all()
    monkeypatch.setattr(settings, "sentinel_enabled", True)
    respx.post(settings.sentinel_stac_url).respond(503)
    r = client.get("/api/satellite", params={"parcel_id": PID})
    assert r.status_code == 200
    s = Satellite.model_validate(r.json())
    assert s.status == "brak_danych" and "HTTP 503" in s.warning


@respx.mock
def test_api_satellite_future_date_and_missing_args(client):
    assert client.get("/api/satellite").status_code == 422
    d = (date.today() + timedelta(days=3)).isoformat()
    mock_all()
    assert client.get("/api/satellite", params={"parcel_id": PID, "date": d}).status_code == 422


@respx.mock
def test_layers_kondycja_wilgotnosc(client, monkeypatch):
    mock_all()
    fake_live(monkeypatch, [])
    for layer, val in (("kondycja", 0.86), ("wilgotnosc", -0.24)):
        r = client.get(f"/api/layers/{layer}", params={"parcel_id": PID})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["raster"]["image_url"].startswith("data:image/png;base64,")
        png = base64.b64decode(d["raster"]["image_url"].split(",", 1)[1])
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) < 20_000
        lo0, la0, lo1, la1 = d["raster"]["bbox"]
        assert lo0 < 22.6009 < lo1 and la0 < 53.05 < la1  # bbox lon/lat wokół działki
        assert d["value"] == val and d["scene_date"] == "2026-11-16" and len(d["legend"]) >= 3
        assert d["source_tag"]["kind"] == "pomiar"


@respx.mock
def test_layers_satellite_404_without_scene(client, monkeypatch):
    mock_all()
    monkeypatch.setattr(settings, "sentinel_enabled", True)

    async def none(geom, on):
        return SM.LiveResult(None, None, None, S.Stats(), 0)
    monkeypatch.setattr(SM, "compute_live", none)
    assert client.get("/api/layers/kondycja", params={"parcel_id": PID}).status_code == 404


# ── 7. A8 (D90): najnowsza zapisana scena ≤ data analizy ───────────────────────────────────


def _sat_ok(d: date) -> Satellite:
    return Satellite(status="ok", date=d, ndvi=0.8, sentence=f"Zdjęcie z {d}", source_tag={"kind": "pomiar", "source": S.SOURCE})


def test_cached_result_picks_newest_scene_not_after_analysis_date():
    SM._store(PARCEL, date(2026, 11, 22), _sat_ok(date(2026, 11, 16)), None)
    SM._store(PARCEL, date(2026, 11, 5), _sat_ok(date(2026, 11, 2)), None)
    assert SM.cached_result(PARCEL, date(2026, 11, 22)).date == date(2026, 11, 16)  # dokładna data
    assert SM.cached_result(PARCEL, date(2026, 11, 20)).date == date(2026, 11, 16)  # scena 16.11 ≤ 20.11
    assert SM.cached_result(PARCEL, date(2026, 11, 10)).date == date(2026, 11, 2)   # 16.11 byłaby z przyszłości
    assert SM.cached_result(PARCEL, date(2026, 10, 30)) is None                      # obie sceny późniejsze
    assert SM.cached_result(PARCEL, date(2027, 3, 1)) is None                        # > 60 dni po scenie


def test_disabled_satellite_message_is_neutral(monkeypatch):
    monkeypatch.setattr(settings, "sentinel_enabled", False)
    sat = asyncio.run(SM.live(PARCEL, date(2026, 11, 22)))
    assert sat.status == "brak_danych" and "ustawieniach" not in (sat.warning or "")
