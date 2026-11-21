"""Silnik reguł: warunek na faktach -> rekomendacja -> fakty, które ją uruchomiły (SPEC 7.D, D38).

Reguły w analysis/rules/*.yaml. Każda reguła:
  id, category (retencja | agrotechnika | nawadnianie), priority, confidence (albo confidence_fact),
  requires (np. [terrain], [water_nearby] – reguła wyłączona, dopóki te dane nie są dostępne),
  when: {all: [warunki], any: [warunki]} – co najmniej jeden warunek (bez warunku = błąd),
  title, description, why (szablony z {fakt}).
Warunek: {fact: nazwa, <op>: wartość}, op ∈ eq, ne, in, not_in, lt, lte, gt, gte.
Fakt = None (brak danych) -> warunek fałszywy. Szablon z brakującym faktem -> reguła pominięta
(żadnego tekstu bez danych). LLM nie uczestniczy.

Kolejność: retencja -> agrotechnika -> nawadnianie, w grupie od najwyższego priorytetu.
Panel: najważniejsza z każdej grupy (maks. 3) – `in_panel`; pełna lista – paszport.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.analysis.facts import FACT_META, Facts
from app.schemas.analysis import Evidence, Recommendation

RULES_DIR = Path(__file__).parent / "rules"
CATEGORY_ORDER = ["retencja", "agrotechnika", "nawadnianie"]
OPS = {"eq", "ne", "in", "not_in", "lt", "lte", "gt", "gte"}
# fakty techniczne – nie pokazujemy ich jako „danych wejściowych”
HIDDEN_FACTS = {"sensitive", "off_season", "crop_kind", "irrigation_status", "season_complete", "non_agricultural"}
DISPLAY_FACT = {"phase": "phase_label", "crop": "crop_label"}
_TOKEN = re.compile(r"\{(\w+)\}")


class RuleError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    priority: int
    confidence: str
    title: str
    description: str
    why: tuple[str, ...]
    all: tuple[dict, ...]
    any: tuple[dict, ...]
    requires: tuple[str, ...] = ()
    confidence_fact: str | None = None
    source_file: str = ""


@dataclass
class Evaluation:
    recommendations: list[Recommendation]
    disabled: list[str] = field(default_factory=list)  # reguły czekające na dane (requires)
    skipped_missing_data: list[str] = field(default_factory=list)


def _validate(raw: dict, src: str) -> Rule:
    for k in ("id", "category", "priority", "title", "description", "when"):
        if k not in raw:
            raise RuleError(f"{src}: reguła bez pola '{k}': {raw.get('id')}")
    if raw["category"] not in CATEGORY_ORDER:
        raise RuleError(f"{src}: zła kategoria w {raw['id']}")
    when = raw["when"] or {}
    all_c, any_c = tuple(when.get("all") or ()), tuple(when.get("any") or ())
    if not all_c and not any_c:
        raise RuleError(f"{src}: reguła {raw['id']} nie ma warunku")
    for c in all_c + any_c:
        ops = set(c) - {"fact"}
        if "fact" not in c or len(ops) != 1 or not ops <= OPS:
            raise RuleError(f"{src}: zły warunek w {raw['id']}: {c}")
    return Rule(
        id=raw["id"], category=raw["category"], priority=int(raw["priority"]),
        confidence=raw.get("confidence", "srednia"), title=raw["title"], description=raw["description"],
        why=tuple(raw.get("why") or ()), all=all_c, any=any_c, requires=tuple(raw.get("requires") or ()),
        confidence_fact=raw.get("confidence_fact"), source_file=src,
    )


@lru_cache
def load_rules(directory: str = str(RULES_DIR)) -> tuple[Rule, ...]:
    rules: list[Rule] = []
    for path in sorted(Path(directory).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for raw in data.get("rules") or []:
            rules.append(_validate(raw, path.name))
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        raise RuleError("Zduplikowane id reguł")
    return tuple(rules)


def cond_true(c: dict, facts: Facts) -> bool:
    value = facts.get(c["fact"])
    if value is None:
        return False
    op, target = next((k, v) for k, v in c.items() if k != "fact")
    try:
        return {
            "eq": lambda: value == target,
            "ne": lambda: value != target,
            "in": lambda: value in target,
            "not_in": lambda: value not in target,
            "lt": lambda: value < target,
            "lte": lambda: value <= target,
            "gt": lambda: value > target,
            "gte": lambda: value >= target,
        }[op]()
    except TypeError:
        return False


def matches(rule: Rule, facts: Facts) -> list[dict] | None:
    """Lista spełnionych warunków albo None, gdy reguła nie pasuje."""
    if not all(cond_true(c, facts) for c in rule.all):
        return None
    hit_any = [c for c in rule.any if cond_true(c, facts)]
    if rule.any and not hit_any:
        return None
    return list(rule.all) + hit_any


def fmt_value(v: Any) -> str:
    if isinstance(v, bool):
        return "tak" if v else "nie"
    if isinstance(v, float):
        return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}".replace(".", ",")
    return str(v)


def render(template: str, facts: Facts) -> str:
    """Podstawia {fakt}; brakujący fakt -> KeyError (reguła zostanie pominięta)."""
    def sub(m: re.Match) -> str:
        v = facts.get(m.group(1))
        if v is None:
            raise KeyError(m.group(1))
        return fmt_value(v)

    return _TOKEN.sub(sub, template)


def evidence(conds: list[dict], facts: Facts) -> list[Evidence]:
    out, seen = [], set()
    for c in conds:
        name = DISPLAY_FACT.get(c["fact"], c["fact"])
        if name in HIDDEN_FACTS or name in seen or facts.get(name) is None:
            continue
        seen.add(name)
        label, unit, source = FACT_META.get(name, (name, None, "analiza"))
        v = facts.get(name)
        out.append(Evidence(name=label, value=v if isinstance(v, (int, float)) and not isinstance(v, bool) else fmt_value(v),
                            unit=unit, source=source))
    return out


def evaluate(facts: Facts, available: set[str] | None = None, rules: tuple[Rule, ...] | None = None) -> Evaluation:
    available = available or set()
    ev = Evaluation([])
    recs: list[Recommendation] = []
    for rule in rules if rules is not None else load_rules():
        if not set(rule.requires) <= available:
            ev.disabled.append(rule.id)
            continue
        conds = matches(rule, facts)
        if conds is None:
            continue
        try:
            title = render(rule.title, facts)
            desc = render(rule.description, facts)
            why_parts = []
            for t in rule.why:
                try:
                    why_parts.append(render(t, facts))
                except KeyError:
                    continue
        except KeyError:
            ev.skipped_missing_data.append(rule.id)
            continue
        inputs = evidence(conds, facts)
        data = ", ".join(f"{e.name.lower()}: {fmt_value(e.value)}{' ' + e.unit if e.unit else ''}" for e in inputs)
        why = " ".join(why_parts) + (f" Dane: {data}." if data else "")
        conf = facts.get(rule.confidence_fact) if rule.confidence_fact else rule.confidence
        recs.append(Recommendation(
            id=rule.id, category=rule.category, title=title, description=desc, why=why.strip(), inputs=inputs,
            confidence=conf if conf in ("wysoka", "srednia", "ograniczona") else rule.confidence,
            rule_id=rule.id, priority=rule.priority,
        ))
    recs.sort(key=lambda r: (CATEGORY_ORDER.index(r.category), -r.priority))
    seen_cat: set[str] = set()
    for i, r in enumerate(recs):
        if r.category not in seen_cat:
            recs[i] = r.model_copy(update={"in_panel": True})
            seen_cat.add(r.category)
    ev.recommendations = recs
    return ev
