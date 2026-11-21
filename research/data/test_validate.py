"""Testy danych referencyjnych upraw (bez sieci).

    python -m pytest research/data/test_validate.py -q
"""

import copy
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate as V  # noqa: E402

REPO = HERE.parent.parent
CROPS = V.read_csv(HERE / "crops.csv")
IUNG_15 = ["zboża ozime", "zboża jare", "kukurydza na ziarno", "kukurydza na kiszonkę",
           "rzepak i rzepik", "rzepak i rzepik (jesień)", "ziemniak", "burak cukrowy",
           "rośliny strączkowe", "warzywa gruntowe", "drzewa owocowe", "krzewy owocowe",
           "truskawki", "chmiel", "tytoń"]


def test_real_crops_csv_is_valid():
    assert V.validate_crops(CROPS) == []


def test_fifteen_iung_crops():
    groups = [r for r in CROPS if r["group_id"] == r["crop_id"]]
    assert [r["iung_name"] for r in groups] == IUNG_15
    assert {r["iung_name"] for r in CROPS} == set(IUNG_15)


SPECIES = {"pszenica_ozima": "zboza_ozime", "zyto": "zboza_ozime", "pszenzyto_ozime": "zboza_ozime",
           "jeczmien_ozimy": "zboza_ozime", "jeczmien_jary": "zboza_jare", "owies": "zboza_jare",
           "lubin": "straczkowe"}


def test_cereal_species_and_lupin_with_groups():
    by = {r["crop_id"]: r for r in CROPS}
    for cid, grp in SPECIES.items():
        assert by[cid]["group_id"] == grp
        assert by[cid]["in_ranking"] == "tak"


def test_in_ranking_excludes_groups_and_minor_crops():
    by = {r["crop_id"]: r for r in CROPS}
    for cid in ("rzepak_jesien", "chmiel", "tyton", "zboza_ozime", "zboza_jare"):
        assert by[cid]["in_ranking"] == "nie", cid
    ranked = [r["crop_id"] for r in CROPS if r["in_ranking"] == "tak"]
    assert len(ranked) == 17


def _kompleksy(val):
    for part in val.split(";"):
        if part.startswith("kompleksy:"):
            return set(part.split(":", 1)[1].split(","))
    return set()


def test_wheat_vs_rye_soils_and_drought():
    """Werdykt „tu nie siej pszenicy, siej żyto”: na kompleksach żytnich słabych pszenica nie, żyto tak."""
    by = {r["crop_id"]: r for r in CROPS}
    for k in ("6", "7"):
        assert k in _kompleksy(by["pszenica_ozima"]["gleby_nieodpowiednie"])
        assert k in _kompleksy(by["zyto"]["gleby_odpowiednie"])
    assert {"1", "2", "3"} <= _kompleksy(by["pszenica_ozima"]["gleby_odpowiednie"])
    assert by["zyto"]["wrazliwosc_na_susze"] == "niska"
    assert float(by["zyto"]["ky_total"]) < float(by["pszenica_ozima"]["ky_total"])


def test_lupin_light_soils():
    by = {r["crop_id"]: r for r in CROPS}
    assert {"5", "6"} <= _kompleksy(by["lubin"]["gleby_odpowiednie"])
    assert "I" in by["lubin"]["gleby_odpowiednie"]


def test_gus_has_new_species():
    rows = V.read_csv(HERE / "gus_variables.csv")
    ids = {r["crop_id"]: r for r in rows}
    for cid in SPECIES:
        assert ids[cid]["var_id"], cid
    assert ids["zyto"]["var_id"] == "4338"
    assert ids["owies"]["var_id"] == "4350"
    assert ids["pszenzyto_ozime"]["var_id"] == "4356"
    assert "ZASTĘPNIK" in ids["lubin"]["uwagi"]


def test_backend_ids_exist_in_backend_config():
    src = (REPO / "backend" / "app" / "analysis" / "crops.py").read_text(encoding="utf-8")
    backend_ids = set(re.findall(r'Crop\("([a-z_]+)"', src))
    for r in CROPS:
        if r["backend_id"]:
            assert r["backend_id"] in backend_ids, r["backend_id"]


def test_kc_matches_backend():
    src = (REPO / "backend" / "app" / "analysis" / "crops.py").read_text(encoding="utf-8")
    for cid, ini, mid, end in re.findall(r'Crop\("([a-z_]+)", "[^"]+", ([0-9.]+), ([0-9.]+), ([0-9.]+)', src):
        row = next(r for r in CROPS if r["backend_id"] == cid)
        assert (float(row["kc_ini"]), float(row["kc_mid"]), float(row["kc_end"])) == \
               (float(ini), float(mid), float(end)), cid


def test_gus_files_consistent():
    ids = {r["crop_id"] for r in CROPS}
    errs = V.validate_gus(ids, V.read_csv(HERE / "gus_variables.csv"),
                          V.read_csv(HERE / "gus_yields_woj.csv"))
    assert errs == []


def test_gus_yields_16_voivodeships():
    rows = V.read_csv(HERE / "gus_yields_woj.csv")
    wheat = {(r["woj_kod"], r["rok"]) for r in rows if r["crop_id"] == "zboza_ozime"}
    assert len({w for w, _ in wheat}) == 16
    assert len({y for _, y in wheat}) == 10


def bad(**changes):
    rows = copy.deepcopy(CROPS)
    rows[0].update(changes)
    return V.validate_crops(rows)


@pytest.mark.parametrize("changes, fragment", [
    ({"kc_mid": "1.6"}, "kc_mid"),
    ({"kc_ini": "0.1"}, "kc_ini"),
    ({"ky_total": "1.8"}, "ky_total"),
    ({"faza_dev_dni": "0"}, "faza"),
    ({"dobre_przedplony": "rzepak;nie_ma_takiej"}, "nieistniejące"),
    ({"zrodla": ""}, "źródła"),
    ({"typowy_siew": "13-40"}, "typowy_siew"),
    ({"irrigation_practice": "sometimes"}, "irrigation_practice"),
    ({"gleby_odpowiednie": "iung:V"}, "gleby_odpowiednie"),
    ({"ky_fazy": "kwitnienie:1.0"}, "ky_fazy"),
    ({"group_id": "nie_ma"}, "group_id"),
    ({"group_id": "zyto"}, "nie jest grupą"),
    ({"in_ranking": "moze"}, "in_ranking"),
    ({"wrazliwosc_na_susze": "duza"}, "wrazliwosc_na_susze"),
])
def test_validator_catches_errors(changes, fragment):
    errs = bad(**changes)
    assert any(fragment in e for e in errs), errs
