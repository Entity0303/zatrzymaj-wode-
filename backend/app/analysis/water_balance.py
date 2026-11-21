"""Bilans wody: KBW = opad − ET0, bilans narastająco od początku sezonu, pasmo z 10 lat.

Buduje sekcję `history` kontraktu /api/analysis (schemas/analysis.py: History) oraz metryki,
których kontrakt nie przewiduje (odchylenie od średniej, percentyl, najdłuższa susza
opadowa, lata porównawcze – od rozszerzenia kontraktu także w `History`; dane do dnia X,
ograniczenia) – w `WaterBalanceResult`.

Zasady:
- tylko dane SPRZED daty analizy (ostatni dzień = data analizy − 1),
- sezon domyślnie od 1 marca; gdy ostatni dzień z danymi jest przed 1 marca – od 1 marca
  roku poprzedniego (D14),
- pasmo porównawcze: ten sam okres (dzień sezonu) w każdym z `years` poprzednich lat,
- brak danych nie udaje pełności: opóźnienie źródła → „dane pogodowe do dnia X”,
  dni bez danych → ograniczenie; dni stresu wypełni model wody w glebie (A3) – tu pusto.
Wszystko wektorowo; pętle tylko po latach (≤ 10) i miesiącach (≤ 12).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from app.analysis.et0 import DailyWeather
from app.schemas.analysis import BalanceRank, BandPoint, DrySpell, History, MonthlyPrecip, SeriesPoint, SourceTag

MAX_MISSING_YEAR = 0.10  # rok porównawczy z większym udziałem braków pomijamy
MAX_MISSING_MONTH = 0.20  # miesiąc z większym udziałem braków = brak sumy
DRY_DAY_MM = 1.0  # dzień „bez opadu” = opad < 1 mm

_MONTHS_GEN = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
]


# ── Daty ────────────────────────────────────────────────────────────────────────────────────


def last_usable_day(analysis_date: date) -> date:
    """Ostatni dzień, którego dane wolno użyć (dane sprzed daty analizy)."""
    return analysis_date - timedelta(days=1)


def default_season_start(analysis_date: date) -> date:
    last = last_usable_day(analysis_date)
    start = date(last.year, 3, 1)
    return start if last >= start else date(last.year - 1, 3, 1)


def history_range(analysis_date: date, season_start: date | None = None, years: int = 10) -> tuple[date, date]:
    """Zakres danych do pobrania: od 1 stycznia (rok początku sezonu − years) do dnia przed analizą."""
    s = season_start or default_season_start(analysis_date)
    return date(s.year - years, 1, 1), last_usable_day(analysis_date)


def shift_years(d: date, k: int) -> date:
    try:
        return d.replace(year=d.year - k)
    except ValueError:  # 29 lutego
        return d.replace(year=d.year - k, day=28)


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def format_date_pl(d: date, with_year: bool = True) -> str:
    return f"{d.day} {_MONTHS_GEN[d.month - 1]}" + (f" {d.year}" if with_year else "")


def format_mm(v: float, signed: bool = True) -> str:
    s = f"{abs(v):.0f}"
    if signed and round(v) < 0:
        return f"−{s}"
    if signed and round(v) > 0:
        return f"+{s}"
    return s


def _r1(v: float | None) -> float | None:
    return None if v is None or np.isnan(v) else round(float(v), 1)


# ── Wynik ───────────────────────────────────────────────────────────────────────────────────


@dataclass
class WaterBalanceResult:
    history: History
    season_start: date
    data_until: date | None  # ostatni dzień z kompletem opadu i ET0
    requested_until: date  # dzień przed datą analizy
    current_balance_mm: float | None = None
    mean_balance_mm: float | None = None
    deviation_mm: float | None = None  # bieżący − średnia z lat porównawczych
    percentile: float | None = None  # % lat porównawczych z NIŻSZYM bilansem (0 = najgorszy)
    lower_years: int | None = None  # ile lat miało niższy bilans
    band_years: list[int] = field(default_factory=list)
    excluded_years: list[int] = field(default_factory=list)
    longest_dry_spell_days: int | None = None
    longest_dry_spell_end: date | None = None
    missing_days_season: int = 0
    et0_methods_season: dict[str, int] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


# ── Obliczenia ──────────────────────────────────────────────────────────────────────────────


def _idx(w: DailyWeather, d: date) -> int:
    """Indeks dnia w serii (może być < 0 lub ≥ len – poza zakresem)."""
    return int((np.datetime64(d, "D") - w.dates[0]).astype(int))


def _dates(w: DailyWeather, i0: int, i1: int) -> list[date]:
    return list(w.dates[i0 : i1 + 1].astype(object))


def longest_run(mask: np.ndarray) -> tuple[int, int]:
    """Najdłuższy ciąg True: (długość, indeks ostatniego dnia) – bez pętli po dniach."""
    if not mask.any():
        return 0, -1
    padded = np.concatenate(([0], mask.astype(np.int8), [0]))
    edges = np.diff(padded)
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    lengths = ends - starts
    k = int(np.argmax(lengths))
    return int(lengths[k]), int(ends[k] - 1)


def _segment(arr: np.ndarray, i0: int, n: int) -> np.ndarray | None:
    if i0 < 0 or i0 + n > len(arr):
        return None
    return arr[i0 : i0 + n]


def build_history(
    w: DailyWeather,
    analysis_date: date,
    season_start: date | None = None,
    years: int = 10,
) -> WaterBalanceResult:
    end = last_usable_day(analysis_date)
    s0 = season_start or default_season_start(analysis_date)
    kbw = w.climatic_water_balance
    tag_source = w.source
    limitations: list[str] = []

    # ostatni dzień z kompletem danych (opad i ET0), nie później niż `end`
    i_req = min(_idx(w, end), len(w.dates) - 1)
    valid_idx = np.flatnonzero(~np.isnan(kbw[: i_req + 1])) if i_req >= 0 else np.array([], dtype=int)
    data_until = w.dates[valid_idx[-1]].astype(object) if valid_idx.size else None
    i_s0 = _idx(w, s0)

    def empty(reason: str) -> WaterBalanceResult:
        limitations.append(reason)
        hist = History(
            period_start=w.dates[0].astype(object) if len(w.dates) else s0,
            period_end=data_until or end,
            season_start=s0,
            balance_cumulative=[],
            balance_band=[],
            stress_days_by_year=[],
            monthly_precip=[],
            summary=None,
            source_tag=SourceTag(kind="brak_danych", date=None, source=tag_source),
        )
        return WaterBalanceResult(hist, s0, data_until, end, limitations=limitations)

    if data_until is None or i_s0 < 0 or data_until < s0:
        return empty(f"Brak danych pogodowych od początku sezonu ({format_date_pl(s0)}).")

    lag = (end - data_until).days
    if lag > 0:
        limitations.append(
            f"Dane pogodowe do dnia {data_until:%d.%m.%Y} (źródło publikuje je z opóźnieniem {lag} dni) "
            "– bilans liczony do tej daty."
        )

    # ── bieżący sezon ──
    i_e = _idx(w, data_until)
    n = i_e - i_s0 + 1
    cur = kbw[i_s0 : i_e + 1]
    cur_p = w.precip[i_s0 : i_e + 1]
    missing = int(np.isnan(cur).sum())
    if missing:
        limitations.append(f"{missing} dni bez danych pogodowych w sezonie – w bilansie przyjęto je jako 0 mm.")
    cum = np.nancumsum(cur)
    season_mask = np.zeros(len(w.dates), dtype=bool)
    season_mask[i_s0 : i_e + 1] = True
    season_methods = w.method_counts(season_mask)
    if season_methods["HG"]:
        limitations.append(
            f"Parowanie dla {season_methods['HG']} dni liczone uproszczoną metodą Hargreavesa "
            "(brak promieniowania, wilgotności lub wiatru)."
        )

    # ── pasmo z poprzednich lat (ten sam dzień sezonu) ──
    rows: list[np.ndarray] = []
    band_years: list[int] = []
    excluded: list[int] = []
    year_offsets: list[int] = []
    for k in range(1, years + 1):
        seg = _segment(kbw, _idx(w, shift_years(s0, k)), n)
        label = s0.year - k
        if seg is None or np.isnan(seg).mean() > MAX_MISSING_YEAR:
            excluded.append(label)
            continue
        rows.append(seg)
        band_years.append(label)
        year_offsets.append(k)
    if excluded:
        limitations.append(
            "Pominięto w porównaniu lata z niepełnymi danymi: " + ", ".join(str(y) for y in sorted(excluded)) + "."
        )

    series_dates = _dates(w, i_s0, i_e)
    balance_cumulative = [SeriesPoint(date=d, value=_r1(v)) for d, v in zip(series_dates, cum)]
    balance_band: list[BandPoint] = []
    current_total = float(cum[-1])
    mean_total = deviation = percentile = None
    lower_years = None
    if rows:
        c = np.nancumsum(np.vstack(rows), axis=1)
        bmin, bmax, bmean = c.min(axis=0), c.max(axis=0), c.mean(axis=0)
        balance_band = [
            BandPoint(date=d, min=_r1(a), max=_r1(b), mean=_r1(m))
            for d, a, b, m in zip(series_dates, bmin, bmax, bmean)
        ]
        totals = c[:, -1]
        mean_total = float(totals.mean())
        deviation = current_total - mean_total
        lower_years = int((totals < current_total).sum())
        percentile = 100.0 * lower_years / len(totals)

    # ── opady miesięczne: bieżący sezon vs średnia z lat porównawczych (te same dni miesiąca) ──
    monthly: list[MonthlyPrecip] = []
    m = date(s0.year, s0.month, 1)
    while m <= data_until:
        a, b = max(m, s0), min(_month_end(m), data_until)
        seg = w.precip[_idx(w, a) : _idx(w, b) + 1]
        current_mm = None if np.isnan(seg).mean() > MAX_MISSING_MONTH else float(np.nansum(seg))
        sums = []
        for k in year_offsets:
            ia, ib = _idx(w, shift_years(a, k)), _idx(w, shift_years(b, k))
            seg_k = _segment(w.precip, ia, ib - ia + 1)
            if seg_k is not None and np.isnan(seg_k).mean() <= MAX_MISSING_MONTH:
                sums.append(float(np.nansum(seg_k)))
        monthly.append(
            MonthlyPrecip(month=m.month, current_mm=_r1(current_mm), mean_mm=_r1(np.mean(sums)) if sums else None)
        )
        m = _month_end(m) + timedelta(days=1)

    # ── najdłuższy okres bez opadu (opad < 1 mm; brak danych przerywa ciąg) ──
    dry_len, dry_end_i = longest_run(np.nan_to_num(cur_p, nan=np.inf) < DRY_DAY_MM)
    dry_end = series_dates[dry_end_i] if dry_len else None

    # ── podsumowanie – wyłącznie z policzonych liczb ──
    summary = (
        f"Od {format_date_pl(s0, with_year=False)} do {format_date_pl(data_until)} bilans wody "
        f"(opad − parowanie) wynosi {format_mm(current_total)} mm."
    )
    if mean_total is not None and deviation is not None and lower_years is not None:
        more_less = "mniej" if deviation < 0 else "więcej"
        summary += (
            f" Średnio w tym okresie w latach {min(band_years)}–{max(band_years)}: {format_mm(mean_total)} mm"
            f" – o {format_mm(deviation, signed=False)} mm {more_less} niż zwykle."
            f" Niższy bilans był w {lower_years} z {len(band_years)} lat."
        )

    history = History(
        period_start=w.dates[0].astype(object),
        period_end=data_until,
        season_start=s0,
        balance_cumulative=balance_cumulative,
        balance_band=balance_band,
        stress_days_by_year=[],  # wypełni model wody w glebie (zadanie A3) – nie zgadujemy
        monthly_precip=monthly,
        summary=summary,
        balance_deviation_mm=_r1(deviation),
        balance_rank=BalanceRank(lower_years=lower_years, of_years=len(band_years)) if lower_years is not None else None,
        longest_dry_spell=DrySpell(days=dry_len, end_date=dry_end),
        band_years=band_years,
        source_tag=SourceTag(kind="obliczenia", date=data_until, source=tag_source),
    )
    return WaterBalanceResult(
        history=history,
        season_start=s0,
        data_until=data_until,
        requested_until=end,
        current_balance_mm=_r1(current_total),
        mean_balance_mm=_r1(mean_total),
        deviation_mm=_r1(deviation),
        percentile=_r1(percentile),
        lower_years=lower_years,
        band_years=band_years,
        excluded_years=sorted(excluded),
        longest_dry_spell_days=dry_len,
        longest_dry_spell_end=dry_end,
        missing_days_season=missing,
        et0_methods_season=season_methods,
        limitations=limitations,
    )
