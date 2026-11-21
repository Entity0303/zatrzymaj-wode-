"""A5: wnioski z konsultacji (mało i jasno, ostrzeżenia, formalności, retencja zawsze, nawożenie przy suszy,
ekoschematy, płodozmian), gleba dla rolnika (SoilGrids, Saxton i Rawls, mapa glebowo-rolnicza), odporność
na awarie źródeł (przeterminowany cache) – bez sieci."""

import asyncio
from datetime import date

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis.crops import CROPS
from app.analysis.facts import Facts
from app.analysis.recommendations import (
    CATEGORY_ORDER,
    ECO_SCHEMES,
    LOW_CONFIDENCE_WARNING,
    MAX_PANEL,
    MAX_TOTAL,
    PERMITS,
    _validate,
    evaluate,
    load_rules,
)
from app.analysis.soil_texture import ksat_saxton_rawls, permeability, rain_retention, texture, usda_class
from app.core.cache import TTLCache, cached_fetch, stale_scope
from app.core.config import settings
from app.core.http import SourceError
from app.main import app
from app.schemas.analysis import AnalysisResponse
from app.sources import iung, kieg, soil_map, soilgrids, uldk, weather_openmeteo, weather_power
from test_analysis import KIEG_CLASSES, NASA, OM, SOIL_MAP, SOILGRIDS, ULDK_ONE, WCS_201305, facts

Q = {"parcel_id": "201305_2.0038.6/1", "crop": "zboza_ozime", "date": "2018-06-10"}
ALL_CACHED = (iung, kieg, uldk, weather_power, soilgrids, soil_map)


@pytest.fixture(autouse=True)
def _clean():
    for m in ALL_CACHED:
        m.clear_cache()
    weather_openmeteo.clear_archive_cache()
    weather_openmeteo.clear_cache()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def mock_all() -> dict[str, respx.Route]:
    return {
        "uldk": respx.get(settings.uldk_url).mock(return_value=httpx.Response(200, text=ULDK_ONE)),
        "nasa": respx.get(settings.nasa_power_url).mock(return_value=httpx.Response(200, json=NASA)),
        "archive": respx.get(settings.open_meteo_archive_url).mock(return_value=httpx.Response(200, json=OM)),
        "wcs": respx.get(settings.iung_wcs_url).mock(return_value=httpx.Response(200, text=WCS_201305)),
        "wms": respx.get(settings.iung_wms_url).mock(return_value=httpx.Response(503)),
        "kieg": respx.get(settings.kieg_url).mock(return_value=httpx.Response(200, text=KIEG_CLASSES)),
        "sg": respx.get(settings.soilgrids_url).mock(return_value=httpx.Response(200, json=SOILGRIDS)),
        "map": respx.get(settings.soil_map_url).mock(return_value=httpx.Response(200, text=SOIL_MAP)),
    }


def rule(**kw):
    base = {"id": "t.x", "category": "agrotechnika", "priority": 50, "title": "T", "description": "D",
            "when": {"all": [{"fact": "month", "gte": 1}]}}
    base.update(kw)
    return _validate(base, "test.yaml")


# ── A2: mało i jasno ────────────────────────────────────────────────────────────────────────


def stress_facts(**kw) -> Facts:
    """Susza w pełni sezonu na lekkiej glebie, zboże po zbożu – pasuje wiele reguł."""
    base = dict(water_pct=15.0, days_to_stress=0, risk="wysokie", strong_stress=True, light_soil=True,
                soil_category=2, soil_category_roman="II", soil_txt="kat. II, piasek gliniasty", wod_mm=150.0,
                balance_percentile=10.0, stress_days_season=25, stress_days_mean=5.0, stress_ratio=5.0,
                irrigation_status="zalecane", irrigation_message="22,5 mm teraz", irrigation_when="teraz",
                irrigation_confidence="ograniczona", previous_crop="zboza_jare", previous_crop_label="zboża jare",
                same_crop=False, cereal_after_cereal=True, rotation_issue="zboże po zbożu",
                rain_retention="splywa", rain_retention_label="ryzyko spływu i zastoisk", ksat_mm_h=8.0)
    base.update(kw)
    return facts(**base)


def test_panel_max_3_passport_max_5():
    ev = evaluate(stress_facts())
    assert len(ev.all_matched) > MAX_TOTAL  # reguł pasuje więcej, niż pokazujemy
    recs = ev.recommendations
    assert len(recs) == MAX_TOTAL
    panel = [r for r in recs if r.in_panel]
    assert len(panel) == MAX_PANEL and {r.category for r in panel} == set(CATEGORY_ORDER)
    cats = [r.category for r in recs]
    assert cats == sorted(cats, key=CATEGORY_ORDER.index)


def test_low_confidence_has_warning_and_is_never_first():
    recs = evaluate(stress_facts()).recommendations
    low = [r for r in recs if r.confidence == "ograniczona"]
    assert low and all(r.warning == LOW_CONFIDENCE_WARNING for r in low)
    assert all(r.warning is None for r in recs if r.confidence != "ograniczona")
    assert recs[0].warning is None
    for cat in CATEGORY_ORDER:  # w każdej grupie pewne przed niepewnymi
        flags = [r.warning is not None for r in recs if r.category == cat]
        assert flags == sorted(flags)
    # nawet z wyższym priorytetem niepewna reguła nie wyprzedza pewnej
    rs = (rule(id="t.pewna", priority=10, confidence="srednia"), rule(id="t.niepewna", priority=99, confidence="ograniczona"))
    assert [r.id for r in evaluate(facts(), rules=rs).recommendations] == ["t.pewna", "t.niepewna"]


# ── A4: formalności ─────────────────────────────────────────────────────────────────────────


def test_permit_for_every_rule_and_category():
    rules = load_rules()
    assert all(r.permit in PERMITS for r in rules)
    assert {r.permit for r in rules if r.category == "nawadnianie"} == {"required"}
    assert {r.permit for r in rules if r.category == "agrotechnika"} == {"none"}
    by_id = {r.id: r.permit for r in rules}
    assert by_id["retencja.zastawka_na_rowie"] == by_id["retencja.oczko_w_zaglebieniu"] == "maybe"
    assert by_id["retencja.mokradlo_srodpolne"] == "maybe" and by_id["retencja.pas_buforowy_na_stoku"] == "none"
    for r in evaluate(stress_facts()).recommendations:
        assert r.permit_note
        assert (r.permit_url is None) == (r.permit == "none")
        if r.permit != "none":
            assert r.permit_url == "https://www.gov.pl/web/wody-polskie" and "Wod" in r.permit_note


def test_permit_none_first_in_group():
    rs = (rule(id="t.zgloszenie", category="retencja", priority=99, permit="maybe"),
          rule(id="t.bez", category="retencja", priority=10))
    recs = evaluate(facts(), rules=rs).recommendations
    assert [r.id for r in recs] == ["t.bez", "t.zgloszenie"] and recs[0].in_panel


# ── A3: retencja zawsze, „teraz” przed działaniami na później ──────────────────────────────


@pytest.mark.parametrize("crop_id", sorted(CROPS))
def test_retention_always_present_in_and_off_season(crop_id):
    crop = CROPS[crop_id]
    for month in range(1, 13):
        info = crop.day_info(date(2025, month, 15))
        f = facts(crop=crop_id, crop_kind=crop.kind, crop_label=crop.label, month=month, phase=info.phase,
                  phase_label=info.phase, sensitive=info.sensitive, in_season=info.phase in
                  {"poczatkowa", "rozwoj", "pelnia", "dojrzewanie"}, off_season=info.phase in
                  {"przed_siewem", "po_zbiorze", "spoczynek_zimowy", "wschody_jesienne"},
                  water_pct=95.0, balance_percentile=90.0, balance_deviation_mm=40.0,
                  balance_vs_mean_txt="o 40 mm więcej niż zwykle", stress_days_season=0, stress_ratio=0.0)
        recs = evaluate(f).recommendations
        ret = [r for r in recs if r.category == "retencja"]
        assert ret, f"{crop_id}, miesiąc {month}, faza {info.phase}: brak rekomendacji retencyjnej"
        assert recs[0].category == "retencja" and recs[0].in_panel and recs[0].warning is None


def test_in_season_retention_after_harvest_with_deficit():
    rec = next(r for r in evaluate(facts(balance_mm=-111.0, balance_vs_mean_txt="o 90 mm mniej niż zwykle")).recommendations
               if r.category == "retencja")
    assert rec.id == "retencja.po_zbiorze_miedzyplon" and rec.when == "po_zbiorze" and rec.when_label == "po zbiorze"
    assert "−111 mm" in rec.description and "o 90 mm mniej niż zwykle" in rec.description


def test_autumn_winter_retention_text():
    f = facts(crop="zboza_jare", crop_kind="jara", month=11, phase="po_zbiorze", in_season=False, off_season=True,
              sensitive=False)
    rec = next(r for r in evaluate(f).recommendations if r.category == "retencja")
    assert rec.id == "retencja.zima_bez_orki" and "roztop" in rec.title and "Nie orz na zimę" in rec.description
    assert rec.when == "teraz" and rec.eco_scheme.code == "E_USU"


def test_now_before_next_season_in_panel():
    rs = (rule(id="t.na_potem", priority=99, timing="przed_sezonem"), rule(id="t.teraz", priority=10))
    recs = evaluate(facts(), rules=rs).recommendations
    assert recs[0].id == "t.teraz" and recs[0].in_panel and not recs[1].in_panel
    assert recs[1].when_label == "przed następnym sezonem"
    # timing zależny od pory roku
    r = rule(id="t.prochnica", timing={"in_season": "po_zbiorze", "off_season": "teraz"})
    assert r.when_for(facts()) == "po_zbiorze" and r.when_for(facts(off_season=True)) == "teraz"


# ── A5: nawożenie przy suszy ────────────────────────────────────────────────────────────────


def test_postpone_fertilization_under_strong_stress():
    recs = evaluate(stress_facts()).recommendations
    odloz = next(r for r in recs if r.id == "agrotechnika.odloz_nawozenie")
    assert odloz.in_panel and "nie zadziała" in odloz.title and "15% wody" in odloz.description
    assert odloz.eco_scheme is None  # A5b-1: bez ekoschematu przy „odłóż nawożenie”
    assert not any(r.id == "agrotechnika.odloz_nawozenie" for r in evaluate(facts()).recommendations)


def test_no_fertilization_rule_under_stress():
    rs = (rule(id="t.nawoz_teraz", fertilization=True), rule(id="t.nawoz_po_zbiorze", fertilization=True, timing="po_zbiorze"))
    ids = [r.id for r in evaluate(stress_facts(), rules=rs).recommendations]
    assert ids == ["t.nawoz_po_zbiorze"]  # „teraz” przy silnym stresie – pominięta
    assert [r.id for r in evaluate(facts(), rules=rs).recommendations] == ["t.nawoz_teraz", "t.nawoz_po_zbiorze"]
    for r in evaluate(stress_facts(), limit=False).recommendations:  # żadna reguła z YAML nie każe teraz nawozić
        if r.when == "teraz" and r.id != "agrotechnika.odloz_nawozenie":
            assert "nawóz" not in r.description.lower() and "nawoż" not in r.description.lower()


# ── A6/A7: ekoschematy i płodozmian ─────────────────────────────────────────────────────────


def test_eco_schemes_without_amounts():
    for e in ECO_SCHEMES.values():
        assert "ARiMR" in e.note and "zł" not in e.practice + e.name + e.note
    by_id = {r.id: r for r in load_rules()}
    assert by_id["retencja.po_zbiorze_miedzyplon"].eco_scheme == "E_MPW"
    assert by_id["agrotechnika.plodozmian"].eco_scheme is None  # E_ZSU poza listą ARiMR 2026
    assert by_id["retencja.prochnica"].eco_scheme == "E_WSG"
    rec = next(r for r in evaluate(facts()).recommendations if r.id == "retencja.po_zbiorze_miedzyplon")
    assert rec.eco_scheme.name.startswith("Rolnictwo węglowe") and rec.eco_scheme.code == "E_MPW"


def test_crop_rotation_rule():
    same = facts(previous_crop="zboza_ozime", previous_crop_label="zboża ozime", same_crop=True,
                 cereal_after_cereal=True, rotation_issue="ta sama uprawa drugi rok z rzędu")
    rec = next(r for r in evaluate(same, limit=False).recommendations if r.id == "agrotechnika.plodozmian")
    assert rec.permit == "none" and rec.when == "przed_sezonem" and rec.eco_scheme is None
    assert "Rok temu zboża ozime, teraz zboża ozime – ta sama uprawa" in rec.description
    other = facts(previous_crop="rzepak", previous_crop_label="rzepak i rzepik", same_crop=False, cereal_after_cereal=False)
    assert "agrotechnika.plodozmian" not in [r.id for r in evaluate(other, limit=False).recommendations]
    assert "agrotechnika.plodozmian" not in [r.id for r in evaluate(facts(), limit=False).recommendations]  # „nie wiem”


# ── A8: gleba dla rolnika ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("sand", "silt", "clay", "cls"),
    [(92, 5, 3, "sand"), (82, 12, 6, "loamy_sand"), (66, 24, 10, "sandy_loam"), (40, 40, 20, "loam"),
     (20, 65, 15, "silt_loam"), (5, 88, 7, "silt"), (30, 35, 35, "clay_loam"), (10, 40, 50, "silty_clay"),
     (20, 20, 60, "clay")],
)
def test_usda_texture_class(sand, silt, clay, cls):
    assert usda_class(sand, silt, clay) == cls


def test_ksat_saxton_rawls_and_rain_retention():
    sand, loam, clay = ksat_saxton_rawls(92, 3, 1.0), ksat_saxton_rawls(40, 20, 1.0), ksat_saxton_rawls(30, 35, 1.0)
    assert sand > 100 and 8 < loam < 20 and clay < 6  # wartości tabelaryczne Saxton i Rawls (2006)
    assert rain_retention(sand) == "ucieka" and rain_retention(loam) == "zatrzymuje" and rain_retention(clay) == "splywa"
    assert rain_retention(30) == "zatrzymuje" and rain_retention(5) == "splywa"
    assert ksat_saxton_rawls(66.5, 9.1, 3.0) > ksat_saxton_rawls(66.5, 9.1, 1.0)  # próchnica zwiększa Ksat


def test_soilgrids_parse_and_texture():
    sg = soilgrids.parse_response(SOILGRIDS, 22.64, 52.86)
    assert sg.sand_pct + sg.silt_pct + sg.clay_pct == pytest.approx(100, abs=0.2)
    assert 60 < sg.sand_pct < 75 and sg.soc_g_kg is not None
    t = texture(sg)
    assert t.texture_code == "sandy_loam" and t.texture_class == "glina piaszczysta" and t.depth == "0–30 cm"
    p = permeability(t)
    assert p.ksat_mm_h > 0 and p.description and p.method.startswith("Saxton")
    assert soilgrids.parse_response({"properties": {"layers": []}}, 0, 0) is None  # brak danych ≠ awaria


def test_soil_map_parse():
    m = soil_map.parse_response(SOIL_MAP)
    assert m.complex_code == "2" and m.complex_label == "pszenny dobry"
    assert m.species_code == "glp" and m.species_label == "glina lekka pylasta" and m.mapped_year == 1973
    assert m.soil_type_code == "Bw"
    empty = '<?xml version="1.0"?><FeatureInfoResponse xmlns="http://www.esri.com/wms"></FeatureInfoResponse>'
    assert soil_map.parse_response(empty) is None
    assert soil_map.label("pl") == "piasek luźny" and "pl" in soil_map.SANDY


@respx.mock
def test_analysis_soil_section_and_previous_crop(client):
    mock_all()
    r = client.get("/api/analysis", params={**Q, "previous_crop": "zboza_ozime"})
    assert r.status_code == 200, r.text
    a = AnalysisResponse.model_validate(r.json())
    assert a.previous_crop == "zboza_ozime"
    assert a.soil.texture.texture_class == "glina piaszczysta" and a.soil.permeability.ksat_mm_h > 0
    assert a.soil.soil_map.species_label == "glina lekka pylasta" and a.soil.soil_map.mapped_year == 1973
    names = {s.name: s.status for s in a.reliability.sources}
    assert names["SoilGrids (ISRIC)"] == "ok" and names["Mapa glebowo-rolnicza (GUGiK)"] == "ok"
    assert len(a.recommendations) <= MAX_TOTAL and sum(x.in_panel for x in a.recommendations) <= MAX_PANEL
    assert any(x.category == "retencja" for x in a.recommendations)
    assert any(s.id == "soilgrids" and s.state == "done" for s in a.steps)


@respx.mock
def test_analysis_without_soilgrids_and_soil_map(client):
    routes = mock_all()
    routes["sg"].mock(return_value=httpx.Response(503))
    routes["map"].mock(return_value=httpx.Response(503))
    r = client.get("/api/analysis", params=Q)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["soil"]["texture"] is None and b["soil"]["permeability"] is None and b["soil"]["soil_map"] is None
    assert "Frakcje gleby: brak danych" in b["soil"]["texture_note"]
    st = {s["id"]: s["state"] for s in b["steps"]}
    assert st["soilgrids"] == "error" and st["soil_map"] == "error"
    assert b["status"]["level"] != "no_data" and b["recommendations"]  # analiza działa dalej


@respx.mock
def test_analysis_unknown_previous_crop_422(client):
    r = client.get("/api/analysis", params={**Q, "previous_crop": "banany"})
    assert r.status_code == 422


# ── B3: przeterminowany cache przy awarii źródła ────────────────────────────────────────────


def test_cached_fetch_uses_stale_entry_and_notes_it():
    c: TTLCache[int] = TTLCache(ttl_s=60)

    async def ok():
        return 1

    async def fail():
        raise SourceError("X", "nie odpowiada")

    async def scenario():
        with stale_scope() as hits:
            assert await cached_fetch(c, "k", "X", ok) == 1
            c.expire_all()
            assert c.get("k") is None and c.get_stale("k")[0] == 1
            assert await cached_fetch(c, "k", "X", fail) == 1
        assert len(hits) == 1 and hits[0].source == "X" and hits[0].reason == "nie odpowiada"
        with pytest.raises(SourceError):
            await cached_fetch(TTLCache(ttl_s=60), "k", "X", fail)  # bez wpisu w cache – błąd

    asyncio.run(scenario())


@respx.mock
def test_analysis_uses_stale_cache_when_sources_down(client):
    routes = mock_all()
    first = client.get("/api/analysis", params=Q).json()
    for m in ALL_CACHED:
        m._cache.expire_all()
    for k in ("uldk", "nasa", "wcs", "kieg", "sg", "map"):
        routes[k].mock(return_value=httpx.Response(503))
    routes["archive"].mock(return_value=httpx.Response(429))
    r = client.get("/api/analysis", params=Q)
    assert r.status_code == 200, r.text
    b = r.json()
    order = ["wysoka", "srednia", "ograniczona"]
    assert order.index(b["reliability"]["confidence"]) == min(order.index(first["reliability"]["confidence"]) + 1, 2)
    assert any("dane z cache z dnia" in x for x in b["reliability"]["limitations"])
    nasa = next(s for s in b["reliability"]["sources"] if s["name"] == "NASA POWER")
    assert nasa["status"] == "czesciowo" and "dane z cache z dnia" in nasa["note"]
    assert b["status"]["score"] == first["status"]["score"]  # te same dane – ten sam wynik


def test_cached_fetch_timeout_falls_back_to_stale():
    c: TTLCache[int] = TTLCache(ttl_s=60)

    async def slow():
        await asyncio.sleep(1)
        return 2

    async def scenario():
        c.set("k", 1)
        c.expire_all()
        with stale_scope() as hits:
            assert await cached_fetch(c, "k", "KIEG", slow, timeout_s=0.05) == 1
        assert hits[0].reason == "brak odpowiedzi w 0 s"
        with pytest.raises(SourceError, match="brak odpowiedzi"):
            await cached_fetch(TTLCache(ttl_s=60), "k", "KIEG", slow, timeout_s=0.05)

    asyncio.run(scenario())


def test_breaker_skips_failing_source_then_uses_stale():
    c: TTLCache[int] = TTLCache(ttl_s=60)
    calls = []

    async def fail():
        calls.append(1)
        raise SourceError("SoilGrids (ISRIC)", "usługa nie odpowiada")

    async def scenario():
        with pytest.raises(SourceError):
            await cached_fetch(c, "a", "SoilGrids (ISRIC)", fail, breaker_s=300)
        with pytest.raises(SourceError, match="ponowna próba"):  # bezpiecznik – bez zapytania
            await cached_fetch(c, "b", "SoilGrids (ISRIC)", fail, breaker_s=300)
        assert len(calls) == 1
        c.set("b", 7)
        c.expire_all()
        assert await cached_fetch(c, "b", "SoilGrids (ISRIC)", fail, breaker_s=300) == 7  # stary wpis
        c.clear()
        with pytest.raises(SourceError):
            await cached_fetch(c, "a", "SoilGrids (ISRIC)", fail, breaker_s=300)
        assert len(calls) == 2  # po wyczyszczeniu bezpiecznik zresetowany

    asyncio.run(scenario())


def test_light_soil_from_soil_map_species():
    assert {"pgl", "pgm", "pl", "ps"} <= soil_map.LIGHT and "glp" not in soil_map.LIGHT and "gs" not in soil_map.LIGHT



def test_off_season_warn_headline_matches_data():
    from app.analysis.scoring import overall_status
    from test_analysis import SOIL_OK

    base = dict(phase="dojrzewanie", phase_label="dojrzewanie", sensitive=False, water_pct=59.0, water_rank_pct=40.0)
    wetter = overall_status(facts(**base, balance_deviation_mm=40.0, balance_percentile=70.0), SOIL_OK)
    drier = overall_status(facts(**base, balance_deviation_mm=-40.0, balance_percentile=30.0), SOIL_OK)
    assert wetter.level == drier.level == "warn"
    assert "niż zwykle" not in wetter.headline and "niż zwykle" in drier.headline
