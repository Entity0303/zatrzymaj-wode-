"""A18: teksty dla rolnika z audytu V3 – odmiana, kwoty, teren bez udziału w przyczynach, opady bez sprzeczności,
oczko bez tautologii, źródło opadu z faktycznej serii, komunikaty bez nazw technicznych."""

from datetime import datetime, timezone

from app.analysis import causes, facts as F, verdict
from app.analysis.facts import Facts
from app.analysis.terrain_interpret import rule_facts
from app.core.cache import StaleHit
from app.core.format import days, plural, zl


def test_plural_and_money():
    assert [days(n) for n in (1, 2, 5, 12, 22, 25)] == ["1 dzień", "2 dni", "5 dni", "12 dni", "22 dni", "25 dni"]
    assert plural(3, "zdjęcie", "zdjęcia", "zdjęć") == "zdjęcia" and plural(14, "zdjęcie", "zdjęcia", "zdjęć") == "zdjęć"
    nb = " "  # spacja nierozdzielająca (D98) – kwota nie łamie się w tekście
    assert zl(2100) == f"2{nb}100 zł" and zl(28500) == f"28{nb}500 zł" and zl(800) == "800 zł"


def test_terrain_cause_is_informative_only():
    f = Facts({"precip_mm": 300.0, "precip_mean_mm": 400.0, "soil_category": 2, "soil_category_roman": "II",
               "wod_mm": 148.7, "terrain_runoff_pct": 60, "terrain_wet_pct": 20, "season_start_txt": "1 marca",
               "precip_source": "stacje IMGW-PIB"})
    cs = causes.build_causes(f)
    t = next(c for c in cs if c.factor == "teren")
    assert t.share == 0 and "informacyjnie" in t.description and t.source_tag.kind != "pomiar"
    assert abs(sum(c.share for c in cs) - 1.0) < 1e-6 and cs[-1].factor == "teren"
    assert next(c for c in cs if c.factor == "opady").source_tag.source == "stacje IMGW-PIB"
    assert next(c for c in cs if c.factor == "gleba").source_tag.kind == "obliczenia"


def test_weather_sources_split():
    assert F.weather_sources("IMGW-PIB (opad) + NASA POWER (parowanie)") == ("stacje IMGW-PIB", "NASA POWER, FAO-56")
    assert F.weather_sources("NASA POWER") == ("NASA POWER", "NASA POWER, FAO-56")
    f = Facts({"precip_source": "stacje IMGW-PIB", "et0_source": "NASA POWER, FAO-56"})
    assert F.fact_source("precip_mm", f) == "stacje IMGW-PIB" and F.fact_source("et0_mm", f) == "NASA POWER, FAO-56"
    assert "IMGW" in F.fact_source("balance_mm", f) and F.fact_source("wod_mm", f) == "IUNG-PIB"


def test_precip_dry_spring_does_not_say_same_as_average():
    st = {"year_mm": 600, "season_mm": 360, "deficit_years": 7, "years": 10, "first": 2016, "last": 2025}
    s = verdict.precip_statement(st, measured=True)
    assert s.level == "bad" and "To tyle, co średnio" not in s.text and "ale w maju–czerwcu to za mało" in s.text
    ok = verdict.precip_statement({**st, "deficit_years": 0, "year_mm": 650}, measured=True)
    assert "ani razu" in ok.text and "w 0 z" not in ok.text


def _pond(kind: str, area: float) -> dict:
    return {"parcel_area_ha": 3.0, "outlets": [], "proposals": [
        {"type": kind, "catchment_m2": 20_000.0, "max_depth_m": 0.1, "suggested_pond_area_m2": area,
         "inflow_runoff_m3": 120.0}]}


def test_pond_texts_without_tautology_and_size_word():
    dep = rule_facts(_pond("oczko_w_zaglebieniu", 300.0), 3)
    assert dep["terrain_pond"] == "opcja" and dep["pond_noun"] == "małe oczko"
    assert "płytkiego zagłębienia" in dep["pond_lead_txt"] and "nie ma zagłębienia" not in dep["pond_lead_txt"]
    assert dep["pond_place_txt"] == "w zagłębieniu bez odpływu"
    out = rule_facts(_pond("oczko_przy_odplywie", 1270.0), 3)
    assert out["pond_noun"] == "oczko" and out["pond_noun_cap"] == "Oczko"
    assert out["pond_lead_txt"].startswith("Na działce nie ma zagłębienia bez odpływu") and "gdzie wypływa" in out["pond_lead_txt"]


def test_stale_text_says_what_happened_and_what_to_do():
    from app.analysis.confidence import stale_text

    t = stale_text(StaleHit("NASA POWER", datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc), "błąd"))
    assert "cache" not in t and "chwilowo nie odpowiada" in t and "Spróbuj za chwilę" in t


def test_verdict_note_short():
    assert verdict.NOTE == "Zdania liczy program z danych tej działki według stałych reguł. Te same dane dają te same zdania."
