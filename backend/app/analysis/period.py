"""Okres / zakres dat analizy (A9b, D100): ile spadło i wyparowało w wybranym okresie i jak to wypada na tle 10 lat.

`period=30d|since_sowing|season` albo `date_from` + `date_to`. Opad – ta sama seria co model (stacje IMGW, D83),
ET0 – FAO-56 z NASA POWER. Dane tylko sprzed daty analizy (koniec okresu ≤ ostatni dzień z danymi).
`normal_balance_mm` – średni bilans (opad − ET0) tego samego okresu w 10 poprzednich latach; `percentile` – w ilu
procentach tych lat było suszej (niższy bilans) niż teraz. Zdanie z liczb, bez AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from app.analysis.et0 import DailyWeather
from app.analysis.water_balance import last_usable_day, shift_years
from app.core.format import date_pl, num
from app.schemas.analysis import PeriodDay, PeriodSummary

PRESETS = ("30d", "since_sowing", "season")
MIN_VALID = 0.9  # rok porównawczy liczy się, gdy ma ≥ 90% dni z danymi


class PeriodError(ValueError):
    """Zły okres – komunikat po polsku (HTTP 422)."""


@dataclass
class Window:
    kind: str           # 30d | since_sowing | season | custom
    start: date
    end: date


def sowing_date(crop, analysis_date: date) -> date | None:
    """Ostatni typowy siew przed datą analizy: oziminy – siew jesienny (crops.csv `typowy_siew`), reszta – siew
    wiosenny (`start_wegetacji`); gdy w tym roku jeszcze nie było – rok wcześniej."""
    if crop is None:
        return None
    md = crop.autumn_sowing if crop.kind == "ozima" and crop.autumn_sowing else crop.start
    d = date(analysis_date.year, *md)
    return d if d < analysis_date else date(analysis_date.year - 1, *md)


def resolve(preset: str | None, date_from: date | None, date_to: date | None, analysis_date: date,
            sowing: date | None) -> Window | None:
    """Okres z parametrów zapytania (walidacja); brak parametrów → None (pole `period` nieobecne)."""
    if preset is None and date_from is None and date_to is None:
        return None
    if preset is not None and (date_from or date_to):
        raise PeriodError("Podaj okres (period) albo zakres dat (date_from, date_to) – nie oba naraz.")
    last = last_usable_day(analysis_date)
    if preset is not None:
        if preset not in PRESETS:
            raise PeriodError("Okres: 30d, since_sowing albo season.")
        if preset == "30d":
            return Window("30d", last - timedelta(days=29), last)
        if preset == "since_sowing":
            if sowing is None:
                raise PeriodError("Okres „od siewu” wymaga wybranej uprawy (parametr crop).")
            return Window("since_sowing", sowing, last)
        y = analysis_date.year
        return Window("season", date(y, 4, 1), min(date(y, 9, 30), last))
    if date_from is None or date_to is None:
        raise PeriodError("Zakres dat wymaga obu końców: date_from i date_to.")
    if date_to > analysis_date:
        raise PeriodError("Koniec zakresu (date_to) nie może być późniejszy niż data analizy.")
    if date_from > date_to:
        raise PeriodError("Początek zakresu (date_from) jest po jego końcu (date_to).")
    return Window("custom", date_from, min(date_to, last))


def _sums(w: DailyWeather, start: date, end: date) -> tuple[float, float, float] | None:
    i0 = int((np.datetime64(start, "D") - w.dates[0]).astype(int))
    i1 = int((np.datetime64(end, "D") - w.dates[0]).astype(int))
    if i0 < 0 or i1 >= len(w.dates) or i1 < i0:
        return None
    p, e = w.precip[i0:i1 + 1], w.et0[i0:i1 + 1]
    ok = ~np.isnan(p) & ~np.isnan(e)
    if ok.mean() < MIN_VALID:
        return None
    return float(np.nansum(p)), float(np.nansum(e)), float(np.nansum(p - e))


def _label(win: Window) -> str:
    same_year = win.start.year == win.end.year
    span = (f"{win.start:%d.%m}–{date_pl(win.end)}" if same_year else f"{date_pl(win.start)}–{date_pl(win.end)}")
    return {"30d": f"Ostatnie 30 dni ({span})", "since_sowing": f"Od siewu ({span})",
            "season": f"Sezon {win.start.year} ({span})", "custom": span}[win.kind]


def _prefix(win: Window) -> str:
    return {"30d": "W ostatnich 30 dniach", "since_sowing": "Od siewu", "season": "W sezonie od 1 kwietnia",
            "custom": f"Od {date_pl(win.start)} do {date_pl(win.end)}"}[win.kind]


def sentence(win: Window, p: float, e: float, b: float, normal: float | None, prev: list[float]) -> str:
    txt = f"{_prefix(win)} spadło {num(p, 0)} mm, wyparowało {num(e, 0)} mm"
    if normal is None or not prev:
        return txt + (f" – zostało {num(b, 0)} mm wody." if b >= 0 else f" – brakuje {num(-b, 0)} mm wody.")
    diff = b - normal
    if abs(diff) < 5:
        txt += " – bilans jak zwykle o tej porze."
    else:
        txt += f" – zostało o {num(abs(diff), 0)} mm {'mniej' if diff < 0 else 'więcej'} niż zwykle."
    n = len(prev)
    if diff < 0:
        k = sum(1 for x in prev if x <= b)
        txt += (f" Tak sucho było w {k} z {n} ostatnich lat." if k else
                f" Tak sucho nie było w żadnym z {n} ostatnich lat.")
    elif diff >= 5:
        k = sum(1 for x in prev if x >= b)
        txt += (f" Tak mokro było w {k} z {n} ostatnich lat." if k else
                f" Tak mokro nie było w żadnym z {n} ostatnich lat.")
    return txt


def build(w: DailyWeather, win: Window, years: int = 10, stress_dates: list[date] | None = None,
          has_crop: bool = False) -> PeriodSummary:
    """Podsumowanie okresu; koniec przycięty do ostatniego dnia z danymi pogodowymi."""
    last_data = None
    ok = ~np.isnan(w.precip) & ~np.isnan(w.et0)
    if ok.any():
        last_data = w.dates[np.flatnonzero(ok)[-1]].astype(object)
    end = min(win.end, last_data) if last_data else win.end
    if end < win.start:
        raise PeriodError("Brak danych pogodowych w wybranym okresie.")
    start = end - timedelta(days=29) if win.kind == "30d" else win.start  # „30 dni” = 30 dni z danymi
    win = Window(win.kind, start, end)
    cur = _sums(w, win.start, win.end)
    if cur is None:
        raise PeriodError("Za mało danych pogodowych w wybranym okresie (przed datą analizy).")
    p, e, b = cur
    prev = []
    for k in range(1, years + 1):
        s = _sums(w, shift_years(win.start, k), shift_years(win.end, k))
        if s is not None:
            prev.append(s[2])
    normal = float(np.mean(prev)) if prev else None
    pct = round(100 * sum(1 for x in prev if x < b) / len(prev)) if prev else 0
    daily, cum = [], 0.0
    i0 = int((np.datetime64(win.start, "D") - w.dates[0]).astype(int))
    for k in range((win.end - win.start).days + 1):
        pd_, ed = float(w.precip[i0 + k]), float(w.et0[i0 + k])
        pd_ = 0.0 if np.isnan(pd_) else pd_
        ed = 0.0 if np.isnan(ed) else ed
        cum += pd_ - ed
        daily.append(PeriodDay(date=win.start + timedelta(days=k), precip_mm=round(pd_, 1), et0_mm=round(ed, 1),
                               balance_cum_mm=round(cum, 1)))
    stress = (sum(1 for d in stress_dates if win.start <= d <= win.end) if has_crop and stress_dates is not None
              else None)
    return PeriodSummary(**{"from": win.start}, to=win.end, label=_label(win), precip_mm=round(p), et0_mm=round(e),
                         balance_mm=round(b), normal_balance_mm=round(normal) if normal is not None else 0,
                         percentile=pct, sentence=sentence(win, p, e, b, normal, prev), stress_days=stress, daily=daily)
