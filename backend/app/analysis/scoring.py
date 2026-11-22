"""Ogólny stan wodny działki: wskaźnik 0–100 (więcej = lepiej) i status ok / warn / risk / danger / no_data.

Składowe (każda 0–100):
- woda – % wody dostępnej (strefa korzeni w fazach uprawy, profil ~1 m poza nimi),
- ryzyko – dni do stresu wodnego (tylko fazy wrażliwe),
- historia – pozycja na tle 10 lat: % lat z niższym bilansem wody od 1 III i % lat z mniejszym
  zapasem wody tego dnia (średnia z dostępnych).
Brak składowej → wagi pozostałych przeskalowane. Wagi i progi poniżej (D35).
Dojrzewanie (poza fazami wrażliwymi, ale w sezonie): woda + historia, status najwyżej „risk” (D35).

POZA SEZONEM uprawy (przed siewem, po zbiorze, wschody jesienne, spoczynek zimowy) i BEZ UPRAWY (A5b-1, D52)
status nie wynika ze stresu uprawy ani z bilansu całego sezonu, tylko z zapasu wody w glebie (profil ~1 m)
i klimatycznego bilansu wodnego z ostatnich 30 dni na tle 10 lat: woda 0,6 + bilans 30 dni 0,4 (pozycja wśród
10 lat, 0–100).

A20: STOPIEŃ braku wody w obu ścieżkach (z uprawą i bez) z jednej funkcji `drought_level` (progi w
rules/status.yaml): zapas ≤ 15% albo najsuchszy okres z 10 lat → „Bardzo mało wody”; ≤ 35% albo 2 najsuchsze → „Mało
wody”; ≤ 50% → „Uwaga”; wyżej → „W normie”. Faza uprawy nie ucina stopnia (dawniej poza fazami wrażliwymi najwyżej
„risk”). Wskaźnik 0–100 zostaje, ale mieści się w paśmie stopnia.
"""

from functools import lru_cache
from pathlib import Path

import yaml

from app.analysis.facts import OFF_SEASON_PHASES, Facts
from app.core.format import days
from app.analysis.water_balance import format_mm
from app.schemas.analysis import OverallStatus, Soil, StatusLevel

# ── WAGI I PROGI (D35) ──────────────────────────────────────────────────────────────────────
WEIGHTS_SENSITIVE = {"woda": 0.45, "ryzyko": 0.35, "historia": 0.20}
WEIGHTS_OTHER = {"woda": 0.65, "historia": 0.35}
# dni do stresu -> punkty (0 = stres trwa); brak stresu w horyzoncie 16 dni -> 100
RISK_POINTS = [(0, 0), (3, 25), (7, 50), (16, 75)]
ORDER: list[StatusLevel] = ["ok", "warn", "risk", "danger"]
WEIGHTS_RESERVE = {"woda": 0.6, "bilans_30d": 0.4}  # poza sezonem i bez uprawy (D52)
SCOPE_LABELS = {"sezon": "w sezonie", "zimowanie": "w polu – zimowanie", "poza_sezonem": "poza sezonem",
                "bez_uprawy": "stan wody na działce"}
WINTERING_PHASES = {"wschody_jesienne", "spoczynek_zimowy"}  # uprawa jest w polu (oziminy, wieloletnie) – D65
# A20: nazwy stopni ze słownika (rules/status.yaml → labels): W normie / Uwaga / Mało wody / Bardzo mało wody
HEADLINES_FIELD: dict[StatusLevel, str] = {
    "ok": "W normie – zapas wody w glebie wystarcza",
    "warn": "Uwaga – mniej wody w glebie niż zwykle",
    "risk": "Mało wody – mały zapas wody w glebie",
    "danger": "Bardzo mało wody w glebie",
}

HEADLINES_SENSITIVE: dict[StatusLevel, str] = {
    "ok": "W normie – wody w glebie wystarcza",
    "warn": "Uwaga – rośnie ryzyko suszy",
    "risk": "Mało wody – rośliny wkrótce odczują brak wody",
    "danger": "Bardzo mało wody – roślinom brakuje wody",
}
HEADLINES_OTHER: dict[StatusLevel, str] = {
    "ok": "W normie – zapas wody w glebie wystarcza",
    "warn": "Uwaga – mniejszy zapas wody w glebie niż zwykle",
    "risk": "Mało wody – mały zapas wody w glebie",
    "danger": "Bardzo mało wody w glebie",
}
STATUS_RULES = Path(__file__).parent / "rules" / "status.yaml"


@lru_cache
def status_cfg() -> dict:
    return yaml.safe_load(STATUS_RULES.read_text(encoding="utf-8"))["status"]


def dry_rank(f: Facts) -> int | None:
    """Gorsza (niższa) z dwóch pozycji wśród lat: zapas wody tego dnia i bilans 30 dni – „w ilu z N lat było mniej”;
    None, gdy żadna nie ma ≥ `rank_min_years` lat porównawczych."""
    c = status_cfg()
    ranks = [lo for lo, of in ((f.get("water_rank_lower"), f.get("water_rank_of")),
                               (f.get("kbw30_rank_lower"), f.get("kbw30_rank_of")))
             if lo is not None and of and of >= c["rank_min_years"]]
    return min(ranks) if ranks else None


def drought_level(water_pct: float | None, rank_lower: int | None = None) -> StatusLevel:
    """A20: JEDYNE progi stopnia braku wody (z uprawą i bez). `rank_lower` – w ilu z 10 lat było mniej wody / niższy
    bilans tego dnia (gorsza z dwóch pozycji); None – bez porównania z latami."""
    c = status_cfg()
    if water_pct is None:
        return "no_data"
    pct = float(water_pct)
    level: StatusLevel = ("danger" if pct <= c["danger_max_pct"] else "risk" if pct <= c["risk_max_pct"] else
                          "warn" if pct <= c["warn_max_pct"] else "ok")
    if rank_lower is None or pct >= c["full_profile_pct"]:
        return level
    by_rank: StatusLevel | None = ("danger" if rank_lower <= c["rank_danger_lower"] else
                                   "risk" if rank_lower <= c["rank_risk_lower"] else None)
    if by_rank is None:
        return level
    if pct > c["rank_escalation_max_pct"]:  # zapas ponad połowę – najsuchszy okres to najwyżej „Uwaga”
        by_rank = "warn"
    return by_rank if ORDER.index(by_rank) > ORDER.index(level) else level


def level_for(f: Facts) -> StatusLevel:
    return drought_level(f.get("water_pct"), dry_rank(f))


def in_band(score: int | None, level: StatusLevel) -> int | None:
    """Wskaźnik 0–100 w paśmie stopnia (spójność liczby ze stopniem)."""
    if score is None or level not in BANDS:
        return score
    lo, hi = BANDS[level]
    return int(min(hi, max(lo, score)))


def risk_points(days_to_stress: int | None) -> float:
    if days_to_stress is None:
        return 100.0
    for limit, pts in RISK_POINTS:
        if days_to_stress <= limit:
            return float(pts)
    return 100.0


def components(f: Facts) -> dict[str, float]:
    out: dict[str, float] = {}
    if f.get("water_pct") is not None:
        out["woda"] = float(max(0, min(100, f["water_pct"])))
    if f.get("sensitive"):
        out["ryzyko"] = risk_points(f.get("days_to_stress"))
    hist = [x for x in (f.get("balance_percentile"), f.get("water_rank_pct")) if x is not None]
    if hist:
        out["historia"] = float(sum(hist) / len(hist))
    return out


def score_value(f: Facts) -> int | None:
    comp = components(f)
    if "woda" not in comp:
        return None
    weights = WEIGHTS_SENSITIVE if f.get("sensitive") else WEIGHTS_OTHER
    used = {k: w for k, w in weights.items() if k in comp}
    total = sum(used.values())
    return round(sum(comp[k] * w for k, w in used.items()) / total)


def summary_sentence(f: Facts) -> str:
    parts = []
    scope = " w strefie korzeni" if f.get("water_scope") == "strefa_korzeni" else ""
    if f.get("water_pct") is not None:
        parts.append(f"Gleba ma {f['water_pct']:.0f}% wody dostępnej{scope}")
    dev = f.get("balance_deviation_mm")
    if f.get("balance_mm") is not None and dev is not None and f.get("season_start_txt"):
        more_less = "mniej" if dev < 0 else "więcej"
        parts.append(
            f"od {f['season_start_txt']} bilans wody wynosi {format_mm(f['balance_mm'])} mm – "
            f"o {format_mm(dev, signed=False)} mm {more_less} niż zwykle"
        )
    elif f.get("precip_deficit_mm") is not None and f.get("season_start_txt"):
        d = f["precip_deficit_mm"]
        parts.append(f"od {f['season_start_txt']} spadło o {abs(d):.0f} mm {'mniej' if d > 0 else 'więcej'} deszczu niż zwykle")
    text = ", a ".join(parts) + "." if parts else "Brak danych do oceny."
    d2s = f.get("days_to_stress")
    if f.get("sensitive"):
        if d2s == 0:
            text += " Rośliny już odczuwają brak wody."
        elif d2s is not None:
            text += f" Rośliny zaczną odczuwać brak wody za ok. {days(d2s)}, jeśli nie spadnie deszcz."
    elif f.get("phase_label"):
        text += f" Uprawa: {f['phase_label']} – ocena dotyczy zapasu wody w glebie."
    return text[0].upper() + text[1:]


def reserve_score(water_pct: float | None, kbw30_percentile: float | None) -> int | None:
    """Zapas wody w glebie (0–100) i pozycja bilansu 30 dni wśród 10 lat (0–100); brak bilansu – sama woda."""
    if water_pct is None:
        return None
    comp = {"woda": float(max(0, min(100, water_pct)))}
    if kbw30_percentile is not None:
        comp["bilans_30d"] = float(kbw30_percentile)
    used = {k: w for k, w in WEIGHTS_RESERVE.items() if k in comp}
    return round(sum(comp[k] * w for k, w in used.items()) / sum(used.values()))


def reserve_summary(f: Facts, scope: str) -> str:
    text = f"W profilu gleby (ok. 1 m) jest {f['water_pct']:.0f}% wody dostępnej"
    if f.get("water_mm") is not None:
        text += f" ({f['water_mm']:.0f} mm)"
    lower, of = f.get("water_rank_lower"), f.get("water_rank_of")
    if lower is None or not of:
        text += "."
    elif lower == 0:
        text += f" – najmniej tego dnia w ostatnich {of} latach."
    else:
        text += f"; mniej wody było tego dnia w {lower} z {of} ostatnich lat."
    if f.get("kbw30_mm") is not None:
        text += (f" Bilans wody {f.get('kbw30_period_txt') or 'z ostatnich 30 dni'} (opad minus parowanie): "
                 f"{format_mm(f['kbw30_mm'])} mm")
        text += f" ({f['kbw30_vs_mean_txt']})." if f.get("kbw30_vs_mean_txt") else "."
    if scope == "poza_sezonem" and f.get("phase_label"):
        text += f" Uprawa: {f['phase_label']} – poza sezonem oceniamy zapas wody w glebie, nie stres roślin."
    elif scope == "zimowanie" and f.get("phase_label"):
        text += f" Uprawa jest w polu ({f['phase_label']}) – zimą oceniamy zapas wody w glebie, nie stres roślin."
    elif scope == "bez_uprawy":
        text += " Bez wybranej uprawy – stan dla typowego pola (po zbiorach goła gleba)."
    return text


BANDS = {"ok": (70, 100), "warn": (50, 69), "risk": (30, 49), "danger": (0, 29)}


def rank_score(f: Facts, level: StatusLevel) -> int:
    """Wskaźnik 0–100 z pozycji wśród 10 lat (woda 0,6, bilans 30 dni 0,4), w przedziale poziomu statusu."""
    w = 100.0 * f["water_rank_lower"] / f["water_rank_of"]
    k_lower, k_of = f.get("kbw30_rank_lower"), f.get("kbw30_rank_of")
    k = 100.0 * k_lower / k_of if k_of and k_lower is not None else w
    lo, hi = BANDS[level]
    return int(min(hi, max(lo, round(WEIGHTS_RESERVE["woda"] * w + WEIGHTS_RESERVE["bilans_30d"] * k))))


def reserve_status(f: Facts, scope: str) -> OverallStatus:
    """Status z zapasu wody w glebie i bilansu 30 dni na tle tej samej daty w 10 latach (poza sezonem uprawy,
    zimowanie, bez uprawy – D65); przy braku lat porównawczych – progi bezwzględne (D52)."""
    if f.get("water_pct") is None:
        return OverallStatus(level="no_data", score=None, headline="Brak danych do oceny stanu wody",
                             summary="Nie udało się policzyć wody w glebie – brak danych pogodowych lub glebowych.",
                             scope=scope, scope_label=SCOPE_LABELS[scope])
    level = level_for(f)  # A20: te same progi co z uprawą; faza nie ucina stopnia
    if f.get("water_rank_lower") is not None and f.get("water_rank_of"):
        score = in_band(rank_score(f, level), level)
    else:
        score = in_band(reserve_score(f.get("water_pct"), f.get("kbw30_percentile")), level)
    headline = (HEADLINES_FIELD if scope == "bez_uprawy" else HEADLINES_OTHER)[level]
    lower, of = f.get("water_rank_lower"), f.get("water_rank_of")
    below_usual = bool(of) and lower is not None and lower < of / 2
    if level == "warn" and not below_usual:
        k_lower = f.get("kbw30_rank_lower")
        headline = ("Uwaga – ostatnie 30 dni najsuchsze od lat" if k_lower == 0 else
                    "Uwaga – zapas wody w glebie niepełny")
    elif level == "warn" and scope != "bez_uprawy":
        headline = "Uwaga – mniejszy zapas wody w glebie niż zwykle"
    return OverallStatus(level=level, score=score, headline=headline, summary=reserve_summary(f, scope),
                         scope=scope, scope_label=SCOPE_LABELS[scope])


def overall_status(f: Facts, soil: Soil) -> OverallStatus:
    if soil.non_agricultural:
        return OverallStatus(
            level="no_data",
            score=None,
            headline="Ocena suszy rolniczej nie dotyczy tej działki",
            summary=soil.non_agricultural_note or "Według mapy gleb IUNG to nie jest grunt rolny.",
        )
    if f.get("has_crop") is False:
        return reserve_status(f, "bez_uprawy")
    if f.get("phase") in WINTERING_PHASES:
        return reserve_status(f, "zimowanie")
    if f.get("phase") in OFF_SEASON_PHASES:
        return reserve_status(f, "poza_sezonem")
    score = score_value(f)
    if score is None:
        return OverallStatus(
            level="no_data", score=None, headline="Brak danych do oceny stanu wody",
            summary="Nie udało się policzyć wody w glebie – brak danych pogodowych lub glebowych.",
        )
    sensitive = bool(f.get("sensitive"))
    level = level_for(f)  # A20: te same progi co bez uprawy; dojrzewanie nie ucina stopnia
    score = in_band(score, level)
    headline = (HEADLINES_SENSITIVE if sensitive else HEADLINES_OTHER)[level]
    if sensitive and level == "risk" and f.get("days_to_stress") == 0:
        headline = "Mało wody – rośliny odczuwają brak wody"
    # „niż zwykle” tylko, gdy dane to potwierdzają (bilans poniżej średniej z 10 lat)
    if not sensitive and level == "warn" and not ((f.get("balance_deviation_mm") or 0) < 0):
        headline = "Uwaga – zapas wody w glebie niepełny"
    return OverallStatus(level=level, score=score, headline=headline, summary=summary_sentence(f),
                         scope="sezon", scope_label=SCOPE_LABELS["sezon"])
