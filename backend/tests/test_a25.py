"""A25: interpretacja zdjęcia satelitarnego zależna od uprawy i pory roku (KOWR 3.2) – tabela rules/satellite.yaml."""
import re
from datetime import date

from app.analysis import satellite as SAT
from app.routers.analysis import _sat_indicator
from app.schemas.analysis import Satellite, SourceTag

TAG = SourceTag(kind="pomiar", date=date(2026, 11, 16), source="Sentinel-2 L2A")
NO_SAT = SourceTag(kind="brak_danych", source="Sentinel-2 L2A")


def sat(ndvi, ndmi=0.1, on=date(2026, 11, 16), trend="podobnie", level="info"):
    d = SAT.describe(ndvi, ndmi, None if trend is None else ndvi, on)
    return Satellite(status="ok", date=on, ndvi=ndvi, ndmi=ndmi, ndvi_class=d["ndvi_class"], ndvi_label=d["ndvi_label"],
                     ndmi_class=d["ndmi_class"], ndmi_label=d["ndmi_label"], trend=trend, level=level,
                     sentence=d["sentence"], note=SAT.NOTE, source_tag=TAG)


def test_table_covers_groups_and_months():
    c = SAT.cfg()
    assert {"zboza_ozime", "rzepak_ozimy", "zboza_jare", "kukurydza", "ziemniak", "burak", "uzytki_zielone"} <= set(c["crop_ndvi"])
    for group, months in c["crop_ndvi"].items():
        assert sorted(months) == list(range(1, 13)), group
        for lo, hi, phase in months.values():
            assert 0 <= lo < hi <= 1 and phase
    assert set(c["crop_groups"].values()) <= set(c["crop_ndvi"])


def test_winter_wheat_november_dense_green_is_above_typical():
    a = SAT.crop_assessment("pszenica_ozima", 0.86, 0.1, date(2026, 11, 16))
    assert a["rating"] == "wyzej" and (a["lo"], a["hi"]) == (0.30, 0.70) and "po wschodach" in a["phase"]
    s = SAT.for_crop(sat(0.86), "pszenica_ozima")
    assert "Pszenica ozima w listopadzie: po wschodach" in s.sentence and "więcej niż typowo" in s.sentence
    assert "Zieleń podobna jak rok temu" in s.sentence and s.level == "ok"
    # tryb Rolnik: w zdaniu nie ma liczby NDVI (jedyne cyfry to data zdjęcia); liczby – w nocie dla Doradcy
    assert not re.search(r"\d", s.sentence.replace("16.11.2026", ""))
    assert "0,30–0,70" in s.note and "0,86" in s.note


def test_weak_canopy_in_season_warns_and_bare_field_does_not():
    s = SAT.for_crop(sat(0.30, on=date(2026, 5, 20), level="ok"), "zboza_ozime")  # maj: typowo 0,65–0,90
    assert "mniej niż typowo" in s.sentence and "sprawdź na polu" in s.sentence and s.level == "warn"
    k = SAT.for_crop(sat(0.15, on=date(2026, 11, 16)), "kukurydza_ziarno")  # po zbiorze goła ziemia jest w normie
    assert "po zbiorze" in k.sentence and "tyle, ile typowo" in k.sentence and k.level == "info"


def test_same_image_different_crop_gives_different_reading():
    img = sat(0.45, on=date(2026, 6, 15), level="ok")
    assert SAT.crop_assessment("zboza_jare", 0.45, 0.1, img.date)["rating"] == "slabiej"   # czerwiec: pełnia
    assert SAT.crop_assessment("kukurydza_ziarno", 0.45, 0.1, img.date)["rating"] == "norma"  # czerwiec: szybki wzrost
    assert SAT.for_crop(img, "zboza_jare").sentence != SAT.for_crop(img, "kukurydza_ziarno").sentence


def test_no_crop_keeps_general_sentence_with_hint_and_unknown_crop_is_unchanged():
    base = sat(0.6)
    s = SAT.for_crop(base, None)
    assert s.sentence.startswith(base.sentence) and s.sentence.endswith("Wybierz uprawę, żeby porównać z typowym rozwojem.")
    assert SAT.for_crop(s, None).sentence == s.sentence  # bez dopisywania drugi raz
    assert SAT.for_crop(base, "drzewa_owocowe").sentence == base.sentence  # uprawa spoza tabeli
    assert base.sentence.count("Wybierz uprawę") == 0  # kopia – wynik w pamięci bez zmian


def test_plant_moisture_only_for_dense_canopy_of_the_crop():
    thin = sat(0.35, ndmi=-0.2, on=date(2026, 6, 15), level="ok")
    ind = _sat_indicator(thin, "ndmi", NO_SAT, "kukurydza_ziarno")
    assert ind.label == "poza sezonem albo za rzadki łan – nie oceniamy" and ind.index_value == -0.2
    dense = SAT.for_crop(sat(0.80, ndmi=-0.2, on=date(2026, 7, 15), level="ok"), "kukurydza_ziarno")
    assert dense.ndmi_class == "sucho" and "mało wody w liściach" in dense.sentence and dense.level == "warn"
    rape = SAT.for_crop(sat(0.75, ndmi=-0.3, on=date(2026, 11, 5)), "rzepak")  # listopad – poza sezonem, bez alarmu
    assert rape.ndmi_class is None and "mało wody w liściach" not in rape.sentence and rape.level == "ok"
    late = _sat_indicator(sat(0.75, ndmi=-0.3, on=date(2026, 11, 5)), "ndmi", NO_SAT, "rzepak")
    assert late.label == "poza sezonem albo za rzadki łan – nie oceniamy"
    health = _sat_indicator(sat(0.86), "ndvi", NO_SAT, "pszenica_ozima")
    assert health.label == "gęsta zieleń – wyżej niż typowo" and "po wschodach" in health.note
    assert _sat_indicator(sat(0.86), "ndvi", NO_SAT).label == "gęsta zieleń"  # bez uprawy jak dotąd
