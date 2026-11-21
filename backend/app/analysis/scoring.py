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
10 lat, 0–100). Poza sezonem najwyżej „risk”; bez uprawy możliwa „susza glebowa” (danger).
"""

from app.analysis.facts import OFF_SEASON_PHASES, Facts
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
WEIGHTS_RESERVE = {"woda": 0.6, "bilans_30d": 0.4}  # poza sezonem i bez uprawy (D52)
SCOPE_LABELS = {"sezon": "w sezonie", "poza_sezonem": "poza sezonem", "bez_uprawy": "stan wody na działce"}
HEADLINES_FIELD: dict[StatusLevel, str] = {
    "ok": "Dobrze – zapas wody w glebie w normie",
    "warn": "Uwaga – mniej wody w glebie niż zwykle",
    "risk": "Ryzyko – mały zapas wody w glebie",
    "danger": "Susza glebowa – bardzo mało wody w glebie",
}

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
        text += f" Bilans opad − parowanie z ostatnich 30 dni: {format_mm(f['kbw30_mm'])} mm"
        text += f" ({f['kbw30_vs_mean_txt']})." if f.get("kbw30_vs_mean_txt") else "."
    if scope == "poza_sezonem" and f.get("phase_label"):
        text += f" Uprawa: {f['phase_label']} – poza sezonem oceniamy zapas wody w glebie, nie stres roślin."
    elif scope == "bez_uprawy":
        text += " Bez wybranej uprawy – stan dla pokrycia referencyjnego FAO-56 (trawa)."
    return text


def reserve_status(f: Facts, scope: str) -> OverallStatus:
    """Status z zapasu wody w glebie i bilansu 30 dni (poza sezonem uprawy / bez uprawy, D52)."""
    score = reserve_score(f.get("water_pct"), f.get("kbw30_percentile"))
    if score is None:
        return OverallStatus(level="no_data", score=None, headline="Brak danych do oceny stanu wody",
                             summary="Nie udało się policzyć wody w glebie – brak danych pogodowych lub glebowych.",
                             scope=scope, scope_label=SCOPE_LABELS[scope])
    level = status_for(score, sensitive=scope == "bez_uprawy")  # poza sezonem najwyżej „risk”
    headline = (HEADLINES_FIELD if scope == "bez_uprawy" else HEADLINES_OTHER)[level]
    lower, of = f.get("water_rank_lower"), f.get("water_rank_of")
    below_usual = bool(of) and lower is not None and lower < of / 2
    if level == "warn" and not below_usual:
        headline = "Uwaga – zapas wody w glebie niepełny"
    elif level == "warn" and scope == "poza_sezonem":
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
    if f.get("phase") in OFF_SEASON_PHASES:
        return reserve_status(f, "poza_sezonem")
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
    # „niż zwykle” tylko, gdy dane to potwierdzają (bilans poniżej średniej z 10 lat)
    if not sensitive and level == "warn" and not ((f.get("balance_deviation_mm") or 0) < 0):
        headline = "Uwaga – zapas wody w glebie niepełny"
    return OverallStatus(level=level, score=score, headline=headline, summary=summary_sentence(f),
                         scope="sezon", scope_label=SCOPE_LABELS["sezon"])
