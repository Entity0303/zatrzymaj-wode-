"""Fakty o działce na datę analizy – wspólne wejście dla oceny (scoring), przyczyn (causes) i reguł
rekomendacji (recommendations). Każdy fakt ma opis, jednostkę i źródło (do „Dlaczego?”).

Fakt = None oznacza brak danych – warunek reguły z takim faktem jest fałszywy (nie zgadujemy).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.analysis.crops import CROPS, Crop
from app.analysis.soil import SoilAssessment
from app.analysis.water_balance import SeasonSums, SoilWaterResult, WaterBalanceResult, format_date_pl
from app.schemas.analysis import Soil
from app.sources.soil_map import SANDY

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}
OFF_SEASON_PHASES = {"przed_siewem", "po_zbiorze", "spoczynek_zimowy", "wschody_jesienne"}
IN_SEASON_PHASES = {"poczatkowa", "rozwoj", "pelnia", "dojrzewanie"}
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
}
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


def build_facts(
    crop: Crop,
    analysis_date: date,
    soil: SoilAssessment,
    model: SoilWaterResult | None,
    wb: WaterBalanceResult | None,
    sums: SeasonSums | None,
    soil_c: Soil | None = None,
    previous_crop: str | None = None,
) -> Facts:
    phase = model.phase if model else crop.day_info(analysis_date).phase
    v: dict[str, Any] = {
        "crop": crop.id,
        "crop_label": crop.label,
        "crop_kind": crop.kind,
        "month": analysis_date.month,
        "phase": phase,
        "phase_label": model.phase_label if model else None,
        "sensitive": bool(model and model.sensitive),
        "off_season": phase in OFF_SEASON_PHASES,
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
    v["horizon_kind"] = model.horizon_kind if model else None
    v["in_season"] = phase in IN_SEASON_PHASES
    # silny stres wodny (D42): Dr > RAW w fazie wrażliwej (stres już jest) albo wysokie ryzyko w 7 dni
    v["strong_stress"] = bool(v["sensitive"] and (v["days_to_stress"] == 0 or v["risk"] == "wysokie"))
    dev = v["balance_deviation_mm"]
    v["balance_vs_mean_txt"] = (
        None if v["balance_mm"] is None else "brak porównania z ostatnimi latami" if dev is None else
        "tyle co zwykle" if abs(dev) < 5 else f"o {abs(dev):.0f} mm {'mniej' if dev < 0 else 'więcej'} niż zwykle"
    )
    # płodozmian
    prev = previous_crop if previous_crop in CROPS else None
    v["previous_crop"] = prev
    v["crop_label_lower"] = crop.label.lower()
    v["previous_crop_label"] = CROPS[prev].label.lower() if prev else None
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
    sandy_map = bool(smap and smap.species_code in SANDY)
    sandy_sg = bool(tex and tex.texture_code in ("sand", "loamy_sand"))
    parts = ([f"kat. {v['soil_category_roman']}"] if v["soil_category_roman"] else []) + (
        [v["texture_label"]] if v["texture_label"] else [])
    v["soil_txt"] = ", ".join(parts) or None
    v["light_soil"] = None if (tex is None and smap is None and v["soil_category"] is None) else bool(
        sandy_map or sandy_sg or (v["soil_category"] is not None and v["soil_category"] <= 2)
    )
    v["irrigation_confidence"] = "srednia" if v["horizon_kind"] == "prognoza" else "ograniczona"
    if model and model.irrigation and model.irrigation.first_date:
        fd = model.irrigation.first_date
        v["irrigation_when"] = "teraz" if fd == analysis_date else f"ok. {fd:%d.%m}"
    return Facts(v)
