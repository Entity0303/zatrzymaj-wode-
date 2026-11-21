"""Ogólny stan wodny działki: wskaźnik 0–100 (więcej = lepiej) i status ok / warn / risk / danger / no_data.

Składowe (każda 0–100):
- woda – % wody dostępnej (strefa korzeni w fazach uprawy, profil ~1 m poza nimi),
- ryzyko – dni do stresu wodnego (tylko fazy wrażliwe),
- historia – pozycja na tle 10 lat: % lat z niższym bilansem wody od 1 III i % lat z mniejszym
  zapasem wody tego dnia (średnia z dostępnych).
Brak składowej → wagi pozostałych przeskalowane. Wagi i progi poniżej (D35).
Poza fazami wrażliwymi (dojrzewanie, po zbiorze, przed siewem, wschody jesienne, spoczynek) ocena
dotyczy ZAPASU WODY W GLEBIE, nie stresu roślin: inne nagłówki, status najwyżej „risk” (D35).
"""

from app.analysis.facts import Facts
from app.analysis.water_balance import format_mm
from app.schemas.analysis import OverallStatus, Soil, StatusLevel

# ── WAGI I PROGI (D35) ──────────────────────────────────────────────────────────────────────
WEIGHTS_SENSITIVE = {"woda": 0.45, "ryzyko": 0.35, "historia": 0.20}
WEIGHTS_OTHER = {"woda": 0.65, "historia": 0.35}
# dni do stresu -> punkty (0 = stres trwa); brak stresu w horyzoncie 16 dni -> 100
RISK_POINTS = [(0, 0), (3, 25), (7, 50), (16, 75)]
STATUS_THRESHOLDS: list[tuple[int, StatusLevel]] = [(70, "ok"), (50, "warn"), (30, "risk"), (0, "danger")]
OFF_SEASON_MAX: StatusLevel = "risk"  # poza fazami wrażliwymi nie ogłaszamy „Suszy” roślin
ORDER: list[StatusLevel] = ["ok", "warn", "risk", "danger"]

HEADLINES_SENSITIVE: dict[StatusLevel, str] = {
    "ok": "Dobrze – wody w glebie wystarcza",
    "warn": "Uwaga – rośnie ryzyko suszy",
    "risk": "Ryzyko – rośliny wkrótce odczują brak wody",
    "danger": "Susza – rośliny cierpią z braku wody",
}
HEADLINES_OTHER: dict[StatusLevel, str] = {
    "ok": "Dobrze – zapas wody w glebie w normie",
    "warn": "Uwaga – mniejszy zapas wody w glebie niż zwykle",
    "risk": "Ryzyko – mały zapas wody w glebie",
}


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


def status_for(score: int, sensitive: bool) -> StatusLevel:
    level = next(s for t, s in STATUS_THRESHOLDS if score >= t)
    if not sensitive and ORDER.index(level) > ORDER.index(OFF_SEASON_MAX):
        level = OFF_SEASON_MAX
    return level


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
            text += f" Rośliny zaczną odczuwać brak wody za ok. {d2s} dni, jeśli nie spadnie deszcz."
    elif f.get("phase_label"):
        text += f" Uprawa: {f['phase_label']} – ocena dotyczy zapasu wody w glebie."
    return text[0].upper() + text[1:]


def overall_status(f: Facts, soil: Soil) -> OverallStatus:
    if soil.non_agricultural:
        return OverallStatus(
            level="no_data",
            score=None,
            headline="Ocena suszy rolniczej nie dotyczy tej działki",
            summary=soil.non_agricultural_note or "Według mapy gleb IUNG to nie jest grunt rolny.",
        )
    score = score_value(f)
    if score is None:
        return OverallStatus(
            level="no_data", score=None, headline="Brak danych do oceny stanu wody",
            summary="Nie udało się policzyć wody w glebie – brak danych pogodowych lub glebowych.",
        )
    sensitive = bool(f.get("sensitive"))
    level = status_for(score, sensitive)
    headline = (HEADLINES_SENSITIVE if sensitive else HEADLINES_OTHER)[level]
    if sensitive and level == "risk" and f.get("days_to_stress") == 0:
        headline = "Ryzyko – rośliny odczuwają brak wody"
    return OverallStatus(level=level, score=score, headline=headline, summary=summary_sentence(f))
