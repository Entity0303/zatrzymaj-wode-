"""A15 – poprawki z weryfikacji V1: nagłówek „Trudna”, zboża na dobrej glebie, kompleksy górskie, satelita słowami."""

from datetime import date

from app.analysis import satellite as SM
from app.analysis import suggestions as S
from app.analysis import verdict as V
from app.analysis.crops import ALL_CROPS as CROPS


def _headline(lv):
    return next(h["text"] for h in V.cfg()["headlines"] if V._match(h["if"], lv, 0.0, 0.0))


def test_trudna_only_with_bad_crops_or_weaker_soil():
    good_soil = {"gleba": "ok", "opady": "bad", "teren": "ok", "uprawy": "warn"}  # Stryjno, Szczytno 126/3
    assert not _headline(good_soil).startswith("Trudna")
    assert _headline({**good_soil, "uprawy": "bad"}).startswith("Trudna")
    assert _headline({**good_soil, "gleba": "warn"}).startswith("Trudna")


def test_mountain_complexes_suit_cereals_and_potato():
    for crop in ("pszenica_ozima", "owies", "jeczmien_jary", "ziemniak"):
        assert S.soil_suitability(CROPS[crop], 3, "11") == "odpowiednia"
        assert S.soil_suitability(CROPS[crop], 3, "10") == "odpowiednia"
    assert S.soil_suitability(CROPS["zyto"], 3, "11") == "odpowiednia"


def test_cereal_on_good_soil_never_unsuitable_reason_names_complex():
    crop = CROPS["pszenica_ozima"]
    rot = S.rotation(crop, [])
    txt = S.reason(crop, "mozliwe", "neutralna", 1, 10, 3.0, 2.5, 2018, 15, rot, False, "pył zwykły 89%",
                   complex_code="5", category_iung=3, cereal_override=True)
    assert "kompleks „żytni dobry”" in txt and "lepiej opłaca się żyto lub pszenżyto" in txt and "nie pasuje" not in txt
    beet = CROPS["burak_cukrowy"]
    txt2 = S.reason(beet, "odradzane", "nieodpowiednia", 1, 10, 40.0, 30.0, 2018, 20, S.rotation(beet, []), False,
                    "pył zwykły 89%", complex_code="5", category_iung=3)
    assert txt2.startswith("Mapa glebowo-rolnicza podaje tu kompleks „żytni dobry”") and "IUNG ocenia glebę lepiej" in txt2


def test_satellite_words_and_no_image_ttl():
    assert SM.NO_IMAGE_TTL_S == 12 * 3600 and SM.FAIL_TTL_S == 1800
    assert SM.plant_words(0.86, -0.24, date(2026, 11, 16)) == ("gęsta zieleń", "poza sezonem")
    assert SM.plant_words(0.8, -0.3, date(2026, 6, 16)) == ("gęsta zieleń", "niska")
    assert SM.plant_words(0.2, None, date(2026, 6, 16))[0] == "goła ziemia"
    assert SM.plant_words(None, None, None) == (None, None)


def test_limitation_plain_language():
    import inspect

    src = inspect.getsource(S)
    assert "reakcja plonu na brak wody (metoda FAO)" in src and "FAO-33, współczynnik Ky" not in src  # A20
