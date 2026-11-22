"""A5b-2a – ranking „Co tu posiać?” (bez sieci): crops.csv jako źródło prawdy, symulacja i plon FAO-33, kalibracja Ym,
kategorie, płodozmian, powierzchnia, status poza sezonem z percentyli, oziminy w listopadzie, kukurydza bez dawek."""

import csv
import time
from datetime import date

import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from app.analysis import suggestions as S
from app.analysis.crops import ALL_CROPS, CROPS, RANKING_CROPS, get_crop
from app.analysis.field_state import REFERENCE
from app.analysis.recommendations import evaluate
from app.analysis.scoring import overall_status, rank_level
from app.analysis.water_balance import soil_water_model
from app.main import app
from app.routers import analysis as analysis_router
from app.schemas.analysis import AnalysisResponse
from test_a5 import mock_all
from test_analysis import SOIL_OK, facts
from test_water_model import WOD, _dry_2018, _et0_seasonal, _wet, synth

PID = "201305_2.0038.6/1"
LAST = date(2018, 11, 20)


@pytest.fixture(autouse=True)
def _fresh():
    S._sim_memo.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def weather(precip=_dry_2018):
    return synth(date(2006, 8, 1), LAST, precip, _et0_seasonal)


def ctx(**kw) -> S.Context:
    base = dict(wod_mm=186.2, category=3, complex_code="2", voivodeship="podlaskie", area_ha=2.0, area_estimated=False,
                area_note="podana", history=[], soil_txt="kat. III")
    base.update(kw)
    return S.Context(**base)


def items(sug) -> dict:
    return {i.crop_id: i for g in sug.groups for i in g.items}


# ── 0. dane osoby C: jedno źródło prawdy ────────────────────────────────────────────────────


def test_crops_csv_is_single_source_of_truth():
    rows = {r["crop_id"]: r for r in csv.DictReader(open(S.DATA / "crops.csv", encoding="utf-8", newline=""))}
    assert set(rows) == set(ALL_CROPS) and len(ALL_CROPS) == 22 and len(CROPS) == 15 and len(RANKING_CROPS) == 17
    for cid, c in ALL_CROPS.items():
        r = rows[cid]
        assert (c.kc_ini, c.kc_mid, c.kc_end, c.p) == tuple(float(r[k]) for k in ("kc_ini", "kc_mid", "kc_end", "p_depletion"))
        assert c.phases == tuple(int(r[k]) for k in ("faza_ini_dni", "faza_dev_dni", "faza_mid_dni", "faza_late_dni"))
        assert c.irrigation_practice == r["irrigation_practice"] and c.group_id == r["group_id"]
    assert ALL_CROPS["zyto"].ky_total == 0.80 and ALL_CROPS["pszenzyto_ozime"].ky_total == 0.90  # decyzja Dominika
    assert ALL_CROPS["zyto"].group_id == "zboza_ozime" and ALL_CROPS["lubin"].group_id == "straczkowe"
    assert not {"zboza_ozime", "zboza_jare", "rzepak_jesien", "chmiel", "tyton"} & {c.id for c in RANKING_CROPS}
    with pytest.raises(ValueError):
        get_crop("zyto")  # gatunki rankingu nie są uprawą do analizy (kontrakt CropId = 15 upraw)


# ── 1. symulacja i plon FAO-33 ──────────────────────────────────────────────────────────────


def test_relative_yield_known_input():
    phases = ["spoczynek_zimowy"] * 5 + ["poczatkowa"] * 10 + ["rozwoj"] * 10 + ["pelnia"] * 10 + ["dojrzewanie"] * 10
    etc = np.full(45, 4.0)
    eta = etc.copy()
    eta[5:] = 3.0  # w sezonie ETa/ETc = 0,75
    eta[:5] = 0.0  # poza sezonem – nie liczy się
    rye, wheat = ALL_CROPS["zyto"], ALL_CROPS["pszenica_ozima"]
    assert S.relative_yield(rye, phases, eta, etc) == pytest.approx(1 - 0.80 * 0.25)  # Ky sezonowe
    # pszenica: Ky faz 0,2 / 0,6 / 0,5 (iloczyn po fazach, dojrzewanie bez Ky)
    assert S.relative_yield(wheat, phases, eta, etc) == pytest.approx((1 - 0.2 * 0.25) * (1 - 0.6 * 0.25) * (1 - 0.5 * 0.25))
    assert S.relative_yield(rye, phases, etc, etc) == 1.0
    maize = ALL_CROPS["kukurydza_ziarno"]  # Ky faz kukurydzy to szacunek – liczymy sezonowym 1,25
    assert S.relative_yield(maize, phases, eta, etc) == pytest.approx(1 - 1.25 * 0.25)


def test_simulation_ten_full_seasons_dry_year_is_worst():
    w = weather()
    sim = S.simulate(w, ALL_CROPS["pszenica_ozima"], 186.2, LAST)
    assert [y for y, _r, _d in sim] == list(range(2009, 2019))
    rel = {y: r for y, r, _d in sim}
    assert min(rel, key=rel.get) == 2018 and rel[2018] < 0.8 and all(r == 1.0 for y, r in rel.items() if y != 2018)
    assert next(d for y, _r, d in sim if y == 2018) > 20  # niedobór wody w mm
    assert S.last_full_season(ALL_CROPS["kukurydza_ziarno"], date(2018, 9, 1)) == 2017  # zbiór 10 X jeszcze przed nami


def test_sandy_soil_loses_more_than_good_soil():
    w = weather()
    sand = dict((y, r) for y, r, _ in S.simulate(w, ALL_CROPS["pszenica_ozima"], 106.3, LAST))
    good = dict((y, r) for y, r, _ in S.simulate(w, ALL_CROPS["pszenica_ozima"], 218.8, LAST))
    assert sand[2018] < good[2018]


# ── kalibracja Ym ───────────────────────────────────────────────────────────────────────────


def test_potential_yield_from_gus_p90():
    rows = [float(r["plon_dt_ha"]) / 10 for r in csv.DictReader(open(S.DATA / "gus_yields_woj.csv", encoding="utf-8", newline=""))
            if r["crop_id"] == "pszenica_ozima" and r["woj_nazwa"] == "podlaskie"]
    pot = S.potential("pszenica_ozima", "podlaskie")
    assert pot.scope == "wojewodztwo" and pot.years == len(rows) == 10 and pot.trend  # A16: trend + P90 reszt
    yrs = np.arange(2016, 2016 + len(rows))
    line = pot.intercept + pot.slope * yrs
    assert pot.factor == pytest.approx(np.percentile(np.array(rows) / line, 90))
    assert pot.ym_t_ha == pytest.approx(pot.at(2026)) and pot.mean_t_ha == pytest.approx(np.mean(rows))
    flat = S.potential("pszenica_ozima", "podlaskie", before_year=2020)  # 2016–2019: < 5 lat – P90 jak przed A16
    assert not flat.trend and flat.ym_t_ha == pytest.approx(np.percentile(rows[:4], 90))
    assert S.potential("pszenica_ozima", "Podlaskie ").ym_t_ha == pot.ym_t_ha
    assert S.potential("pszenica_ozima", "nieznane").scope == "kraj"


@pytest.mark.parametrize("woj", ["podlaskie", "lubelskie", "wielkopolskie"])
def test_calibration_average_soil_close_to_gus_mean(woj):
    """Przeciętna gleba (WOD odniesienia, współczynnik 1,0): w dobrym roku plon = P90 GUS (z definicji), a P90 GUS
    leży najwyżej ~25% nad średnią GUS – symulowana średnia mieści się więc w paśmie średniej województwa."""
    w = weather(_wet)
    for crop in RANKING_CROPS:
        if crop.kind == "wieloletnia":
            continue
        assert S.reference_level(w, crop, LAST) == pytest.approx(1.0)  # mokre lata – brak strat na glebie odniesienia
        pot = S.potential(crop.id, woj)  # A16: P90 reszt względem trendu (bez ym_adjust) – 0–30% nad linią trendu
        adj = S.config().get("ym_adjust", {}).get(crop.id, 1.0)
        assert 1.0 <= pot.factor / adj <= 1.30, (crop.id, woj)


def test_reference_normalization():
    w = weather()
    crop = ALL_CROPS["ziemniak"]
    ref = S.reference_level(w, crop, LAST)
    raw = [r for _y, r, _d in S.simulate(w, crop, S.REFERENCE_WOD_MM, LAST)]
    assert ref == pytest.approx(np.percentile(raw, 90)) and 0.3 <= ref <= 1.0


# ── kategorie i gleba ───────────────────────────────────────────────────────────────────────


def test_soil_suitability_rules():
    wheat, rye, lupin = ALL_CROPS["pszenica_ozima"], ALL_CROPS["zyto"], ALL_CROPS["lubin"]
    assert S.soil_suitability(wheat, 1, None) == "nieodpowiednia" and S.soil_suitability(wheat, 2, "6") == "nieodpowiednia"
    assert S.soil_suitability(wheat, 3, "2") == "odpowiednia" and S.soil_suitability(wheat, 3, None) == "odpowiednia"
    assert S.soil_suitability(rye, 1, "6") == "odpowiednia" and S.soil_suitability(rye, 3, "2") == "neutralna"
    assert S.soil_suitability(lupin, 4, None) == "nieodpowiednia" and S.soil_suitability(lupin, 2, "5") == "odpowiednia"


def test_category_thresholds():
    ok = S.RotationCheck(status="ok")
    assert S.category("odpowiednia", 1, 0.95, ok) == "polecane"
    assert S.category("odpowiednia", 4, 0.9, ok) == "mozliwe"  # gleba pasuje – woda nie daje „odradzane”
    assert S.category("odpowiednia", 8, 0.6, ok) == "mozliwe"
    assert S.category("neutralna", 1, 0.95, ok) == "mozliwe"
    assert S.category("neutralna", 5, 0.9, ok) == "odradzane" and S.category("neutralna", 1, 0.65, ok) == "odradzane"
    assert S.category("nieodpowiednia", 0, 1.0, ok) == "odradzane"
    assert S.category("odpowiednia", 0, 1.0, S.RotationCheck(status="naruszenie", notes=["x"])) == "odradzane"


def test_weak_soil_rye_not_wheat_good_soil_wheat():
    """Kluczowy przekaz: na słabej ziemi nie siej pszenicy / rzepaku – siej żyto; na dobrej bezpiecznie pszenicę."""
    w = weather()
    weak = items(S.build(w, date(2018, 11, 21), ctx(wod_mm=106.3, category=1, complex_code="7", soil_txt="kat. I")))
    assert weak["pszenica_ozima"].category == "odradzane" and weak["rzepak"].category == "odradzane"
    assert weak["zyto"].category in ("polecane", "mozliwe") and weak["zyto"].rank < weak["pszenica_ozima"].rank
    assert weak["zyto"].soil_suitability == "odpowiednia" and weak["lubin"].category != "odradzane"
    assert "lekka ziemia" in weak["pszenica_ozima"].reason
    good = items(S.build(w, date(2018, 11, 21), ctx()))
    assert good["pszenica_ozima"].category == "polecane" and good["zyto"].category == "mozliwe"
    assert good["pszenica_ozima"].yield_typical_t_ha > weak["pszenica_ozima"].yield_typical_t_ha


def test_ranking_structure_and_item_fields():
    sug = S.build(weather(), date(2018, 11, 21), ctx())
    assert [g.key for g in sug.groups] == ["polowe"]  # A5b-2b: wieloletnie osobno, bez kategorii
    per = {i.crop_id for i in sug.perennials.items}
    assert per == {"drzewa_owocowe", "krzewy_owocowe", "truskawki"} and not per & {i.crop_id for i in sug.groups[0].items}
    assert sug.perennials.label == "Uprawy wieloletnie – inwestycja na lata"
    assert all(p.confidence == "ograniczona" and "osobnej analizy opłacalności" in p.note for p in sug.perennials.items)
    assert len(items(sug)) == 14 and sug.seasons[-1] == 2018 and len(sug.seasons) >= 10
    order = {"polecane": 0, "mozliwe": 1, "odradzane": 2}
    for g in sug.groups:
        cats = [order[i.category] for i in g.items]
        assert cats == sorted(cats) and [i.rank for i in g.items] == list(range(1, len(g.items) + 1))
    w = items(sug)["pszenica_ozima"]
    assert w.weak_year == 2018 and w.yield_weak_t_ha < w.yield_typical_t_ha <= w.yield_potential_t_ha
    assert w.drought_risk_years == sum(y.relative < 0.8 for y in w.yields_by_year) and w.years_simulated == 10
    assert w.reason.count(".") <= 2 and w.reason.endswith(".") and w.price is None
    # A16: analiza z 2018 r. – plony GUS tylko z 2016–2017 (dane sprzed daty), seria krótka → pewność ograniczona
    assert w.irrigation_practice == "not_practiced" and w.confidence == "ograniczona" and len(w.source_tags) == 2
    assert "krótka albo niepełna seria plonów GUS" in w.confidence_note
    low = items(sug)["lubin"]
    assert low.confidence == "ograniczona" and "szacunek" in low.confidence_note and "łubinu nie ma" in low.confidence_note
    assert next(p for p in sug.perennials.items if p.crop_id == "krzewy_owocowe").confidence == "ograniczona"
    assert sug.rotation_hint.startswith("Podaj, co rosło") and "BEZ" not in sug.note and "bez nawadniania" in sug.note


def test_ranking_under_one_second():
    w = weather()
    t0 = time.perf_counter()
    S.build(w, date(2018, 11, 21), ctx())
    assert time.perf_counter() - t0 < 1.0


# ── 2. płodozmian ───────────────────────────────────────────────────────────────────────────


def test_rotation_hard_rule_rapeseed():
    r = S.rotation(ALL_CROPS["rzepak"], ["nie_wiem", "rzepak"])
    assert r.status == "naruszenie" and "2 lata temu" in r.notes[0] and "3 lata przerwy" in r.notes[0]
    assert "po sobie częściej chorują" in r.notes[0]
    assert "kiła kapusty" in r.notes[0]
    assert S.rotation(ALL_CROPS["rzepak"], ["zyto", "pszenica_ozima", "rzepak"]).status == "naruszenie"
    assert S.rotation(ALL_CROPS["rzepak"], ["zyto", "pszenica_ozima", "owies"]).status != "naruszenie"
    sug = items(S.build(weather(), date(2018, 11, 21), ctx(history=["nie_wiem", "rzepak"])))
    assert sug["rzepak"].category == "odradzane" and "kiła kapusty" in sug["rzepak"].reason
    assert sug["pszenica_ozima"].category == "polecane"


def test_rotation_rye_after_rye_and_soft_rules():
    rye = S.rotation(ALL_CROPS["zyto"], ["zyto", "zyto"])
    assert rye.status == "ok" and "znosi uprawę po sobie" in rye.notes[0]  # przerwa 0
    assert S.rotation(ALL_CROPS["pszenica_ozima"], ["pszenica_ozima"]).status == "naruszenie"  # przerwa 1 rok
    soft = S.rotation(ALL_CROPS["pszenica_ozima"], ["jeczmien_jary"])
    assert soft.status == "ostrzezenie" and "niższy plon" in soft.notes[0]  # zły przedplon – nie wykluczenie
    cereal = S.rotation(ALL_CROPS["zyto"], ["pszenica_ozima"])
    assert cereal.status == "ostrzezenie" and "Zboże po zbożu" in cereal.notes[0]
    plus = S.rotation(ALL_CROPS["pszenica_ozima"], ["owies"])
    assert plus.status == "plus" and "owies przerywa choroby" in plus.notes[0]
    assert S.rotation(ALL_CROPS["pszenica_ozima"], ["rzepak"]).status == "plus"
    assert S.rotation(ALL_CROPS["pszenica_ozima"], []).status == "brak_historii"
    assert S.rotation(ALL_CROPS["pszenica_ozima"], ["nie_wiem"]).status == "brak_historii"
    w = weather()
    a = items(S.build(w, date(2018, 11, 21), ctx(history=["jeczmien_jary"])))["pszenica_ozima"]
    b = items(S.build(w, date(2018, 11, 21), ctx(history=["owies"])))["pszenica_ozima"]
    assert a.category != "odradzane" and a.score < b.score  # ostrzeżenie obniża ocenę, plus podnosi


def test_parse_history():
    assert S.parse_history("rzepak, nie_wiem ,zyto,owies") == ["rzepak", "nie_wiem", "zyto"]  # najwyżej 3 lata
    assert S.parse_history(None) == [] and S.parse_history("  ") == []
    with pytest.raises(ValueError):
        S.parse_history("banany")


# ── endpoint: historia, powierzchnia ────────────────────────────────────────────────────────


@pytest.fixture
def long_weather(monkeypatch):
    """Pogoda z 12 lat zamiast krótkiej fikstury NASA (ranking potrzebuje 10 pełnych sezonów)."""
    async def fake(lon, lat, analysis_date, season_start=None):
        w = synth(date(2006, 8, 1), analysis_date.replace(day=max(1, analysis_date.day - 1)), _dry_2018, _et0_seasonal)
        return analysis_router.WeatherLoad(w, date(2006, 8, 1), analysis_date, False, 1)

    monkeypatch.setattr(analysis_router, "load_weather_history", fake)


@respx.mock
def test_analysis_suggestions_history_and_area(client, long_weather):
    mock_all()
    q = {"parcel_id": PID, "date": "2018-11-21"}
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params=q).json())
    s = a.suggestions
    assert s is not None and a.crop is None and a.crop_history == [] and s.rotation_hint
    assert s.area.estimated and s.area.value_ha == a.cultivated_area_ha == pytest.approx(0.58, abs=0.01)
    assert "udział gruntów rolnych" in s.area.note
    wheat = items(s)["pszenica_ozima"]
    assert wheat.total_typical_t == pytest.approx(wheat.yield_typical_t_ha * s.area.value_ha, abs=0.15)
    assert any(st.id == "suggestions" and st.state == "done" for st in a.steps)

    b = AnalysisResponse.model_validate(client.get("/api/analysis", params={
        **q, "crop": "zboza_ozime", "crop_history": "nie_wiem,rzepak", "cultivated_area_ha": "2.5"}).json())
    assert b.crop == "zboza_ozime" and b.crop_history == ["nie_wiem", "rzepak"] and b.cultivated_area_ha == 2.5
    assert not b.suggestions.area.estimated and b.suggestions.rotation_hint is None
    wb = items(b.suggestions)
    assert wb["rzepak"].category == "odradzane" and wb["rzepak"].rotation.status == "naruszenie"
    assert wb["pszenica_ozima"].total_weak_t == pytest.approx(wb["pszenica_ozima"].yield_weak_t_ha * 2.5, abs=0.15)

    c = client.get("/api/analysis", params={**q, "previous_crop": "rzepak"}).json()
    assert c["crop_history"] == ["rzepak"]  # sam przedplon (A5) = historia 1 roku


@respx.mock
def test_history_and_area_validation(client):
    r = client.get("/api/analysis", params={"parcel_id": PID, "crop_history": "banany"})
    assert r.status_code == 422 and "historii pola" in r.json()["detail"]["message"]
    assert client.get("/api/analysis", params={"parcel_id": PID, "cultivated_area_ha": "0"}).status_code == 422
    assert client.get("/api/report.pdf", params={"parcel_id": PID, "crop_history": "banany"}).status_code == 422


@respx.mock
def test_short_weather_gives_null_suggestions(client):
    mock_all()  # fikstura NASA: 2017–2018 – brak 5 pełnych sezonów
    b = client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-06-10"}).json()
    assert b["suggestions"] is None and b["cultivated_area_ha"] is not None


# ── 4. status poza sezonem: percentyle, zimowanie, goła gleba ───────────────────────────────


def test_rank_level_same_date_in_ten_years():
    def f(**kw):
        return facts(**{**dict(water_pct=60.0, water_rank_lower=5, water_rank_of=10, kbw30_rank_lower=5,
                               kbw30_rank_of=10), **kw})

    assert rank_level(f(), "poza_sezonem") == "ok"  # w normie
    assert rank_level(f(water_rank_lower=2), "poza_sezonem") == "warn"  # niżej niż w 8 na 10 lat
    assert rank_level(f(water_rank_lower=3), "poza_sezonem") == "ok"
    assert rank_level(f(water_rank_lower=0), "poza_sezonem") == "risk"  # najniżej od 10 lat
    assert rank_level(f(water_rank_lower=0, water_pct=20.0), "bez_uprawy") == "danger"
    assert rank_level(f(water_rank_lower=0, water_pct=95.0), "poza_sezonem") == "ok"  # pełny profil to nie alarm
    assert rank_level(f(kbw30_rank_lower=0), "poza_sezonem") == "warn"  # 30 dni najsuchsze od 10 lat
    assert rank_level(f(water_rank_of=3), "poza_sezonem") is None  # za mało lat – progi bezwzględne
    s = overall_status(f(phase="po_zbiorze", phase_label="po zbiorze", sensitive=False, water_rank_lower=1), SOIL_OK)
    assert s.level == "warn" and 50 <= s.score <= 69 and s.scope == "poza_sezonem"
    assert "mniej wody było tego dnia w 1 z 10" in s.summary


def test_winter_crops_in_november_are_in_the_field():
    nov = date(2026, 11, 21)
    table = {cid: CROPS[cid].day_info(nov).phase for cid in ("zboza_ozime", "rzepak", "kukurydza_ziarno", "zboza_jare",
                                                             "ziemniak", "drzewa_owocowe")}
    assert table == {"zboza_ozime": "spoczynek_zimowy", "rzepak": "spoczynek_zimowy", "kukurydza_ziarno": "po_zbiorze",
                     "zboza_jare": "po_zbiorze", "ziemniak": "po_zbiorze", "drzewa_owocowe": "spoczynek_zimowy"}
    assert CROPS["zboza_ozime"].day_info(date(2026, 10, 10)).phase == "wschody_jesienne"
    assert CROPS["zboza_ozime"].day_info(date(2026, 8, 20)).phase == "po_zbiorze"  # między zbiorem a siewem
    for phase, scope, label in (("spoczynek_zimowy", "zimowanie", "w polu – zimowanie"),
                                ("wschody_jesienne", "zimowanie", "w polu – zimowanie"),
                                ("po_zbiorze", "poza_sezonem", "poza sezonem")):
        s = overall_status(facts(phase=phase, phase_label=phase, sensitive=False), SOIL_OK)
        assert (s.scope, s.scope_label) == (scope, label)
    assert "Uprawa jest w polu" in overall_status(facts(phase="spoczynek_zimowy", phase_label="spoczynek zimowy",
                                                        sensitive=False), SOIL_OK).summary


def test_field_state_bare_soil_after_typical_harvest():
    assert not REFERENCE.day_info(date(2026, 6, 15)).bare and REFERENCE.day_info(date(2026, 6, 15)).kc == 1.0
    for d in (date(2026, 8, 1), date(2026, 11, 21), date(2026, 2, 10)):
        info = REFERENCE.day_info(d)
        assert info.bare and info.kc < 0.5 and info.zr < 0.2  # parowanie tylko z wierzchniej warstwy


# ── 5. kukurydza: żadnych dawek ─────────────────────────────────────────────────────────────


def test_maize_optional_no_doses_only_information():
    w = synth(date(2006, 8, 1), date(2018, 7, 19), _dry_2018, _et0_seasonal)
    r = soil_water_model(w, get_crop("kukurydza_ziarno"), WOD, date(2018, 7, 20), soil_category=3)
    assert r.sensitive and r.irrigation.dose_mm is None and r.irrigation.doses_7d is None
    assert r.irrigation.status in ("informacyjne", "niepotrzebne")
    if r.irrigation.status == "informacyjne":
        assert "deszczowni" in r.irrigation.message and "Wody Polskie" in r.irrigation.message
    f = facts(crop="kukurydza_ziarno", irrigation_practice="optional", irrigation_status="zalecane",
              irrigation_message="27,5 mm teraz", irrigation_when="teraz", season_deficit_mm=62.0, days_to_stress=0)
    recs = [x for x in evaluate(f, limit=False).recommendations if x.category == "nawadnianie"]
    assert [x.id for x in recs] == ["nawadnianie.informacja_optional"]
    assert "62 mm" in recs[0].description and "mm teraz" not in recs[0].description and recs[0].permit == "required"
    assert recs[0].permit_url and "pozwolenia wodnoprawnego" in recs[0].permit_note
    none = evaluate(facts(irrigation_practice="not_practiced", season_deficit_mm=80.0, irrigation_status="zalecane",
                          irrigation_message="x", irrigation_when="teraz"), limit=False).recommendations
    assert not any(x.category == "nawadnianie" for x in none)  # zboża, rzepak, strączkowe – zero o nawadnianiu
    assert CROPS["burak_cukrowy"].irrigation_practice == "not_practiced" and CROPS["ziemniak"].irrigation_practice == "optional"
