"""Okresy bez opadu, upał i próchnica (A24) – przyczyny wymienione w „Podstawach naukowych” KOWR: dane meteo to opady,
temperatura i DŁUGOŚĆ OKRESÓW BEZOPADOWYCH; najczęstsza przyczyna niedoboru to deficyt opadów z wysoką temperaturą;
próchnica poprawia pojemność wodną gleby.

Wszystko liczone z danych, których już używamy (bez nowych źródeł):
- okres bez opadu – z dziennej serii opadu analizy (stacje IMGW / NASA / Open-Meteo): ciąg dni z opadem < 1 mm,
- upał – temperatura maksymalna dobowa z NASA POWER (T2M_MAX): dni ≥ 30°C i ≥ 25°C,
- próchnica – węgiel organiczny 0–30 cm z SoilGrids (średnia ważona głębokością) × 1,72.
To pozycje INFORMACYJNE: nie zmieniają policzonego bilansu wody ani WOD (upał działa w bilansie tylko przez parowanie).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import numpy as np

from app.analysis.et0 import DailyWeather
from app.analysis.water_balance import shift_years
from app.core.format import num
from app.schemas.analysis import DrySpellStats, Heat, OrganicMatter, SourceTag

DRY_DAY_MM = 1.0        # dzień „bez opadu”: opad < 1 mm
LONG_SPELL_DAYS = 10    # liczymy też, ile było ciągów co najmniej tak długich
HOT_C = 30.0            # dzień upalny
WARM_C = 25.0           # dzień gorący
VERDICT_SPELL_DAYS = 14  # od tylu dni zdanie o okresie bez deszczu trafia do punktu „Opady” werdyktu
MIN_VALID = 0.8         # okno roku porównawczego: co najmniej 80% dni z danymi
SOC_TO_HUMUS = 1.72     # próchnica ≈ węgiel organiczny × 1,72 (współczynnik van Bemmelena)
# Klasy zawartości próchnicy w glebach mineralnych – progi z treści zadania A24 (orientacyjne klasy stosowane
# w polskim doradztwie rolniczym; do weryfikacji z agronomem): < 1% bardzo niska, 1–2% niska, 2–3,5% średnia, > 3,5% wysoka
HUMUS_CLASSES = [(1.0, "bardzo_niska", "bardzo niska"), (2.0, "niska", "niska"), (3.5, "srednia", "średnia"),
                 (float("inf"), "wysoka", "wysoka")]
LIMITATION = "Upał i okresy bez deszczu pokazujemy informacyjnie – model plonu uwzględnia je tylko przez parowanie."
HUMUS_CAUSE = "Gleba uboga w próchnicę słabiej trzyma wodę."
# Kontrola 22.11.2026: w 56 punktach w Polsce SoilGrids podaje 19–61 g/kg węgla (próchnica 3,3–10,5%) – ani razu klasy
# „niska”, także na piaskach; model globalny wygląda na zawyżony dla gleb ornych, dlatego jawne zastrzeżenie
HUMUS_LIMITATION = ("Próchnica to szacunek modelu globalnego SoilGrids (siatka ok. 250 m) – w naszych sprawdzeniach "
                    "wychodzi wyższa, niż zwykle mają gleby orne; traktuj ją orientacyjnie, pewną wartość da badanie gleby.")


def season_window(last: date) -> tuple[date, date]:
    """Sezon: od 1 marca do daty analizy (najdalej do 31 października); przed 1 marca – sezon poprzedniego roku."""
    y = last.year if last >= date(last.year, 3, 1) else last.year - 1
    return date(y, 3, 1), min(last, date(y, 10, 31))


def _slice(w: DailyWeather, arr: np.ndarray, start: date, end: date) -> np.ndarray | None:
    i0 = int((np.datetime64(start, "D") - w.dates[0]).astype(int))
    i1 = int((np.datetime64(end, "D") - w.dates[0]).astype(int))
    if i0 < 0 or i1 >= len(w.dates) or i1 < i0:
        return None
    return arr[i0:i1 + 1]


def longest_dry_run(precip: np.ndarray) -> tuple[int, int, int]:
    """(długość najdłuższego ciągu dni z opadem < 1 mm, indeks jego początku, liczba ciągów ≥ 10 dni).
    Dzień bez danych (NaN) przerywa ciąg."""
    best, best_start, run, run_start, long_runs = 0, 0, 0, 0, 0
    for i, v in enumerate(precip):
        if not np.isnan(v) and v < DRY_DAY_MM:
            if run == 0:
                run_start = i
            run += 1
            if run > best:
                best, best_start = run, run_start
        else:
            long_runs += run >= LONG_SPELL_DAYS
            run = 0
    long_runs += run >= LONG_SPELL_DAYS
    return best, best_start, long_runs


def dry_spell(w: DailyWeather, start: date, end: date, years: int = 10) -> DrySpellStats | None:
    """Najdłuższy okres bez opadu w oknie [start, end] i to samo okno w `years` poprzednich latach."""
    cur = _slice(w, w.precip, start, end)
    if cur is None or len(cur) == 0 or np.isnan(cur).mean() > 1 - MIN_VALID:
        return None
    n, i0, long_runs = longest_dry_run(cur)
    d0 = start + timedelta(days=i0)
    d1 = d0 + timedelta(days=max(0, n - 1))
    prev = []
    for k in range(1, years + 1):
        p = _slice(w, w.precip, shift_years(start, k), shift_years(end, k))
        if p is not None and len(p) and np.isnan(p).mean() <= 1 - MIN_VALID:
            prev.append(longest_dry_run(p)[0])
    usual = int(round(float(np.median(prev)))) if prev else None
    longer = sum(1 for x in prev if x > n) if prev else None
    txt = f"Najdłuższy okres bez deszczu: {n} dni ({d0:%d.%m}–{d1:%d.%m})" if n else "Nie było dni bez deszczu"
    if usual is not None and n:
        of = len(prev)
        tail = (f"tak długiego nie było w żadnym z {of} lat" if longer == 0 else
                f"dłuższy był tylko w {longer} z {of} lat" if longer <= 2 else f"dłuższy był w {longer} z {of} lat")
        txt += f", zwykle {usual} – {tail}"
    return DrySpellStats(window_from=start, window_to=end, longest_days=n, longest_from=d0 if n else None,
                    longest_to=d1 if n else None, spells_10d=long_runs, usual_days=usual, longer_in_years=longer,
                    of_years=len(prev), sentence=txt + ".",
                    source_tag=SourceTag(kind="obliczenia", date=end, source=w.source))


def heat(w: DailyWeather, start: date, end: date, years: int = 10, crop=None, crop_label: str | None = None) -> Heat | None:
    """Dni z Tmax ≥ 30°C i ≥ 25°C w oknie, mediana z poprzednich lat; dla uprawy – ile dni upalnych w fazie wrażliwej."""
    cur = _slice(w, w.tmax, start, end)
    if cur is None or len(cur) == 0 or np.isnan(cur).mean() > 1 - MIN_VALID:
        return None
    d30, d25 = int((cur >= HOT_C).sum()), int((cur >= WARM_C).sum())
    p30, p25 = [], []
    for k in range(1, years + 1):
        p = _slice(w, w.tmax, shift_years(start, k), shift_years(end, k))
        if p is not None and len(p) and np.isnan(p).mean() <= 1 - MIN_VALID:
            p30.append(int((p >= HOT_C).sum()))
            p25.append(int((p >= WARM_C).sum()))
    u30 = int(round(float(np.median(p30)))) if p30 else None
    u25 = int(round(float(np.median(p25)))) if p25 else None
    sens, phase_label = None, None
    if crop is not None:
        from app.analysis.crops import PHASE_LABELS

        hot_days = [start + timedelta(days=int(i)) for i in np.flatnonzero(cur >= HOT_C)]
        infos = [crop.day_info(d) for d in hot_days]
        sens_infos = [i for i in infos if i.sensitive]
        sens = len(sens_infos)
        if sens_infos:
            phase = Counter(i.phase for i in sens_infos).most_common(1)[0][0]
            phase_label = PHASE_LABELS.get(phase, phase)
    if d30:
        txt = f"Upał: {d30} dni powyżej 30°C" + (f" (zwykle {u30})" if u30 is not None else "")
        if sens:
            txt += (f", w tym {sens} w fazie wrażliwej uprawy ({(crop_label or '').lower()}: {phase_label}) – upał w tej "
                    "fazie może obniżyć plon ponad to, co pokazuje bilans wody")
    else:
        txt = "Upał: bez dni powyżej 30°C" + (f" (zwykle {u30})" if u30 is not None else "")
    txt += f"; dni powyżej 25°C: {d25}" + (f" (zwykle {u25})" if u25 is not None else "")
    return Heat(window_from=start, window_to=end, days_30=d30, days_25=d25, usual_days_30=u30, usual_days_25=u25,
                of_years=len(p30), sensitive_days_30=sens, sensitive_phase_label=phase_label, sentence=txt + ".",
                source_tag=SourceTag(kind="obliczenia", date=end, source="NASA POWER (temperatura maksymalna)"))


def organic_matter(soc_g_kg: float | None) -> OrganicMatter | None:
    """Próchnica [%] z węgla organicznego SoilGrids [g/kg]: SOC × 1,72 / 10; klasa wg HUMUS_CLASSES."""
    if soc_g_kg is None or not np.isfinite(soc_g_kg) or soc_g_kg <= 0:
        return None
    pct = round(soc_g_kg * SOC_TO_HUMUS / 10.0, 1)
    key, label = next((k, lab) for lim, k, lab in HUMUS_CLASSES if pct < lim or lim == float("inf"))
    return OrganicMatter(value_pct=pct, class_key=key, class_label=label,
                         sentence=f"Próchnica: ok. {num(pct, 1)}% ({label}) – szacunek SoilGrids, siatka ok. 250 m.",
                         source_tag=SourceTag(kind="szacunek_modelu", source="SoilGrids (ISRIC) – węgiel organiczny 0–30 cm × 1,72"))


def rule_facts(dry: DrySpellStats | None, hot: Heat | None, om: OrganicMatter | None) -> dict:
    """Fakty dla przyczyn i reguł rekomendacji."""
    low = om is not None and om.class_key in ("bardzo_niska", "niska")
    return {
        "dry_spell_days": dry.longest_days if dry else None,
        "dry_spell_cause": dry.sentence if dry and dry.longest_days else None,
        "heat_days_30": hot.days_30 if hot else None,
        "heat_cause": hot.sentence if hot else None,
        "humus_pct": om.value_pct if om else None,
        "humus_pct_txt": num(om.value_pct, 1) if om else None,
        "humus_class": om.class_key if om else None,
        "humus_class_label": om.class_label if om else None,
        "humus_cause": (f"{HUMUS_CAUSE} Próchnica: ok. {num(om.value_pct, 1)}% ({om.class_label}) – szacunek SoilGrids."
                        if low else None),
    }
