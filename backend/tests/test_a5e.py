"""A5e – wybór rolnika (planned_crops: choice / alternatives / not_recommended), raport krótki i pełny, jeden stan wody
poza sezonem uprawy, zero nawadniania poza sezonem, jedno „najważniejsze”, słupki „Na tle 10 lat”. Bez sieci."""

import io
import re
from datetime import date

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.analysis import choice as CH
from app.analysis import suggestions as S
from app.analysis.crops import ALL_CROPS, CROPS
from app.analysis.water_balance import history_sentence
from app.core.config import settings
from app.main import app
from app.report.builder import render_html
from app.schemas.analysis import AnalysisResponse
from test_a5 import mock_all
from test_a5b2 import long_weather  # noqa: F401 – fixture: pogoda z 12 lat (sucha 2018)
from test_water_model import _dry_2018, _et0_seasonal, synth

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


def ranking(history=(), **kw):
    base = dict(wod_mm=186.2, category=3, complex_code="2", voivodeship="podlaskie", area_ha=2.0, area_estimated=False,
                area_note="podana", history=list(history), soil_txt="kat. III", soil_group="srednia")
    base.update(kw)
    w = synth(date(2006, 8, 1), LAST, _dry_2018, _et0_seasonal)
    return S.build(w, LAST, S.Context(**base))


WEAK = dict(wod_mm=106.3, category=1, complex_code="7", soil_txt="piasek luźny", soil_group="lekka")


# ── 1. planned_crops ────────────────────────────────────────────────────────────────────────


def test_parse_planned_crops():
    assert CH.parse_planned(None) == [] and CH.parse_planned("") == []
    assert CH.parse_planned("pszenica_ozima") == ["pszenica_ozima"]
    assert CH.parse_planned("pszenica_ozima, rzepak,pszenica_ozima") == ["pszenica_ozima", "rzepak"]
    assert CH.parse_planned(["zyto", "lubin", "owies"]) == ["zyto", "lubin", "owies"]
    with pytest.raises(ValueError):
        CH.parse_planned("banany")
    assert CH.parse_planned("zboza_ozime,straczkowe") == ["zboza_ozime", "straczkowe"]  # A5e-2: grupy upraw
    with pytest.raises(ValueError):
        CH.parse_planned("zyto,lubin,owies,rzepak")  # najwyżej 3


def test_choice_without_planned_is_top5_and_not_recommended():
    sug = CH.attach(ranking(**WEAK), [], light=True)
    assert sug.choice == [] and sug.alternatives == [] and sug.choice_summary is None
    field = sug.groups[0].items
    assert sug.top_ids == [i.crop_id for i in field if i.category != "odradzane"][:5]
    assert sug.not_recommended and len(sug.not_recommended) <= 6
    ids = [n.crop_id for n in sug.not_recommended]
    assert ids[:2] == ["pszenica_ozima", "rzepak"]  # najpopularniejsze najpierw
    assert all(n.reason and "%" not in n.reason or "plonu" in n.reason for n in sug.not_recommended)
    assert len(field) == 14  # pełna lista 14 upraw polowych zostaje w API


def test_choice_with_history_wheat_after_wheat():
    sug = CH.attach(ranking(history=["pszenica_ozima"]), ["pszenica_ozima"], light=False)
    (c,) = sug.choice
    assert c.crop_id == "pszenica_ozima" and c.category == "odradzane" and c.rotation.status == "naruszenie"
    assert c.yield_typical_t_ha and c.total_typical_t == pytest.approx(c.yield_typical_t_ha * 2.0, abs=0.15)
    assert c.weak_year and c.years_simulated == 10 and 0 <= c.drought_risk_years <= 10
    assert c.why == "Pszenica ozima rosła tu rok temu – lepiej zrobić rok przerwy."  # A7: nazwa uprawy + odmiana
    assert not re.search(r"\d", c.why)  # „dlaczego” nie powtarza liczb z tabeli
    assert sug.choice_summary == "Pszenica ozima rosła tu rok temu – w tym roku lepiej posiać tu coś innego."
    assert 1 <= len(sug.alternatives) <= 3 and all(a.crop_id != "pszenica_ozima" for a in sug.alternatives)
    assert all(a.category != "odradzane" and a.relation in ("lepsza", "podobna") for a in sug.alternatives)
    rz = next((a for a in sug.alternatives if a.crop_id == "rzepak"), None)
    if rz is not None and "pszenica_ozima" in ALL_CROPS["rzepak"].good_previous + ("zboza_ozime",):
        assert rz.why.startswith("Po pszenicy ozimej rzepak i rzepik – dobry przedplon")


def test_choice_good_pick_says_it_fits():
    sug = CH.attach(ranking(), ["rzepak"], light=False)
    (c,) = sug.choice
    assert c.category == "polecane" and c.rotation.status == "brak_historii"
    assert sug.choice_summary in ("Twój wybór pasuje do tej działki.",
                                  "Twój wybór jest dobry, ale poniżej są uprawy, które wypadają tu jeszcze lepiej.")
    assert c.why in (CH.cfg()["why"]["ok_soil"], CH.cfg()["why"]["ok_tolerant"])


def test_choice_on_weak_soil_one_bad_one_possible():
    sug = CH.attach(ranking(**WEAK), ["pszenica_ozima", "zyto"], light=True)
    cats = {c.crop_id: c.category for c in sug.choice}
    assert cats["pszenica_ozima"] == "odradzane" and cats["zyto"] in ("polecane", "mozliwe")
    wheat = next(c for c in sug.choice if c.crop_id == "pszenica_ozima")
    assert wheat.why == CH.cfg()["why"]["soil_bad_light"]
    assert "pszenica ozima" in sug.choice_summary and "nie polecamy" in sug.choice_summary
    assert all(n.crop_id not in ("pszenica_ozima", "zyto") for n in sug.not_recommended)  # wybrane – w choice


def test_not_recommended_rotation_reason_names_years():
    burak = ALL_CROPS["burak_cukrowy"]
    assert burak.min_break_years >= 2
    sug = CH.attach(ranking(history=["nie_wiem", "burak_cukrowy"]), [], light=False)
    nb = next(n for n in sug.not_recommended if n.crop_id == "burak_cukrowy")
    assert nb.reason == f"rósł tu 2 lata temu – lepiej zrobić {S.years_break(burak.min_break_years)} przerwy"


def test_choice_perennial_has_no_category():
    sug = CH.attach(ranking(), ["truskawki"], light=False)
    (c,) = sug.choice
    assert c.perennial and c.category is None and "wieloletnia" in c.why
    assert sug.choice_summary.startswith("Uprawy wieloletnie")


@respx.mock
def test_api_planned_crops_and_validation(client, long_weather):
    mock_all()
    q = {"parcel_id": PID, "date": "2018-11-21", "planned_crops": "pszenica_ozima", "crop_history": "pszenica_ozima"}
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params=q).json())
    assert a.planned_crops == ["pszenica_ozima"] and a.suggestions.choice[0].crop_id == "pszenica_ozima"
    assert a.suggestions.choice[0].rotation.status == "naruszenie"
    b = client.post("/api/analysis", json={"parcel_id": PID, "date": "2018-11-21", "planned_crops": ["zyto", "lubin"]})
    assert b.status_code == 200 and [c["crop_id"] for c in b.json()["suggestions"]["choice"]] == ["zyto", "lubin"]
    r = client.get("/api/analysis", params={"parcel_id": PID, "planned_crops": "banany"})
    assert r.status_code == 422 and "planie siewu" in r.json()["detail"]["message"]


# ── 2. raport krótki / pełny ────────────────────────────────────────────────────────────────


@respx.mock
def test_report_short_vs_full_pages(client, long_weather):
    settings.terrain_saved_results = True
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    q = {"parcel_id": PID, "date": "2018-11-21", "planned_crops": "pszenica_ozima", "crop_history": "pszenica_ozima"}
    short = client.get("/api/report.pdf", params=q)
    full = client.get("/api/report.pdf", params={**q, "report_type": "full"})
    assert short.status_code == full.status_code == 200
    ps, pf = PdfReader(io.BytesIO(short.content)).pages, PdfReader(io.BytesIO(full.content)).pages
    assert len(ps) == 2 and 5 <= len(pf) <= 10  # A5e-2/F19: skrócony = 2 strony, szczegółowy – reszta
    ts = " ".join(" ".join(p.extract_text() for p in ps).split())
    tf = " ".join(" ".join(p.extract_text() for p in pf).split())
    for phrase in ("Raport skrócony", "Twój wybór", "Co mogę zrobić?", "Bilans wody na tle 10 lat", "dane pogodowe do"):
        assert phrase in ts, phrase
    for phrase in ("Raport szczegółowy", "Woda w glebie", "Gleba i teren", "Wszystkie uprawy",
                   "Szczegóły techniczne"):
        assert phrase in tf, phrase
    assert "Wszystkie uprawy" not in ts
    assert "opad minus parowanie" in ts and "spadło minus wyparowało" not in ts  # F19: słownik jak w aplikacji
    assert "szczegolowy" in full.headers["content-disposition"] and "skrocony" in short.headers["content-disposition"]
    post = client.post("/api/report.pdf", json={**q, "planned_crops": ["pszenica_ozima"], "report_type": "full"})
    assert post.status_code == 200 and len(PdfReader(io.BytesIO(post.content)).pages) == len(pf)


@respx.mock
def test_report_without_choice_shows_top5_and_one_line_not_sow(client, long_weather):
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-11-21"}).json())
    html = render_html(a, ortho=None)
    assert "Co tu posiać" in html and ("Unikaj:" in html or "nie jest tu odradzana" in html)
    assert "Twój wybór:" not in html
    for cid in a.suggestions.top_ids:
        label = next(i.label for i in a.suggestions.groups[0].items if i.crop_id == cid)
        assert label in html


@respx.mock
def test_report_only_one_most_important_action(client, long_weather):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-06-10",
                                                                            "crop": "zboza_ozime"}).json())
    assert sum(r.in_panel for r in a.recommendations) >= 2  # w API nadal do 3 w panelu
    html = render_html(a, ortho=None, report_type="full")
    assert html.count(">Najważniejsze<") == 1
    short = render_html(a, ortho=None)  # F19: jedna lista maks. 3 działań, jedno „Najważniejsze”
    assert short.count(">Najważniejsze<") == 1 and short.split('class="acts"')[1].split("</ol>")[0].count("<li") <= 3


# ── 3. jeden stan wody, zero nawadniania poza sezonem ───────────────────────────────────────


@respx.mock
def test_one_water_state_off_season(client, long_weather):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={
        "parcel_id": PID, "date": "2018-11-21", "crop": "kukurydza_ziarno"}).json())
    assert a.crop_season.phase == "po_zbiorze"
    assert a.status.scope == "bez_uprawy" and a.status == a.field_state.status  # jeden status: stan działki
    assert a.indicators.soil_water_pct.value == a.field_state.soil_water_pct.value  # jedna liczba wody w glebie
    assert a.irrigation is None
    assert not any(r.category == "nawadnianie" for r in a.recommendations)
    chosen = next(s for s in a.verdict.statements if s.kind == "uprawa_wybrana")
    assert "uprawy nie ma w polu" in chosen.text and chosen.numbers["poza_sezonem"] == 1


@respx.mock
def test_crop_state_in_season(client, long_weather):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={
        "parcel_id": PID, "date": "2018-07-10", "crop": "kukurydza_ziarno"}).json())
    assert a.crop_season.phase in ("rozwoj", "pelnia", "poczatkowa")
    assert a.status.scope == "sezon" and a.irrigation is not None
    chosen = next(s for s in a.verdict.statements if s.kind == "uprawa_wybrana")
    assert "uprawy nie ma w polu" not in chosen.text


@respx.mock
def test_wintering_crop_is_in_field_not_field_state(client, long_weather):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={
        "parcel_id": PID, "date": "2018-11-21", "crop": "zboza_ozime"}).json())
    assert a.status.scope == "zimowanie" and a.irrigation is None  # w polu, ale bez nawadniania poza sezonem wzrostu


def test_irrigation_rules_require_in_season():
    import yaml

    rules = yaml.safe_load(open("app/analysis/rules/nawadnianie.yaml", encoding="utf-8"))["rules"]
    for r in rules:
        assert {"fact": "in_season", "eq": True} in r["when"]["all"], r["id"]
    assert CROPS["ziemniak"].irrigation_practice == "optional"  # A5e (D76)


# ── 4. słupki „Na tle 10 lat” i jedno źródło liczby ─────────────────────────────────────────


@respx.mock
def test_seasonal_balance_by_year_consistent(client, long_weather):
    mock_all()
    a = AnalysisResponse.model_validate(client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-11-21"}).json())
    ys = a.seasonal_balance_by_year
    assert len(ys) == 11 and [y.year for y in ys] == list(range(2008, 2019))
    assert [y.current for y in ys] == [False] * 10 + [True]
    cur = ys[-1].balance_mm
    assert cur == a.indicators.water_balance_season.value == round(cur)  # jedna liczba, całe mm
    mean = a.seasonal_balance_mean_mm
    assert mean == round(sum(y.balance_mm for y in ys[:10]) / 10) or abs(mean - sum(y.balance_mm for y in ys[:10]) / 10) <= 1
    assert a.history.balance_deviation_mm == cur - mean  # odchylenie = różnica pokazanych liczb
    lower = sum(y.balance_mm < cur for y in ys[:10])
    assert a.history.balance_rank.lower_years == lower
    assert a.history.summary == history_sentence(lower, 10)
    assert f"{abs(cur):.0f} mm" in a.history.details and f"o {abs(cur - mean):.0f} mm" in a.history.details
    assert a.weather_data_until == date(2018, 11, 20) and a.seasonal_balance_label.startswith("od 1 marca do")
    html = render_html(a, ortho=None)
    for y in ys:
        assert f">{y.year}</text>" in html  # słupek z rokiem na osi
    assert "dane pogodowe do 20.11.2018" in html


@pytest.mark.parametrize("lower,n,start", [
    (0, 10, "Ten rok jest najsuchszy"), (2, 10, "Ten rok jest suchszy niż zwykle – mniej wody było tylko w 2 z ostatnich 10 lat"),
    (4, 10, "Ten rok jest trochę suchszy"), (5, 10, "Pod względem wody ten rok jest przeciętny"),
    (7, 10, "Ten rok jest trochę wilgotniejszy"), (9, 10, "Ten rok jest wilgotniejszy"), (10, 10, "Ten rok jest najwilgotniejszy"),
    (None, 0, "Brak lat porównawczych"),
])
def test_history_sentence(lower, n, start):
    assert history_sentence(lower, n).startswith(start)


# ── A5e-2: raport skrócony = 2 strony, ostrzejsze alternatywy, grupy upraw ──────────────────


@respx.mock
@pytest.mark.parametrize("extra", [
    {},
    {"planned_crops": "pszenica_ozima", "crop_history": "pszenica_ozima"},
    {"planned_crops": "pszenica_ozima,ziemniak,lubin", "crop_history": "pszenica_ozima,rzepak,nie_wiem"},
    {"planned_crops": "zboza_ozime,straczkowe,chmiel", "crop": "zboza_ozime"},
])
def test_short_report_is_exactly_two_pages(client, long_weather, extra):
    settings.terrain_saved_results = True
    mock_all()
    respx.get(settings.ortho_wms_url).mock(return_value=httpx.Response(503))
    r = client.get("/api/report.pdf", params={"parcel_id": PID, "date": "2018-11-21", **extra})
    assert r.status_code == 200, r.text
    pages = PdfReader(io.BytesIO(r.content)).pages
    assert len(pages) == 2
    p2 = " ".join(pages[1].extract_text().split())
    assert "Co tu posiać" in p2 and "Co mogę zrobić?" in p2 and "Bilans wody na tle 10 lat" in p2
    p1 = " ".join(pages[0].extract_text().split())  # F19: wybór rolnika i „Unikaj” na stronie 1
    assert ("Twój wybór" in p1) == bool(extra.get("planned_crops"))
    assert ("Unikaj:" in p1 or "nie jest tu odradzana" in p1)


def test_alternatives_must_have_lower_drought_risk():
    sug = CH.attach(ranking(**WEAK), ["pszenica_ozima"], light=True)
    wheat = next(i for i in sug.groups[0].items if i.crop_id == "pszenica_ozima")
    for a in sug.alternatives:
        assert a.relation == "lepsza" and a.drought_risk_years < wheat.drought_risk_years
        assert "zamiast" in a.why and "t/ha" not in a.why  # w czym lepsza: lata ze stratą, nie same t/ha
    same_risk = [i.crop_id for i in sug.groups[0].items
                 if i.drought_risk_years >= wheat.drought_risk_years and i.crop_id != "pszenica_ozima"]
    assert not {a.crop_id for a in sug.alternatives} & set(same_risk)  # np. ziemniak 7/10 nie jest „lepszy” od 7/10


def test_alternatives_rotation_only_case_explains_break_and_skips_cereal_after_cereal():
    sug = CH.attach(ranking(history=["pszenica_ozima"]), ["pszenica_ozima"], light=False)
    (c,) = sug.choice
    assert c.category == "odradzane" and c.rotation.status == "naruszenie" and CH._rotation_only(
        next(i for i in sug.groups[0].items if i.crop_id == "pszenica_ozima"))
    items = {i.crop_id: i for i in sug.groups[0].items}
    for a in sug.alternatives:
        assert items[a.crop_id].rotation.status != "ostrzezenie"  # jęczmień po pszenicy = zboże po zbożu – nie
        if a.relation == "podobna":
            assert "przerw" in a.why or "przedplon" in a.why


def test_planned_crop_groups_pick_best_species():
    sug = CH.attach(ranking(**WEAK), ["zboza_ozime", "straczkowe", "chmiel"], light=True)
    by_req = {c.requested_id: c for c in sug.choice}
    winter = by_req["zboza_ozime"]
    field = {i.crop_id: i for i in sug.groups[0].items}
    species = [s for s in ("pszenica_ozima", "zyto", "pszenzyto_ozime", "jeczmien_ozimy") if s in field]
    best = min((field[s] for s in species), key=lambda i: (CH.CATEGORY_ORDER[i.category], -i.score))
    assert winter.crop_id == best.crop_id
    assert winter.group_note == f"Z grupy zboża ozime najlepiej wypada: {best.label.lower()}."
    assert by_req["straczkowe"].crop_id in ("straczkowe", "lubin")
    assert sug.choice_notes and sug.choice_notes[0].startswith("Chmiel: tej uprawy nie ma w rankingu")


@respx.mock
def test_api_accepts_groups_and_species_without_422(client, long_weather):
    mock_all()
    a = client.get("/api/analysis", params={"parcel_id": PID, "date": "2018-11-21", "crop": "pszenica_ozima",
                                            "previous_crop": "zyto", "planned_crops": "zboza_jare",
                                            "crop_history": "zboza_ozime"})
    assert a.status_code == 200, a.text
    body = a.json()
    assert body["crop"] == "zboza_ozime" and body["previous_crop"] == "zboza_ozime"  # gatunek → grupa modelu wody
    assert body["planned_crops"] == ["zboza_jare"]
    (c,) = body["suggestions"]["choice"]
    assert c["requested_id"] == "zboza_jare" and c["crop_id"] in ("jeczmien_jary", "owies") and c["group_note"]


def test_rotation_texts_natural_language():
    r = S.rotation(ALL_CROPS["rzepak"], ["nie_wiem", "rzepak"])
    assert r.notes[0].startswith("Rzepak i rzepik rosły tu 2 lata temu – po sobie częściej chorują")
    r = S.rotation(ALL_CROPS["owies"], ["owies"])
    assert r.notes[0].startswith("Owies rósł tu rok temu") and "lepiej zrobić" in r.notes[0]
    assert S.years_break(1) == "rok" and S.years_break(3) == "3 lata" and S.years_break(5) == "5 lat"
