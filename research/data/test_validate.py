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
    # Ky żyta niższe niż pszenicy – kalibracja GUS (C3) celowo NIE podniosła go, bo GUS miesza
    # gatunek z glebą, a backend liczy glebę osobno (WOD)
    assert float(by["zyto"]["ky_total"]) < float(by["pszenica_ozima"]["ky_total"])
    assert float(by["pszenzyto_ozime"]["ky_total"]) < float(by["pszenica_ozima"]["ky_total"])


def test_ky_after_gus_calibration():
    by = {r["crop_id"]: r for r in CROPS}
    expected = {"zyto": 0.80, "pszenzyto_ozime": 0.90,  # cofnięte – bez zmian w C3
                "jeczmien_ozimy": 1.00, "owies": 1.10,
                "rzepak": 0.95, "kukurydza_kiszonka": 1.10,
                # zweryfikowane w FAO-33 – bez zmian
                "pszenica_ozima": 1.00, "kukurydza_ziarno": 1.25, "ziemniak": 1.10,
                "burak_cukrowy": 0.90, "straczkowe": 1.15}
    for cid, ky in expected.items():
        assert float(by[cid]["ky_total"]) == pytest.approx(ky), cid
    for cid in ("jeczmien_ozimy", "owies", "rzepak", "kukurydza_kiszonka"):
        assert "KY ZMIENIONE (C3" in by[cid]["zrodla"], cid
    for cid in ("zyto", "pszenzyto_ozime"):
        assert "KY ZMIENIONE (C3" not in by[cid]["zrodla"], cid
        assert "NIE zmieniane w C3" in by[cid]["zrodla"], cid
    # owies nadal wśród najbardziej wrażliwych zbóż (ex aequo z jęczmieniem jarym)
    cereals = ["pszenica_ozima", "zyto", "pszenzyto_ozime", "jeczmien_ozimy", "jeczmien_jary", "owies"]
    assert float(by["owies"]["ky_total"]) == max(float(by[c]["ky_total"]) for c in cereals)


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


# Backend (A5b-2a, D60) czyta konfigurację upraw z backend/app/data/crops/crops.csv – kopii naszego
# research/data/crops.csv z dodatkowymi kolumnami backendu (np. root_depth_m, typ).
BACKEND_CSV = REPO / "backend" / "app" / "data" / "crops" / "crops.csv"
SHARED = ["name_pl", "backend_id", "group_id", "in_ranking", "iung_name", "kc_ini", "kc_mid", "kc_end",
          "typowy_siew", "typowy_zbior", "ozima", "ky_total", "irrigation_practice", "min_przerwa_lat",
          "zle_przedplony", "dobre_przedplony", "gleby_odpowiednie", "gleby_nieodpowiednie"]
# celowe różnice kopii backendu (decyzje zespołu) – (crop_id, kolumna): uzasadnienie
KNOWN_DIFF = {("ziemniak", "irrigation_practice"): "D60: decyzja Dominika (A5b-1) optional → common"}


def _backend_rows():
    if not BACKEND_CSV.exists():
        pytest.skip("brak backend/app/data/crops/crops.csv na tej gałęzi")
    return {r["crop_id"]: r for r in V.read_csv(BACKEND_CSV)}


def test_backend_ids_exist_in_backend_config():
    backend = _backend_rows()
    backend_ids = {cid for cid, r in backend.items() if r["backend_id"]}
    for r in CROPS:
        if r["backend_id"]:
            assert r["backend_id"] in backend_ids, r["backend_id"]
    assert set(backend) == {r["crop_id"] for r in CROPS}


def test_kc_matches_backend():
    backend = _backend_rows()
    for r in CROPS:
        b = backend[r["crop_id"]]
        for k in ("kc_ini", "kc_mid", "kc_end"):
            assert float(r[k]) == float(b[k]), (r["crop_id"], k)


@pytest.mark.parametrize("col", SHARED)
def test_shared_columns_match_backend_copy(col):
    """Kopia w backendzie nie może się rozjechać z research/data/crops.csv we wspólnych kolumnach."""
    backend = _backend_rows()
    if col not in next(iter(backend.values())):
        pytest.skip(f"backend nie ma kolumny {col}")
    diff = [r["crop_id"] for r in CROPS if r[col].strip() != backend[r["crop_id"]][col].strip()
            and not _num_equal(r[col], backend[r["crop_id"]][col]) and (r["crop_id"], col) not in KNOWN_DIFF]
    assert diff == [], f"{col}: różnice w {diff}"


def _num_equal(a, b):
    try:
        return float(a) == float(b)
    except ValueError:
        return False


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
