"""Silnik reguł: warunek na faktach -> rekomendacja -> fakty, które ją uruchomiły (SPEC 7.D, D38).

Reguły w analysis/rules/*.yaml. Każda reguła:
  id, category (retencja | agrotechnika | nawadnianie), priority, confidence (albo confidence_fact),
  requires (np. [terrain], [water_nearby] – reguła wyłączona, dopóki te dane nie są dostępne),
  when: {all: [warunki], any: [warunki]} – co najmniej jeden warunek (bez warunku = błąd),
  title, description, why (szablony z {fakt}).
Warunek: {fact: nazwa, <op>: wartość}, op ∈ eq, ne, in, not_in, lt, lte, gt, gte, exists.
Fakt = None (brak danych) -> warunek fałszywy. Szablon z brakującym faktem -> reguła pominięta
(żadnego tekstu bez danych). LLM nie uczestniczy.

A5 (D42, konsultacja z mentorem): pola reguły
  timing: teraz | po_zbiorze | przed_sezonem  albo {in_season: …, off_season: …},
  permit: none | maybe | required (domyślnie: nawadnianie – required, reszta – none),
  eco_scheme: klucz z ECO_SCHEMES, fertilization: true – reguła o nawożeniu (pomijana przy silnym stresie).

Kolejność: retencja -> agrotechnika -> nawadnianie; w grupie: najpierw pewne (bez ostrzeżenia), potem bez
formalności, potem „teraz” przed „po zbiorze” i „przed następnym sezonem”, na końcu priorytet.
Panel: pierwsza z każdej grupy (maks. 3) – `in_panel`. Paszport: maks. 5 (panel + najlepsze wg priorytetu
i pewności). Niska pewność -> `warning` „obarczone dużym ryzykiem błędu”, nigdy pierwsza w grupie.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.analysis.facts import FACT_META, Facts
from app.schemas.analysis import EcoScheme, Evidence, Recommendation

RULES_DIR = Path(__file__).parent / "rules"
CATEGORY_ORDER = ["retencja", "agrotechnika", "nawadnianie"]
OPS = {"eq", "ne", "in", "not_in", "lt", "lte", "gt", "gte", "exists"}
# fakty techniczne – nie pokazujemy ich jako „danych wejściowych”
HIDDEN_FACTS = {"sensitive", "off_season", "crop_kind", "irrigation_status", "season_complete", "non_agricultural",
                "in_season", "strong_stress"}
DISPLAY_FACT = {"phase": "phase_label", "crop": "crop_label", "rain_retention": "rain_retention_label",
                "light_soil": "soil_txt", "same_crop": "previous_crop_label", "cereal_after_cereal": "previous_crop_label",
                "soil_species": "texture_label"}
_TOKEN = re.compile(r"\{(\w+)\}")

MAX_PANEL = 3
MAX_TOTAL = 5
TIMINGS = ("teraz", "po_zbiorze", "przed_sezonem")
TIMING_LABELS = {"teraz": "teraz", "po_zbiorze": "po zbiorze", "przed_sezonem": "przed następnym sezonem"}
PERMITS = ("none", "maybe", "required")
WODY_POLSKIE_URL = "https://www.gov.pl/web/wody-polskie"
PERMIT_NOTES = {
    "none": "Bez formalności – możesz to zrobić sam.",
    "maybe": "Może wymagać zgłoszenia wodnoprawnego – sprawdź w Wodach Polskich.",
    "required": "Wymaga pozwolenia wodnoprawnego (pobór wody) – Wody Polskie.",
}
LOW_CONFIDENCE_WARNING = "Obarczone dużym ryzykiem błędu – traktuj jako wskazówkę i sprawdź na polu."
CONFIDENCE_BONUS = {"wysoka": 10, "srednia": 0, "ograniczona": -20}
_ECO_CARBON = "Rolnictwo węglowe i zarządzanie składnikami odżywczymi"
ECO_NOTE = "Sprawdź aktualne warunki w ARiMR."
# Ekoschematy PS WPR 2023–2027 (ARiMR) – nazwy praktyk; bez kwot dopłat (D42)
ECO_SCHEMES: dict[str, EcoScheme] = {
    "E_MPW": EcoScheme(name=_ECO_CARBON, practice="Międzyplony ozime lub wsiewki śródplonowe", code="E_MPW", note=ECO_NOTE),
    "E_USU": EcoScheme(name=_ECO_CARBON, practice="Uproszczone systemy uprawy", code="E_USU", note=ECO_NOTE),
    "E_WSG": EcoScheme(name=_ECO_CARBON, practice="Wymieszanie słomy z glebą", code="E_WSG", note=ECO_NOTE),
    "E_ZSU": EcoScheme(name=_ECO_CARBON, practice="Zróżnicowana struktura upraw", code="E_ZSU", note=ECO_NOTE),
    "PLAN_NAWOZENIA": EcoScheme(name=_ECO_CARBON, practice="Opracowanie i przestrzeganie planu nawożenia",
                                code=None, note=ECO_NOTE),
    "TUZ_RETENCJA": EcoScheme(name="Retencjonowanie wody na trwałych użytkach zielonych",
                              practice="Retencjonowanie wody na TUZ (tylko trwałe użytki zielone)", code=None,
                              note=ECO_NOTE),
}


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
    timing: str = "teraz"
    timing_off_season: str | None = None
    permit: str = "none"
    eco_scheme: str | None = None
    fertilization: bool = False

    def when_for(self, facts: Facts) -> str:
        return self.timing_off_season if (self.timing_off_season and facts.get("off_season")) else self.timing


@dataclass
class Evaluation:
    recommendations: list[Recommendation]
    disabled: list[str] = field(default_factory=list)  # reguły czekające na dane (requires)
    skipped_missing_data: list[str] = field(default_factory=list)
    all_matched: list[Recommendation] = field(default_factory=list)  # przed ograniczeniem do 5


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
    timing = raw.get("timing", "teraz")
    t_in, t_off = (timing.get("in_season"), timing.get("off_season")) if isinstance(timing, dict) else (timing, None)
    if t_in not in TIMINGS or (t_off is not None and t_off not in TIMINGS):
        raise RuleError(f"{src}: złe 'timing' w {raw['id']}")
    permit = raw.get("permit", "required" if raw["category"] == "nawadnianie" else "none")
    if permit not in PERMITS:
        raise RuleError(f"{src}: złe 'permit' w {raw['id']}")
    eco = raw.get("eco_scheme")
    if eco is not None and eco not in ECO_SCHEMES:
        raise RuleError(f"{src}: nieznany ekoschemat w {raw['id']}: {eco}")
    return Rule(
        id=raw["id"], category=raw["category"], priority=int(raw["priority"]),
        confidence=raw.get("confidence", "srednia"), title=raw["title"], description=raw["description"],
        why=tuple(raw.get("why") or ()), all=all_c, any=any_c, requires=tuple(raw.get("requires") or ()),
        confidence_fact=raw.get("confidence_fact"), source_file=src,
        timing=t_in, timing_off_season=t_off, permit=permit, eco_scheme=eco,
        fertilization=bool(raw.get("fertilization", False)),
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
    op, target = next((k, v) for k, v in c.items() if k != "fact")
    if op == "exists":  # {fact: x, exists: true} – są dane (reguła zależna tylko od ich obecności)
        return (value is not None) == bool(target)
    if value is None:
        return False
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
    if isinstance(v, (int, float)):
        # bez pozornej precyzji: od 10 w górę liczby całkowite; minus typograficzny
        txt = f"{v:.0f}" if abs(v) >= 10 or abs(v - round(v)) < 0.05 else f"{v:.1f}".replace(".", ",")
        return txt.replace("-", "−")
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


def _order_key(r: Recommendation) -> tuple:
    return (CATEGORY_ORDER.index(r.category), r.warning is not None, PERMITS.index(r.permit),
            TIMINGS.index(r.when), -r.priority)


def _score(r: Recommendation) -> int:
    """Wybór do paszportu (maks. 5): priorytet + pewność; działania na później i formalności niżej."""
    return r.priority + CONFIDENCE_BONUS[r.confidence] - 10 * TIMINGS.index(r.when) - 5 * PERMITS.index(r.permit)


def select(recs: list[Recommendation]) -> list[Recommendation]:
    """Panel: pierwsza z każdej grupy (maks. 3). Paszport: panel + najlepsze pozostałe – razem maks. 5."""
    ordered = sorted(recs, key=_order_key)
    panel_ids: list[str] = []
    seen: set[str] = set()
    for r in ordered:
        if r.category not in seen and len(panel_ids) < MAX_PANEL:
            seen.add(r.category)
            panel_ids.append(r.id)
    rest = sorted((r for r in ordered if r.id not in panel_ids), key=lambda r: -_score(r))
    chosen = [r for r in ordered if r.id in panel_ids] + rest[: max(0, MAX_TOTAL - len(panel_ids))]
    chosen.sort(key=_order_key)
    return [r.model_copy(update={"in_panel": r.id in panel_ids}) for r in chosen]


def evaluate(facts: Facts, available: set[str] | None = None, rules: tuple[Rule, ...] | None = None,
             limit: bool = True) -> Evaluation:
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
        when = rule.when_for(facts)
        if rule.fertilization and facts.get("strong_stress") and when == "teraz":
            ev.skipped_missing_data.append(rule.id)  # przy suszy nawóz nie zadziała (D40, D42)
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
        conf = conf if conf in ("wysoka", "srednia", "ograniczona") else rule.confidence
        recs.append(Recommendation(
            id=rule.id, category=rule.category, title=title, description=desc, why=why.strip(), inputs=inputs,
            confidence=conf, rule_id=rule.id, priority=rule.priority,
            when=when, when_label=TIMING_LABELS[when], permit=rule.permit, permit_note=PERMIT_NOTES[rule.permit],
            permit_url=None if rule.permit == "none" else WODY_POLSKIE_URL,
            warning=LOW_CONFIDENCE_WARNING if conf == "ograniczona" else None,
            eco_scheme=ECO_SCHEMES[rule.eco_scheme] if rule.eco_scheme else None,
        ))
    ev.all_matched = sorted(recs, key=_order_key)
    ev.recommendations = select(recs) if limit else ev.all_matched
    return ev
