"""Fakty o działce na datę analizy – wspólne wejście dla oceny (scoring), przyczyn (causes) i reguł
rekomendacji (recommendations). Każdy fakt ma opis, jednostkę i źródło (do „Dlaczego?”).

Fakt = None oznacza brak danych – warunek reguły z takim faktem jest fałszywy (nie zgadujemy).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.analysis.crops import CROPS, Crop, no_irrigation_sentence
from app.analysis.field_state import FieldStateResult
from app.analysis.soil import SoilAssessment
from app.analysis.soil_label import SoilProfile
from app.analysis.water_balance import (
    RecentBalance,
    SeasonSums,
    SoilWaterResult,
    WaterBalanceResult,
    format_date_pl,
)
from app.schemas.analysis import Soil
from app.sources.soil_map import LIGHT

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}
OFF_SEASON_PHASES = {"przed_siewem", "po_zbiorze", "spoczynek_zimowy", "wschody_jesienne"}
IN_SEASON_PHASES = {"poczatkowa", "rozwoj", "pelnia", "dojrzewanie"}
CROP_OFF_PHASES = {"przed_siewem", "po_zbiorze"}  # A5e (D79): uprawy nie ma w polu – status = stan działki
CEREALS = {"zboza_ozime", "zboza_jare"}  # „zboże po zbożu” (D42)

# fakt -> (opis do „Dlaczego?”, jednostka, źródło)
FACT_META: dict[str, tuple[str, str | None, str]] = {
    "crop_label": ("Uprawa", None, "wybór rolnika"),
    "phase_label": ("Faza uprawy", None, "kalendarz upraw (FAO-56, PL)"),
    "month": ("Miesiąc analizy", None, "data analizy"),
    "soil_category": ("Kategoria podatności gleby na suszę", None, "IUNG-PIB"),
    "wod_mm": ("Woda dostępna dla roślin w glebie (WOD)", "mm", "IUNG-PIB"),
    "water_pct": ("Woda w glebie", "%", "Model wody w glebie FAO-56"),
    "water_mm": ("Woda w glebie", "mm", "Model wody w glebie FAO-56"),
    "water_rank_pct": ("Lata z mniejszym zapasem wody tego dnia", "%", "Model wody w glebie FAO-56"),
    "balance_mm": ("Bilans wody od początku sezonu (opad − parowanie)", "mm", "NASA POWER"),
    "balance_deviation_mm": ("Bilans wody względem średniej z 10 lat", "mm", "NASA POWER"),
    "balance_percentile": ("Lata z niższym bilansem wody", "%", "NASA POWER"),
    "precip_mm": ("Opad od początku sezonu", "mm", "NASA POWER"),
    "precip_mean_mm": ("Średni opad w tym okresie (10 lat)", "mm", "NASA POWER"),
    "precip_pct_of_mean": ("Opad względem średniej", "%", "NASA POWER"),
    "et0_mm": ("Parowanie (ET0) od początku sezonu", "mm", "NASA POWER, FAO-56"),
    "et0_mean_mm": ("Średnie parowanie w tym okresie (10 lat)", "mm", "NASA POWER, FAO-56"),
    "longest_dry_spell_days": ("Najdłuższy okres bez opadu w sezonie", "dni", "NASA POWER"),
    "days_to_stress": ("Dni do stresu wodnego roślin", "dni", "Model wody w glebie FAO-56"),
    "stress_days_season": ("Dni stresu wodnego w sezonie", "dni", "Model wody w glebie FAO-56"),
    "stress_days_mean": ("Średnia dni stresu (10 lat)", "dni", "Model wody w glebie FAO-56"),
    "irrigation_dose_mm": ("Dawka nawadniania", "mm", "Model wody w glebie FAO-56"),
    "irrigation_total_mm": ("Niedobór wody w 7 dniach", "mm", "Model wody w glebie FAO-56"),
    "etc_mm_day": ("Zużycie wody przez uprawę teraz", "mm/dzień", "FAO-56 (Kc × ET0)"),
    "risk": ("Ryzyko niedoboru wody w 7 dni", None, "Model wody w glebie FAO-56"),
    "previous_crop_label": ("Uprawa w poprzednim roku", None, "wybór rolnika"),
    "texture_label": ("Uziarnienie gleby", None, "Mapa glebowo-rolnicza / SoilGrids"),
    "sand_pct": ("Piasek w glebie (0–30 cm)", "%", "SoilGrids (ISRIC)"),
    "ksat_mm_h": ("Przepuszczalność gleby (Ksat)", "mm/h", "SoilGrids + Saxton i Rawls (2006)"),
    "rain_retention_label": ("Woda z ulewy", None, "SoilGrids + Saxton i Rawls (2006)"),
    "soil_complex_label": ("Kompleks przydatności rolniczej", None, "Mapa glebowo-rolnicza (GUGiK)"),
    "soil_txt": ("Gleba", None, "IUNG-PIB, mapa glebowo-rolnicza, SoilGrids"),
    "kbw30_mm": ("Bilans wody z ostatnich 30 dni (opad − parowanie)", "mm", "NASA POWER"),
    "kbw30_percentile": ("Lata z niższym bilansem wody w ostatnich 30 dniach", "%", "NASA POWER"),
    "et0_recent_mm_day": ("Parowanie (ET0) w ostatnich 7 dniach", "mm/dzień", "NASA POWER, FAO-56"),
    "season_deficit_mm": ("Niedobór wody uprawy w tym sezonie", "mm", "Model wody w glebie FAO-56"),
    # teren (A6, NMT GUGiK)
    "slope_max_pct": ("Największy spadek terenu", "%", "NMT GUGiK"),
    "steep_share_pct": ("Część działki o spadku > 5%", "%", "NMT GUGiK"),
    "wet_spot_area_m2": ("Zagłębienie bez odpływu w działce", "m²", "NMT GUGiK"),
    "outlet_share_pct": ("Część działki odprowadzana głównym odpływem", "%", "NMT GUGiK"),
    "inflow_ha": ("Powierzchnia, z której woda spływa na działkę", "ha", "NMT GUGiK"),
    "pond_catchment_ha": ("Zlewnia miejsca na oczko", "ha", "NMT GUGiK"),
    "terrain_relief_m": ("Różnica wysokości w działce", "m", "NMT GUGiK"),
}
OPTIONAL_IRRIGATION_NOTE = (" {crop} w Polsce nawadnia się rzadko – ma to sens tylko przy dostępnej wodzie i sprzęcie"
                            " (pozwolenie wodnoprawne).")
RAIN_LABEL = {"ucieka": "szybko wsiąka i ucieka w głąb", "zatrzymuje": "dobrze ją zatrzymuje",
              "splywa": "ryzyko spływu i zastoisk"}


@dataclass
class Facts:
    values: dict[str, Any]

    def get(self, key: str) -> Any:
        return self.values.get(key)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]


def _pct(lower: int | None, of: int | None) -> float | None:
    return None if lower is None or not of else round(100 * lower / of, 0)


def recent_facts(recent: RecentBalance | None) -> dict[str, Any]:
    v: dict[str, Any] = {
        "kbw30_mm": recent.balance_mm if recent else None,
        "kbw30_percentile": recent.percentile if recent else None,
        "kbw30_deviation_mm": recent.deviation_mm if recent else None,
        "kbw30_mean_mm": recent.mean_mm if recent else None,
        "kbw30_rank_lower": recent.lower_years if recent else None,
        "kbw30_rank_of": recent.of_years if recent else None,
    }
    dev30 = v["kbw30_deviation_mm"]
    v["kbw30_vs_mean_txt"] = (
        None if v["kbw30_mm"] is None else "brak porównania z ostatnimi latami" if dev30 is None else
        "tyle co zwykle" if abs(dev30) < 5 else f"o {abs(dev30):.0f} mm {'mniej' if dev30 < 0 else 'więcej'} niż zwykle"
    )
    return v


def field_facts(field: FieldStateResult, recent: RecentBalance | None) -> Facts:
    """Minimalne fakty do statusu „stan wody na działce” (field_state.status)."""
    return Facts({"has_crop": False, "water_pct": field.water_pct if field.status == "ok" else None,
                  "water_mm": field.water_mm, "water_rank_lower": field.rank_lower, "water_rank_of": field.rank_of,
                  **recent_facts(recent)})


def build_facts(
    crop: Crop | None,
    analysis_date: date,
    soil: SoilAssessment,
    model: SoilWaterResult | None,
    wb: WaterBalanceResult | None,
    sums: SeasonSums | None,
    soil_c: Soil | None = None,
    previous_crop: str | None = None,
    field: FieldStateResult | None = None,
    recent: RecentBalance | None = None,
    soil_profile: "SoilProfile | None" = None,
) -> Facts:
    """Fakty na datę analizy. `crop` = None – analiza bez uprawy: stan wody z modelu pokrycia referencyjnego
    (`field`), brak faktów zależnych od uprawy (faza, stres, nawadnianie)."""
    if crop is None:
        model = None
    phase = (model.phase if model else crop.day_info(analysis_date).phase) if crop else None
    v: dict[str, Any] = {
        "has_crop": crop is not None,
        "crop": crop.id if crop else None,
        "crop_label": crop.label if crop else None,
        "crop_kind": crop.kind if crop else None,
        "irrigation_practice": crop.irrigation_practice if crop else None,
        "month": analysis_date.month,
        "phase": phase,
        "phase_label": model.phase_label if model else None,
        "sensitive": bool(model and model.sensitive),
        "off_season": phase in OFF_SEASON_PHASES if crop else True,
        "season_complete": bool(model and model.season_complete),
        "non_agricultural": soil.not_agricultural,
        "soil_category": soil.dominant_mineral,
        "soil_category_roman": ROMAN.get(soil.dominant_mineral or 0),
        "wod_mm": soil.wod_mm,
        "agricultural_share_pct": None if soil.agricultural_share is None else round(100 * soil.agricultural_share),
        # stan wody (model)
        "water_pct": model.water_pct if model and model.status == "ok" else None,
        "water_mm": model.water_mm if model and model.status == "ok" else None,
        "water_scope": model.scope if model else None,
        "water_rank_pct": _pct(model.rank_lower, model.rank_of) if model else None,
        "water_rank_lower": model.rank_lower if model else None,
        "water_rank_of": model.rank_of if model else None,
        "days_to_stress": model.days_to_stress if model else None,
        "risk": model.risk if model else None,
        "stress_days_season": model.stress_days_season if model and model.status == "ok" else None,
        "stress_days_mean": model.mean_prev_stress_days if model else None,
        "kc": model.kc if model else None,
        "irrigation_status": model.irrigation.status if model and model.irrigation else None,
        "irrigation_message": model.irrigation.message if model and model.irrigation else None,
        "irrigation_dose_mm": model.irrigation.dose_mm if model and model.irrigation else None,
        "irrigation_total_mm": model.irrigation.total_7d_mm if model and model.irrigation else None,
        "irrigation_when": None,
        "season_deficit_mm": model.season_deficit_mm if model and model.status == "ok" else None,
        # bilans (historia)
        "balance_mm": wb.current_balance_mm if wb else None,
        "balance_mean_mm": wb.mean_balance_mm if wb else None,
        "balance_deviation_mm": wb.deviation_mm if wb else None,
        "balance_percentile": wb.percentile if wb else None,
        "longest_dry_spell_days": wb.longest_dry_spell_days if wb else None,
        "season_start_txt": format_date_pl(wb.season_start, with_year=False) if wb else None,
        # sumy sezonu
        "precip_mm": sums.precip_mm if sums else None,
        "precip_mean_mm": sums.precip_mean_mm if sums else None,
        "et0_mm": sums.et0_mm if sums else None,
        "et0_mean_mm": sums.et0_mean_mm if sums else None,
        # dane o terenie i wodach w okolicy – zadania A6/A7
        "terrain": None,
        "water_nearby": None,
    }
    if v["precip_mm"] is not None and v["precip_mean_mm"]:
        v["precip_pct_of_mean"] = round(100 * v["precip_mm"] / v["precip_mean_mm"])
        v["precip_deficit_mm"] = round(v["precip_mean_mm"] - v["precip_mm"], 1)
    else:
        v["precip_pct_of_mean"] = v["precip_deficit_mm"] = None
    if v["et0_mm"] is not None and v["et0_mean_mm"]:
        v["et0_excess_mm"] = round(v["et0_mm"] - v["et0_mean_mm"], 1)
    else:
        v["et0_excess_mm"] = None
    v["etc_mm_day"] = (
        round(v["kc"] * sums.et0_recent_mm_day, 1)
        if sums and sums.et0_recent_mm_day is not None and v["kc"] is not None and v["sensitive"]
        else None
    )
    sd, sm = v["stress_days_season"], v["stress_days_mean"]
    v["stress_ratio"] = round(sd / sm, 2) if sd is not None and sm else None
    if crop is None and field is not None and field.status == "ok":  # stan działki (pokrycie referencyjne)
        v.update(water_pct=field.water_pct, water_mm=field.water_mm, water_scope="profil",
                 water_rank_pct=_pct(field.rank_lower, field.rank_of), water_rank_lower=field.rank_lower,
                 water_rank_of=field.rank_of)
    v["water_description"] = (model.description if model and model.status == "ok" else
                              field.description if crop is None and field and field.status == "ok" else None)
    v.update(recent_facts(recent))  # bilans z ostatnich 30 dni (status poza sezonem i bez uprawy)
    v["et0_recent_mm_day"] = sums.et0_recent_mm_day if sums else None
    v["horizon_kind"] = model.horizon_kind if model else None
    v["in_season"] = phase in IN_SEASON_PHASES
    # silny stres wodny (D42): Dr > RAW w fazie wrażliwej (stres już jest) albo wysokie ryzyko w 7 dni
    v["strong_stress"] = bool(v["sensitive"] and (v["days_to_stress"] == 0 or v["risk"] == "wysokie"))
    # stres wodny w ciągu 7 dni w fazie wrażliwej – tam, gdzie inne uprawy dostałyby plan nawadniania (D48)
    d2s = v["days_to_stress"]
    v["water_stress_7d"] = bool(v["sensitive"] and d2s is not None and d2s <= 7)
    v["stress_when_txt"] = ("" if d2s is None else " – rośliny już odczuwają brak wody" if d2s == 0 else
                            f" – rośliny odczują brak wody za ok. {d2s} dni")
    v["no_irrigation_txt"] = no_irrigation_sentence(crop) if crop else None
    v["irrigation_practice_note"] = (OPTIONAL_IRRIGATION_NOTE.format(crop=crop.label) if crop and
                                     crop.irrigation_practice == "optional" else "")
    dev = v["balance_deviation_mm"]
    v["balance_vs_mean_txt"] = (
        None if v["balance_mm"] is None else "brak porównania z ostatnimi latami" if dev is None else
        "tyle co zwykle" if abs(dev) < 5 else f"o {abs(dev):.0f} mm {'mniej' if dev < 0 else 'więcej'} niż zwykle"
    )
    # płodozmian
    prev = previous_crop if previous_crop in CROPS else None
    v["previous_crop"] = prev
    v["crop_label_lower"] = crop.label.lower() if crop else None
    v["previous_crop_label"] = CROPS[prev].label.lower() if prev else None
    if crop is None:
        prev = None
    v["same_crop"] = None if prev is None else (prev == crop.id or (prev.startswith("rzepak") and crop.id.startswith("rzepak")))
    v["cereal_after_cereal"] = None if prev is None else (prev in CEREALS and crop.id in CEREALS)
    v["rotation_issue"] = (
        None if prev is None else
        "ta sama uprawa drugi rok z rzędu" if v["same_crop"] else
        "zboże po zbożu" if v["cereal_after_cereal"] else None
    )
    # gleba dla rolnika (SoilGrids, mapa glebowo-rolnicza)
    tex = soil_c.texture if soil_c else None
    perm = soil_c.permeability if soil_c else None
    smap = soil_c.soil_map if soil_c else None
    v["sand_pct"] = tex.sand_pct if tex else None
    v["ksat_mm_h"] = perm.ksat_mm_h if perm else None
    v["rain_retention"] = perm.rain_retention if perm else None
    v["rain_retention_label"] = RAIN_LABEL.get(perm.rain_retention) if perm else None
    v["soil_species"] = smap.species_code if smap else None
    v["soil_complex_label"] = smap.complex_label if smap else None
    v["texture_label"] = (smap.species_label if smap and smap.species_label else tex.texture_class if tex else None)
    sandy_map = bool(smap and smap.species_code in LIGHT)
    sandy_sg = bool(tex and tex.texture_code in ("sand", "loamy_sand"))
    parts = ([f"kat. {v['soil_category_roman']}"] if v["soil_category_roman"] else []) + (
        [v["texture_label"]] if v["texture_label"] else [])
    v["soil_txt"] = ", ".join(parts) or None
    v["light_soil"] = None if (tex is None and smap is None and v["soil_category"] is None) else bool(
        sandy_map or sandy_sg or (v["soil_category"] is not None and v["soil_category"] <= 2)
    )
    if soil_profile is not None and soil_profile.group != "nieznana":
        # A5b-2b (D66): etykieta ważona udziałem gatunków (mapa glebowo-rolnicza) – nie jeden punkt / jedno źródło
        v["light_soil"] = soil_profile.group == "lekka"
        v["soil_txt"] = soil_profile.text
        v["soil_group"] = soil_profile.group
    v["irrigation_confidence"] = "srednia" if v["horizon_kind"] == "prognoza" else "ograniczona"
    if model and model.irrigation and model.irrigation.first_date:
        fd = model.irrigation.first_date
        v["irrigation_when"] = "teraz" if fd == analysis_date else f"ok. {fd:%d.%m}"
    return Facts(v)
