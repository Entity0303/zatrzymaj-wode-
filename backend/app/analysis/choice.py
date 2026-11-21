"""„Co planuję posiać” (A5e, D77; A5e-2, D80): ocena wyboru rolnika na tej działce + lepsze możliwości + czego nie siać.

Wejście = gotowy ranking (`suggestions.build`) – tu nic się nie symuluje, tylko dobiera i opisuje. Szablony zdań i
progi: rules/choice.yaml; formy wyrazów (dopełniacz, rodzaj): rules/verdict.yaml. Te same dane → te same zdania.

Alternatywa (D80) musi być LEPSZA od wyboru pod względem ryzyka suszy (mniej lat ze stratą > 20%) przy podobnym lub
lepszym plonie względnym. Wyjątek: wybór jest ❌ wyłącznie przez płodozmian – wtedy uprawa o podobnym ryzyku z
wyraźnym zdaniem „po pszenicy lepiej zrobić przerwę – rzepak jej nie wymaga”.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.analysis import suggestions as sugg_mod
from app.analysis import verdict as verdict_mod
from app.analysis.crops import ALL_CROPS, RANKING_CROPS
from app.analysis.suggestions import HISTORY_UNKNOWN, _ago, _same, grew, years_break
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
SOIL_RANK = {"nieodpowiednia": 0, "neutralna": 1, "odpowiednia": 2}


@lru_cache
def cfg() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["choice"]


def parse_planned(value: str | list[str] | None) -> list[str]:
    """'pszenica_ozima,zboza_jare' albo lista → 1–3 identyfikatory: uprawy z rankingu albo GRUPY upraw (zboża ozime,
    zboża jare, strączkowe, rzepak jesień, …) – grupę oceniamy przez najlepszy gatunek (D80). Nieznany → ValueError."""
    if value is None:
        return []
    items = value.split(",") if isinstance(value, str) else list(value)
    out: list[str] = []
    for x in (i.strip() for i in items):
        if not x:
            continue
        if x not in ALL_CROPS:
            raise ValueError(x)
        if x not in out:
            out.append(x)
    if len(out) > cfg()["max_planned"]:
        raise ValueError(f"najwyżej {cfg()['max_planned']} uprawy")
    return out


def group_members(crop_id: str) -> list[str]:
    """Gatunki z rankingu reprezentujące grupę (group_id z crops.csv + aliasy z choice.yaml). Pusta lista = nie grupa."""
    alias = cfg().get("group_alias", {}).get(crop_id)
    if alias:
        return list(alias)
    members = [c.id for c in RANKING_CROPS if c.group_id == crop_id and c.id != crop_id]
    return ([crop_id] if crop_id in RANKING_IDS else []) + members if members else []


def _gen(crop_id: str) -> str:
    return verdict_mod.cfg()["genitive"].get(crop_id) or ALL_CROPS[crop_id].label.lower()


def _prev(history: list[str]) -> str | None:
    return history[0] if history and history[0] != HISTORY_UNKNOWN and history[0] in ALL_CROPS else None


def _rotation_k(crop_id: str, history: list[str]) -> int | None:
    return next((k + 1 for k, h in enumerate(history) if h != HISTORY_UNKNOWN and _same(h, crop_id)), None)


def why_choice(item: CropSuggestion, history: list[str], light: bool) -> str:
    w = cfg()["why"]
    crop = ALL_CROPS[item.crop_id]
    prev = _prev(history)
    if item.rotation.status == "naruszenie" and item.soil_suitability != "nieodpowiednia":
        k = _rotation_k(item.crop_id, history) or 1
        return w["rotation_violation"].format(label=item.label, grew=grew(item.crop_id), ago=_ago(k),
                                              years=years_break(crop.min_break_years))
    if item.soil_suitability == "nieodpowiednia":  # gleba ważniejsza; płodozmian – w rotation.notes
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


def _choice_from_field(item: CropSuggestion, history: list[str], light: bool, requested: str,
                       group_note: str | None = None) -> ChoiceItem:
    return ChoiceItem(
        crop_id=item.crop_id, label=item.label, category=item.category, category_label=item.category_label,
        requested_id=requested, group_note=group_note,
        yield_typical_t_ha=item.yield_typical_t_ha, total_typical_t=item.total_typical_t,
        yield_weak_t_ha=item.yield_weak_t_ha, total_weak_t=item.total_weak_t, weak_year=item.weak_year,
        drought_risk_years=item.drought_risk_years, years_simulated=item.years_simulated, rotation=item.rotation,
        why=why_choice(item, history, light), confidence=item.confidence)


def _choice_from_perennial(item: PerennialSuggestion, rotation: RotationCheck) -> ChoiceItem:
    return ChoiceItem(
        crop_id=item.crop_id, label=item.label, category=None, category_label=None, perennial=True,
        requested_id=item.crop_id,
        yield_typical_t_ha=item.yield_typical_t_ha, total_typical_t=item.total_typical_t,
        yield_weak_t_ha=item.yield_weak_t_ha, total_weak_t=item.total_weak_t, weak_year=item.weak_year,
        drought_risk_years=item.drought_risk_years, years_simulated=item.years_simulated, rotation=rotation,
        why=cfg()["why"]["perennial"], confidence="ograniczona")


def _rotation_only(ref: CropSuggestion) -> bool:
    """Wybór jest ❌ wyłącznie przez płodozmian (gleba i woda pozwoliłyby go uprawiać)."""
    if ref.category != "odradzane" or ref.rotation.status != "naruszenie":
        return False
    return sugg_mod.category(ref.soil_suitability, ref.drought_risk_years, ref.relative_yield_median,
                             RotationCheck(status="ok")) != "odradzane"


def why_alternative(alt: CropSuggestion, ref: CropSuggestion | None, history: list[str], light: bool,
                    rotation_case: bool) -> str:
    a = cfg()["alternative_why"]
    prev = _prev(history)
    n = alt.years_simulated
    if ref is None:
        txt = a["no_ref"].format(risk=alt.drought_risk_years, n=n)
    elif rotation_case and alt.drought_risk_years >= ref.drought_risk_years:
        if alt.rotation.status == "plus" and prev:
            return a["rotation_only_plus"].format(prev_gen=_gen(prev), cand_low=alt.label.lower(),
                                                  risk=alt.drought_risk_years, n=n)
        txt = a["rotation_only"].format(ref_gen=_gen(ref.crop_id), cand_low=alt.label.lower(),
                                        risk=alt.drought_risk_years, n=n)
    else:
        better_soil = SOIL_RANK[alt.soil_suitability] > SOIL_RANK[ref.soil_suitability]
        key = ("risk_soil_light" if better_soil and light and alt.soil_suitability == "odpowiednia" else
               "risk_soil" if better_soil else "risk")
        txt = a[key].format(cand=alt.label, risk=alt.drought_risk_years, n=n, ref_risk=ref.drought_risk_years)
    if alt.rotation.status == "plus" and prev:
        txt += a["plus_suffix"].format(prev_gen=_gen(prev))
    return txt


def alternatives_for(field: list[CropSuggestion], chosen: list[CropSuggestion], excluded: set[str],
                     history: list[str], light: bool) -> list[AlternativeItem]:
    c = cfg()
    ref = max(chosen, key=lambda i: i.score, default=None)
    pool = [i for i in field if i.crop_id not in excluded and i.category != "odradzane"
            and i.rotation.status != "naruszenie"]
    rotation_case = ref is not None and _rotation_only(ref)
    picked: list[tuple[CropSuggestion, str]] = []
    for i in pool:
        if ref is None:
            picked.append((i, "lepsza"))
            continue
        similar_yield = i.relative_yield_median >= ref.relative_yield_median - c["similar_relative_yield"]
        if i.drought_risk_years < ref.drought_risk_years and similar_yield:
            picked.append((i, "lepsza"))
        elif (rotation_case and similar_yield and i.rotation.status != "ostrzezenie"  # nie „zboże po zbożu”
              and SOIL_RANK[i.soil_suitability] >= SOIL_RANK[ref.soil_suitability]):
            picked.append((i, "podobna"))
    picked.sort(key=lambda t: (t[1] != "lepsza", t[0].rotation.status == "ostrzezenie", t[0].drought_risk_years,
                               -SOIL_RANK[t[0].soil_suitability], -t[0].relative_yield_median, -t[0].score))
    return [AlternativeItem(
        crop_id=i.crop_id, label=i.label, category=i.category, category_label=i.category_label, relation=rel,
        yield_typical_t_ha=i.yield_typical_t_ha, total_typical_t=i.total_typical_t,
        drought_risk_years=i.drought_risk_years, years_simulated=i.years_simulated,
        why=why_alternative(i, ref, history, light, rotation_case)) for i, rel in picked[: c["max_alternatives"]]]


def not_recommended_reason(item: CropSuggestion, history: list[str], light: bool) -> str:
    r = cfg()["not_recommended"]
    crop = ALL_CROPS[item.crop_id]
    if item.rotation.status == "naruszenie":
        k = _rotation_k(crop.id, history)
        if k is not None:
            return r["rotation"].format(grew=grew(crop.id), ago=_ago(k), years=years_break(crop.min_break_years))
    if item.soil_suitability == "nieodpowiednia":
        return r["soil_light"] if light else r["soil"]
    return r["drought"].format(risk=item.drought_risk_years, n=item.years_simulated)


def attach(sug: CropSuggestions | None, planned: list[str], light: bool) -> CropSuggestions | None:
    """Dokłada do rankingu: choice (wybór rolnika), choice_summary, choice_notes, alternatives, not_recommended, top_ids."""
    if sug is None:
        return None
    c = cfg()
    history = list(sug.crop_history)
    field = [i for g in sug.groups if g.key == "polowe" for i in g.items]
    by_id = {i.crop_id: i for i in field}
    per = {p.crop_id: p for p in (sug.perennials.items if sug.perennials else [])}
    popular = {k: n for n, k in enumerate(verdict_mod.cfg()["popular"])}

    choice: list[ChoiceItem] = []
    notes: list[str] = []
    for rid in planned:
        members = group_members(rid)
        if members and not (rid in by_id and len(members) == 1):
            cands = [by_id[m] for m in members if m in by_id]
            if cands:
                best = min(cands, key=lambda i: (CATEGORY_ORDER[i.category], -i.score))
                note = None if best.crop_id == rid else c["group_note"].format(
                    group=ALL_CROPS[rid].label.lower(), best=best.label.lower())
                if all(x.crop_id != best.crop_id for x in choice):
                    choice.append(_choice_from_field(best, history, light, rid, note))
                continue
        if rid in by_id:
            if all(x.crop_id != rid for x in choice):
                choice.append(_choice_from_field(by_id[rid], history, light, rid))
        elif rid in per:
            choice.append(_choice_from_perennial(per[rid], sugg_mod.rotation(ALL_CROPS[rid], history)))
        else:
            notes.append(c["unrated"].format(label=ALL_CROPS[rid].label))

    chosen_ids = {x.crop_id for x in choice}
    chosen_field = [by_id[x.crop_id] for x in choice if x.crop_id in by_id]
    alternatives = alternatives_for(field, chosen_field, chosen_ids, history, light) if choice else []

    bad = sorted((i for i in field if i.category == "odradzane" and i.crop_id not in chosen_ids),
                 key=lambda i: popular.get(i.crop_id, 99))
    not_recommended = [NotRecommendedItem(crop_id=i.crop_id, label=i.label,
                                          reason=not_recommended_reason(i, history, light))
                       for i in bad[: c["not_recommended_max"]]]
    top_ids = [i.crop_id for i in field if i.category != "odradzane"][: c["top_n"]]

    summary = None
    if choice:
        s = c["summary"]
        cats = [x.category for x in choice if x.category is not None]
        better = any(a.relation == "lepsza" for a in alternatives)
        if not cats:
            summary = s["perennial_only"]
        elif len(chosen_field) == 1 and _rotation_only(chosen_field[0]):  # ❌ tylko przez płodozmian
            one = chosen_field[0]
            summary = s["rotation_only"].format(label=one.label, grew=grew(one.crop_id),
                                                ago=_ago(_rotation_k(one.crop_id, history) or 1))
        elif all(x == "odradzane" for x in cats):
            summary = s["all_bad"] if alternatives else s["all_bad_no_alt"]
        elif "odradzane" in cats:
            summary = s["some_bad"].format(bad=", ".join(x.label.lower() for x in choice if x.category == "odradzane"))
        else:
            best = min(cats, key=CATEGORY_ORDER.get)
            summary = (s["good_but_better"] if better else s["good"]) if best == "polecane" else \
                (s["possible_but_better"] if better else s["possible"])

    return sug.model_copy(update={"choice": choice, "choice_summary": summary, "choice_notes": notes,
                                  "alternatives": alternatives, "not_recommended": not_recommended,
                                  "top_ids": top_ids})
