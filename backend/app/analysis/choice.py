"""„Co planuję posiać” (A5e, D77): ocena wyboru rolnika na tej działce + lepsze możliwości + czego nie siać.

Wejście = gotowy ranking (`suggestions.build`) – tu nic się nie symuluje, tylko dobiera i opisuje. Szablony zdań i
progi: rules/choice.yaml; formy wyrazów (dopełniacz, biernik): rules/verdict.yaml. Te same dane → te same zdania.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.analysis import verdict as verdict_mod
from app.analysis.crops import ALL_CROPS, RANKING_CROPS
from app.analysis.suggestions import HISTORY_UNKNOWN, _ago, _same, _years
from app.schemas.analysis import (
    AlternativeItem,
    ChoiceItem,
    CropSuggestion,
    CropSuggestions,
    NotRecommendedItem,
    PerennialSuggestion,
    RotationCheck,
)

RULES = Path(__file__).parent / "rules" / "choice.yaml"
RANKING_IDS = [c.id for c in RANKING_CROPS]
CATEGORY_ORDER = {"polecane": 0, "mozliwe": 1, "odradzane": 2}


@lru_cache
def cfg() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["choice"]


def parse_planned(value: str | list[str] | None) -> list[str]:
    """'pszenica_ozima,rzepak' albo lista → 1–3 identyfikatory upraw z rankingu (bez powtórzeń). Nieznany → ValueError."""
    if value is None:
        return []
    items = value.split(",") if isinstance(value, str) else list(value)
    out: list[str] = []
    for x in (i.strip() for i in items):
        if not x:
            continue
        if x not in RANKING_IDS:
            raise ValueError(x)
        if x not in out:
            out.append(x)
    if len(out) > cfg()["max_planned"]:
        raise ValueError(f"najwyżej {cfg()['max_planned']} uprawy")
    return out


def _gen(crop_id: str) -> str:
    return verdict_mod.cfg()["genitive"].get(crop_id) or ALL_CROPS[crop_id].label.lower()


def _n(v: float | None) -> str:
    return "–" if v is None else f"{v:.1f}".replace(".", ",")


def _prev(history: list[str]) -> str | None:
    return history[0] if history and history[0] != HISTORY_UNKNOWN and history[0] in ALL_CROPS else None


def why_choice(item: CropSuggestion, history: list[str], light: bool) -> str:
    w = cfg()["why"]
    crop = ALL_CROPS[item.crop_id]
    prev = _prev(history)
    if item.rotation.status == "naruszenie":
        return w["rotation_violation"]
    if item.soil_suitability == "nieodpowiednia":
        return w["soil_bad_light"] if light else w["soil_bad"]
    if item.category == "odradzane":
        return w["drought_bad_sensitive"] if crop.sensitivity == "wysoka" else w["drought_bad"]
    if item.rotation.status == "plus" and prev:
        return w["rotation_plus"].format(prev_gen=_gen(prev))
    if item.rotation.status == "ostrzezenie" and prev:
        return w["rotation_warn"].format(prev_nom=ALL_CROPS[prev].label.lower())
    if item.category == "polecane":
        return w["ok_tolerant"] if crop.sensitivity == "niska" else w["ok_soil"]
    if item.soil_suitability == "odpowiednia":
        return w["possible_soil"]
    return w["neutral"]


def _choice_from_field(item: CropSuggestion, history: list[str], light: bool) -> ChoiceItem:
    return ChoiceItem(
        crop_id=item.crop_id, label=item.label, category=item.category, category_label=item.category_label,
        yield_typical_t_ha=item.yield_typical_t_ha, total_typical_t=item.total_typical_t,
        yield_weak_t_ha=item.yield_weak_t_ha, total_weak_t=item.total_weak_t, weak_year=item.weak_year,
        drought_risk_years=item.drought_risk_years, years_simulated=item.years_simulated, rotation=item.rotation,
        why=why_choice(item, history, light), confidence=item.confidence)


def _choice_from_perennial(item: PerennialSuggestion, rotation: RotationCheck) -> ChoiceItem:
    return ChoiceItem(
        crop_id=item.crop_id, label=item.label, category=None, category_label=None, perennial=True,
        yield_typical_t_ha=item.yield_typical_t_ha, total_typical_t=item.total_typical_t,
        yield_weak_t_ha=item.yield_weak_t_ha, total_weak_t=item.total_weak_t, weak_year=item.weak_year,
        drought_risk_years=item.drought_risk_years, years_simulated=item.years_simulated, rotation=rotation,
        why=cfg()["why"]["perennial"], confidence="ograniczona")


def why_alternative(alt: CropSuggestion, ref: CropSuggestion | None, history: list[str]) -> str:
    a = cfg()["alternative_why"]
    prev = _prev(history)
    if alt.rotation.status == "plus" and prev:
        txt = a["rotation_plus"].format(prev_gen=_gen(prev), crop_nom=alt.label.lower())
        return txt[:1].upper() + txt[1:]
    if ref is not None:
        if alt.drought_risk_years < ref.drought_risk_years:
            return a["less_drought"].format(risk=alt.drought_risk_years, n=alt.years_simulated,
                                            ref_risk=ref.drought_risk_years, ref_gen=_gen(ref.crop_id))
        if (alt.yield_typical_t_ha and ref.yield_typical_t_ha and alt.group_id == ref.group_id
                and alt.yield_typical_t_ha > ref.yield_typical_t_ha):
            return a["more_yield"].format(yield_t=_n(alt.yield_typical_t_ha), ref_yield=_n(ref.yield_typical_t_ha),
                                          ref_gen=_gen(ref.crop_id))
    return a["soil_good"]


def not_recommended_reason(item: CropSuggestion, history: list[str], light: bool) -> str:
    r = cfg()["not_recommended"]
    crop = ALL_CROPS[item.crop_id]
    if item.rotation.status == "naruszenie":
        k = next((k + 1 for k, h in enumerate(history) if h != HISTORY_UNKNOWN and _same(h, crop.id)), None)
        if k is not None:
            return r["rotation"].format(ago=_ago(k), years=_years(crop.min_break_years))
    if item.soil_suitability == "nieodpowiednia":
        return r["soil_light"] if light else r["soil"]
    return r["drought"].format(risk=item.drought_risk_years, n=item.years_simulated)


def attach(sug: CropSuggestions | None, planned: list[str], light: bool) -> CropSuggestions | None:
    """Dokłada do rankingu: choice (wybór rolnika), choice_summary, alternatives, not_recommended, top_ids."""
    if sug is None:
        return None
    c = cfg()
    history = list(sug.crop_history)
    field = [i for g in sug.groups if g.key == "polowe" for i in g.items]
    by_id = {i.crop_id: i for i in field}
    per = {p.crop_id: p for p in (sug.perennials.items if sug.perennials else [])}
    popular = {k: n for n, k in enumerate(verdict_mod.cfg()["popular"])}

    choice: list[ChoiceItem] = []
    for cid in planned:
        if cid in by_id:
            choice.append(_choice_from_field(by_id[cid], history, light))
        elif cid in per:
            from app.analysis.suggestions import rotation as rotation_check

            choice.append(_choice_from_perennial(per[cid], rotation_check(ALL_CROPS[cid], history)))

    chosen_field = [by_id[cid] for cid in planned if cid in by_id]
    ref = max(chosen_field, key=lambda i: i.score, default=None)
    alternatives: list[AlternativeItem] = []
    if planned:
        pool = [i for i in field if i.crop_id not in planned and i.category != "odradzane"
                and i.rotation.status != "naruszenie"]
        pool.sort(key=lambda i: (CATEGORY_ORDER[i.category], -i.score))
        for i in pool:
            if ref is None:
                rel = "lepsza"
            elif i.score - ref.score >= c["better_margin"] or CATEGORY_ORDER[i.category] < CATEGORY_ORDER[ref.category]:
                rel = "lepsza"
            elif i.score >= ref.score - c["similar_margin"] and CATEGORY_ORDER[i.category] <= CATEGORY_ORDER[ref.category]:
                rel = "podobna"
            else:
                continue
            alternatives.append(AlternativeItem(
                crop_id=i.crop_id, label=i.label, category=i.category, category_label=i.category_label, relation=rel,
                yield_typical_t_ha=i.yield_typical_t_ha, total_typical_t=i.total_typical_t,
                drought_risk_years=i.drought_risk_years, years_simulated=i.years_simulated,
                why=why_alternative(i, ref, history)))
            if len(alternatives) >= c["max_alternatives"]:
                break

    bad = sorted((i for i in field if i.category == "odradzane" and i.crop_id not in planned),
                 key=lambda i: popular.get(i.crop_id, 99))
    not_recommended = [NotRecommendedItem(crop_id=i.crop_id, label=i.label,
                                          reason=not_recommended_reason(i, history, light))
                       for i in bad[: c["not_recommended_max"]]]
    top_ids = [i.crop_id for i in field if i.category != "odradzane"][: c["top_n"]]

    summary = None
    if planned:
        s = c["summary"]
        cats = [x.category for x in choice if x.category is not None]
        if not cats:
            summary = s["perennial_only"] if choice else None
        elif all(x == "odradzane" for x in cats):
            summary = s["all_bad"]
        elif "odradzane" in cats:
            summary = s["some_bad"].format(bad=", ".join(x.label.lower() for x in choice if x.category == "odradzane"))
        else:
            better = any(a.relation == "lepsza" for a in alternatives)
            best = min(cats, key=CATEGORY_ORDER.get)
            summary = (s["good_but_better"] if better else s["good"]) if best == "polecane" else \
                (s["possible_but_better"] if better else s["possible"])

    return sug.model_copy(update={"choice": choice, "choice_summary": summary, "alternatives": alternatives,
                                  "not_recommended": not_recommended, "top_ids": top_ids})
