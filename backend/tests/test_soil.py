"""A2: gleba IUNG (WCS + zapasowo GetFeatureInfo) i klasy EGiB (KIEG) – bez sieci.

Fikstury w tests/fixtures/ to PRAWDZIWE odpowiedzi usług zapisane 2026-11-21 dla działki
201305_2.0038.6/1 (IUNG WCS, IUNG GetFeatureInfo, KIEG) i 040703_5.0020.76 (KIEG bez klas).
"""

import asyncio
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient
from shapely.geometry import box

from app.analysis.soil import assess_soil
from app.core.config import settings
from app.core.geo import parse_wkt
from app.core.http import SourceError, close_client
from app.main import app
from app.sources import iung, kieg, uldk
from app.sources.iung import SoilResult, count_cells, parse_wcs_text

FIX = Path(__file__).parent / "fixtures"
WCS_201305 = (FIX / "iung_wcs_201305.txt").read_text(encoding="utf-8")
GFI_3 = (FIX / "iung_gfi_code3.json").read_text(encoding="utf-8")
KIEG_CLASSES = (FIX / "kieg_201305_klasy.html").read_text(encoding="utf-8")
KIEG_NONE = (FIX / "kieg_040703_bez_klas.html").read_text(encoding="utf-8")

# prawdziwa geometria 201305_2.0038.6/1 z ULDK (EPSG:2180, wschód północ)
WKT_201305 = (
    "POLYGON((741326.598870282 582135.860610104,741196.719087438 582172.956309767,"
    "741196.080461016 582126.579753392,741319.716303976 582092.766677043,"
    "741323.823760127 582113.17232317,741326.598870282 582135.860610104))"
)
GEOM_201305 = parse_wkt(WKT_201305)
ULDK_ONE = f"0\nSRID=2180;{WKT_201305}|201305_2.0038.6/1|podlaskie|powiat wysokomazowiecki|Kobylin-Borzymy|Wnory-Wandy|6/1\n"


@pytest.fixture(autouse=True)
def _clean():
    for m in (iung, kieg, uldk):
        m.clear_cache()
    yield
    for m in (iung, kieg, uldk):
        m.clear_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _run(coro):
    async def go():
        try:
            return await coro
        finally:
            await close_client()

    return asyncio.run(go())


def wcs_text(grid: list[list[int]], bounds: tuple[float, float, float, float]) -> str:
    """Odpowiedź w formacie WCS text/plain GeoServera (jak w iung_wcs_201305.txt)."""
    e0, n0, e1, n1 = bounds
    rows = "\n".join(" ".join(str(v) for v in r) for r in grid)
    return f"Grid bounds: GeneralBounds[({e0}, {n0}), ({e1}, {n1})]\nGrid CRS: PROJCS[\"x\"]\nContents:\nBand 0:\n{rows}\n"


# ── IUNG: WCS ───────────────────────────────────────────────────────────────────────────────


def test_parse_real_wcs_and_count_cells_in_polygon():
    grid, bounds = parse_wcs_text(WCS_201305)
    assert grid.shape == (16, 26)  # 80 m × 130 m w komórkach 5 m; wiersz 0 = północ
    r = count_cells(GEOM_201305, grid, bounds)
    assert r.method == "wcs" and r.cell_size_m == 5.0
    assert r.total == 236  # ≈ 0,5822 ha / 25 m²
    assert set(r.counts) == {1, 3}
    assert r.shares[3] == pytest.approx(0.75, abs=0.01) and r.dominant == 3
    assert r.agricultural_share == 1.0
    assert r.wod_mm == pytest.approx(0.75 * 186.2 + 0.25 * 106.3, abs=0.5)
    assert r.not_agricultural_code is None


def test_count_cells_orientation_row0_is_north():
    # 2×2 komórki 5 m: górny wiersz (północ) = 11, dolny = 3; działka w dolnej połowie
    grid = np.array([[11, 11], [3, 3]])
    r = count_cells(box(0, 0, 10, 5), grid, (0.0, 0.0, 10.0, 10.0))
    assert r.counts == {3: 2}


def test_tiny_parcel_smaller_than_cell_uses_cell_with_point():
    grid = np.array([[2, 4], [1, 3]])
    r = count_cells(box(6, 6, 7, 7), grid, (0.0, 0.0, 10.0, 10.0))  # w komórce NE
    assert r.counts == {4: 1}


def test_nodata_cells_excluded_from_shares():
    r = count_cells(box(0, 0, 10, 10), np.array([[0, 2], [255, 2]]), (0.0, 0.0, 10.0, 10.0))
    assert r.counts == {2: 2} and r.nodata == 2 and r.nodata_share == 0.5


@respx.mock
def test_large_parcel_requests_scalefactor():
    big = box(500000, 400000, 503000, 403000)  # 3 km × 3 km = 360 000 komórek 5 m
    route = respx.get(settings.iung_wcs_url).mock(
        return_value=httpx.Response(200, text=wcs_text([[3, 3], [3, 3]], (500000, 400000, 503000, 403000)))
    )
    r = _run(iung.fetch_wcs(big))
    params = route.calls.last.request.url.params
    assert params.get_list("SUBSET") == ["x(400000.0,403000.0)", "y(500000.0,503000.0)"]  # x = północ
    assert 0 < float(params["SCALEFACTOR"]) < 1
    assert r.counts == {3: 4}


# ── IUNG: GetFeatureInfo (zapas) i przełączenie ─────────────────────────────────────────────


def test_parse_gfi():
    import json

    assert iung.parse_gfi(json.loads(GFI_3)) == 3
    assert iung.parse_gfi({"features": [{"properties": {"GRAY_INDEX": 0}}]}) is None
    assert iung.parse_gfi({"features": []}) is None


@respx.mock
def test_wcs_error_falls_back_to_points():
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(500))
    gfi = respx.get(settings.iung_wms_url).mock(return_value=httpx.Response(200, text=GFI_3))
    r = _run(iung.soil_for_parcel(GEOM_201305))
    assert r.method == "punkty" and r.counts == {3: r.total} and 1 <= r.total <= settings.soil_sample_points
    assert gfi.call_count == r.total
    a = assess_soil(r)
    assert a.degrades_confidence and any("metodą zapasową" in x for x in a.limitations)
    assert a.sources[0].status == "czesciowo"


@respx.mock
def test_iung_down_gives_no_data_and_lower_confidence():
    respx.get(settings.iung_wcs_url).mock(side_effect=httpx.ConnectError("dns"))
    respx.get(settings.iung_wms_url).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceError) as e:
        _run(iung.soil_for_parcel(GEOM_201305))
    a = assess_soil(e.value)  # analiza się nie wywraca
    assert a.soil_capacity.value is None
    assert a.soil_capacity.source_tag.kind == "brak_danych"
    assert a.degrades_confidence and a.sources[0].status == "brak"
    assert "pewność wyniku obniżona" in a.limitations[0]


# ── ocena gleby ─────────────────────────────────────────────────────────────────────────────


def test_assess_agricultural_soil():
    a = assess_soil(SoilResult(counts={2: 60, 3: 40}, method="wcs"))
    ind = a.soil_capacity
    assert ind.value == round(0.6 * 148.7 + 0.4 * 186.2)
    assert ind.unit == "mm" and ind.label == "Kat. II – podatna na suszę" and ind.status == "warn"
    assert ind.source_tag.kind == "pomiar" and ind.source_tag.source == "IUNG-PIB"
    assert not a.not_agricultural and not a.degrades_confidence


@pytest.mark.parametrize(
    ("counts", "flag", "reason"),
    [
        ({11: 60, 3: 40}, True, "las lub zadrzewienie"),
        ({5: 51, 2: 49}, True, "gleby organiczne"),
        ({12: 30, 13: 25, 3: 45}, True, "woda"),  # łącznie 55% nierolne
        ({11: 50, 3: 50}, False, None),  # dokładnie 50% – jeszcze grunt rolny
    ],
)
def test_not_agricultural_flag(counts, flag, reason):
    a = assess_soil(SoilResult(counts=counts, method="wcs"))
    assert a.not_agricultural is flag
    if flag:
        assert reason in a.not_agricultural_reason
        assert a.soil_capacity.value is None and a.soil_capacity.label == "Nie dotyczy"
        assert "nie ma tu zastosowania" in a.soil_capacity.note
    assert any("tylko gleby mineralne" in x for x in a.limitations)


# ── KIEG ────────────────────────────────────────────────────────────────────────────────────


def test_kieg_parse_with_classes():
    f = kieg.parse_html(KIEG_CLASSES)
    assert f["Identyfikator działki"] == "201305_2.0038.6/1"
    assert f["Oznaczenie konturu"] == "RIIIb,RIVa,RIVb"
    r = kieg.merge("201305_2.0038.6/1", [f, f])
    assert r.classes == ["RIIIb", "RIVa", "RIVb"] and r.available and r.points_matched == 2
    assert "Grupa rejestrowa" not in r.raw_fields  # nie przenosimy pól o właścicielach


def test_kieg_without_classes_is_not_an_error():
    r = kieg.merge("040703_5.0020.76", [kieg.parse_html(KIEG_NONE)])
    assert r.classes is None and not r.available
    assert r.note == kieg.NO_CLASSES_NOTE
    a = assess_soil(SoilResult(counts={3: 10}, method="wcs"), r)
    assert not a.degrades_confidence
    assert any("niedostępne w tym powiecie" in x for x in a.limitations)


def test_kieg_ignores_neighbour_parcel():
    other = kieg.parse_html(KIEG_CLASSES)  # dotyczy 201305_2.0038.6/1
    r = kieg.merge("201305_2.0038.6/2", [other])
    assert r.classes is None and r.points_matched == 0


def test_kieg_down_is_informational_only():
    a = assess_soil(SoilResult(counts={3: 10}, method="wcs"), SourceError(kieg.SOURCE, "timeout"))
    assert not a.degrades_confidence
    assert a.sources[-1].status == "brak"


# ── endpoint deweloperski ───────────────────────────────────────────────────────────────────


@respx.mock
def test_dev_soil_endpoint(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=WCS_201305))
    respx.get(settings.kieg_url).mock(return_value=httpx.Response(200, text=KIEG_CLASSES))
    r = client.get("/api/dev/soil", params={"parcel_id": "201305_2.0038.6/1"})
    assert r.status_code == 200
    b = r.json()
    assert b["dominant_code"] == 3 and b["method"] == "wcs" and b["cells"] == 236
    assert b["soil_capacity"]["value"] == 166 and b["soil_capacity"]["source_tag"]["kind"] == "pomiar"
    assert b["classes"] == ["RIIIb", "RIVa", "RIVb"]
    assert "RIIIb" in b["soil_capacity"]["note"]
    assert {s["name"] for s in b["sources"]} == {"IUNG-PIB", "EGiB (KIEG)"}


@respx.mock
def test_dev_soil_endpoint_survives_source_failures(client):
    respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE))
    respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(503))
    respx.get(settings.iung_wms_url).mock(return_value=httpx.Response(503))
    respx.get(settings.kieg_url).mock(side_effect=httpx.ReadTimeout("slow"))
    r = client.get("/api/dev/soil", params={"parcel_id": "201305_2.0038.6/1"})
    assert r.status_code == 200
    b = r.json()
    assert b["soil_capacity"]["value"] is None and b["degrades_confidence"] is True
    assert b["classes"] is None
    assert [s["status"] for s in b["sources"]] == ["brak", "brak"]


# ── test na żywo (pytest -m live -s) ────────────────────────────────────────────────────────

LIVE_PARCELS = [
    "201305_2.0038.6/1",
    "061704_2.0011.383/2",
    "040703_5.0020.76",
    "302114_5.0018.445",
    "160703_5.0011.945",
    "143203_2.0027.112/11",
]


@pytest.mark.live
def test_live_soil_test_parcels():
    import time

    async def one(pid):
        t0 = time.perf_counter()
        [p] = await uldk.by_id(pid)
        res = await asyncio.gather(
            iung.soil_for_parcel(p.geom_2180), kieg.classes_for_parcel(p.id, p.geom_2180), return_exceptions=True
        )
        a = assess_soil(*res)
        return pid, p.area_ha, a, time.perf_counter() - t0

    async def run_all():
        try:
            return [await one(pid) for pid in LIVE_PARCELS]
        finally:
            await close_client()

    rows = asyncio.run(run_all())
    print("\n| działka | ha | dominująca | udziały | WOD mm | klasy EGiB | nierolna | metoda | czas s |")
    for pid, ha, a, sec in rows:
        sh = ", ".join(f"{s.code}: {round(s.share * 100)}%" for s in a.shares if s.share >= 0.005)
        print(f"| {pid} | {ha} | {a.dominant_code} | {sh} | {a.wod_mm} | {a.classes} | "
              f"{a.not_agricultural_reason or 'nie'} | {a.method} | {sec:.2f} |")
    by = {pid: a for pid, _, a, _ in rows}
    assert by["201305_2.0038.6/1"].classes and not by["201305_2.0038.6/1"].not_agricultural
    assert by["061704_2.0011.383/2"].classes
    assert by["040703_5.0020.76"].classes is None
    assert by["160703_5.0011.945"].not_agricultural and by["160703_5.0011.945"].dominant_code == 11
    assert by["143203_2.0027.112/11"].not_agricultural and by["143203_2.0027.112/11"].dominant_code == 11
    assert all(a.method == "wcs" for a in by.values())
