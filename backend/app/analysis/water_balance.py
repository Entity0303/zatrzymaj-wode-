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

from app.analysis.crops import Crop
from app.analysis.et0 import DailyWeather
from app.schemas.analysis import (
    BalanceRank,
    BandPoint,
    DrySpell,
    Evidence,
    History,
    Indicator,
    MonthlyPrecip,
    Recommendation,
    RiskIndicator,
    SeriesPoint,
    SourceTag,
    YearStress,
)

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
    """Zakres danych do pobrania: od 1 listopada (rok początku sezonu − years − 1) do dnia przed analizą.

    Listopad–grudzień przed najstarszym sezonem porównawczym jest potrzebny do zapasu wody na start
    sezonu w modelu FAO-56 (okno zimowe, D28)."""
    s = season_start or default_season_start(analysis_date)
    return date(s.year - years - 1, 11, 1), last_usable_day(analysis_date)


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


# ═══════════════════════════════════════════════════════════════════════════════════════════
# Model wody w glebie FAO-56 („wiadro” strefy korzeniowej) – A3
# ═══════════════════════════════════════════════════════════════════════════════════════════
#
# Dr – ubytek wody w strefie korzeniowej [mm] (0 = pojemność polowa, TAW = punkt więdnięcia).
# FAO-56 rozdz. 8: Dr,i = Dr,i−1 − (P − RO)i + Ks·Kc·ET0,i ; Dr < 0 → przesiąkanie (DP), Dr = 0.
# Ks = 1 gdy Dr ≤ RAW, inaczej (TAW − Dr)/(TAW − RAW) (równanie 84). Stres = Dr > RAW.

PROFILE_DEPTH_M = 1.0  # WOD z IUNG odnosi się do profilu ok. 1 m (D25)
RUNOFF_THRESHOLD_MM = 20.0  # spływ: 20% części opadu powyżej 20 mm/dzień (D26) –
RUNOFF_FRACTION = 0.20  # parametry do nadpisania przez analizę terenu (NMT)
HORIZON_DAYS = 16  # „stres za X dni” – tyle dni ma prognoza Open-Meteo
RISK_HIGH_DAYS = 3  # przekroczenie RAW w ≤ 3 dni (lub już) → wysokie (D27)
RISK_MEDIUM_DAYS = 7  # 4–7 dni → średnie; później / wcale w 16 dniach → niskie
MODEL_SOURCE = "Model wody w glebie FAO-56"


def taw_from_wod(wod_mm: float, root_depth_m: float, profile_m: float = PROFILE_DEPTH_M) -> float:
    """TAW strefy korzeniowej: WOD (profil ~1 m) × min(Zr, 1 m) / 1 m – korzenie głębsze nie zwiększają (D25)."""
    return wod_mm * min(root_depth_m, profile_m) / profile_m


def effective_precip(
    p: np.ndarray, threshold: float = RUNOFF_THRESHOLD_MM, fraction: float = RUNOFF_FRACTION
) -> np.ndarray:
    """Opad efektywny = opad − spływ; spływ = fraction × (opad − threshold) dla opadu > threshold."""
    return p - fraction * np.maximum(p - threshold, 0.0)


def ks_coefficient(dr: float, taw: float, raw: float) -> float:
    """Współczynnik stresu wodnego Ks (FAO-56, równanie 84)."""
    if dr <= raw:
        return 1.0
    return max(0.0, (taw - dr) / (taw - raw)) if taw > raw else 0.0


@dataclass
class Run:
    dr: np.ndarray  # ubytek na koniec dnia [mm]
    ks: np.ndarray  # Ks użyte w danym dniu (ze stanu z początku dnia)
    eta: np.ndarray  # ETc skorygowane Ks [mm]
    dp: np.ndarray  # przesiąkanie poniżej strefy korzeniowej [mm]
    missing: int  # dni bez danych (stan bez zmian)
    raw: float

    @property
    def stress_days(self) -> int:
        """Dni stresu = dni, na których koniec Dr > RAW."""
        return int((self.dr > self.raw).sum())


def simulate(
    precip: np.ndarray,
    et0: np.ndarray,
    kc: np.ndarray,
    taw: float,
    raw: float,
    dr0: float,
    runoff_threshold: float = RUNOFF_THRESHOLD_MM,
    runoff_fraction: float = RUNOFF_FRACTION,
) -> Run:
    """Dzienny bilans FAO-56 (sekwencyjny – każdy dzień zależy od poprzedniego).

    Dzień z brakiem opadu lub ET0 (NaN) nie zmienia stanu i jest liczony w `missing`.
    """
    n = len(precip)
    pe = effective_precip(np.asarray(precip, float), runoff_threshold, runoff_fraction)
    etc = np.asarray(kc, float) * np.asarray(et0, float)
    dr_out, ks_out, eta_out, dp_out = np.empty(n), np.ones(n), np.zeros(n), np.zeros(n)
    dr, missing = min(max(dr0, 0.0), taw), 0
    for i in range(n):
        k = ks_coefficient(dr, taw, raw)
        ks_out[i] = k
        if np.isnan(pe[i]) or np.isnan(etc[i]):
            missing += 1
            dr_out[i] = dr
            continue
        eta = k * etc[i]
        dr = dr - pe[i] + eta
        dp = 0.0
        if dr < 0:
            dp, dr = -dr, 0.0
        dr = min(dr, taw)
        dr_out[i], eta_out[i], dp_out[i] = dr, eta, dp
    return Run(dr_out, ks_out, eta_out, dp_out, missing, raw)


def kc_series(crop: Crop, first_day: int, n: int) -> np.ndarray:
    """Kc dla kolejnych n dni sezonu od dnia `first_day` (NaN poza sezonem)."""
    vals = [crop.kc(first_day + i) for i in range(n)]
    return np.array([np.nan if v is None else v for v in vals], dtype=float)


def winter_window_start(season_start: date) -> date:
    """Okno bilansu przed sezonem: od 1 XI roku poprzedniego; dla siewu letnio-jesiennego od 1 VII (D28)."""
    return date(season_start.year - 1, 11, 1) if season_start.month <= 6 else date(season_start.year, 7, 1)


def initial_depletion(w: DailyWeather, season_start: date, taw: float) -> tuple[float, float | None, date]:
    """Zapas na start sezonu: profil pełny (Dr = 0), chyba że bilans P − ET0 w oknie przed startem jest
    ujemny – wtedy Dr0 = min(TAW, |bilans|) (D28). Zwraca (Dr0, bilans okna lub None przy brakach, okno)."""
    ws = winter_window_start(season_start)
    i0, i1 = _idx(w, ws), _idx(w, season_start) - 1
    seg = _segment(w.climatic_water_balance, i0, i1 - i0 + 1)
    if seg is None or np.isnan(seg).mean() > MAX_MISSING_MONTH:
        return 0.0, None, ws
    bal = float(np.nansum(seg))
    return float(min(taw, max(0.0, -bal))), round(bal, 1), ws


def round_dose(mm: float) -> int:
    """Dawka nawadniania do pojemności polowej, zaokrąglona do 5 mm (min. 5 mm)."""
    return int(max(5, 5 * round(mm / 5)))


SINGLE_DOSE_MAX_MM = 40  # większą dawkę w praktyce dzieli się na kilka zabiegów (D29)


def dose_hint(dose: int) -> str:
    return f" W praktyce w {-(-dose // 35)} dawkach po ok. 30–35 mm." if dose > SINGLE_DOSE_MAX_MM else ""


@dataclass
class HorizonDay:
    day: date
    precip: float
    et0: float


@dataclass
class Irrigation:
    needed: bool
    dose_mm: int | None = None
    when: date | None = None  # termin (nazwa pola ≠ typ `date`)
    text: str = "Nawadnianie niepotrzebne."


@dataclass
class SoilWaterResult:
    crop_id: str
    season_status: str  # "w_sezonie" | "przed_sezonem" | "po_sezonie" | "brak_danych"
    season_start: date
    season_end: date
    taw_mm: float
    raw_mm: float
    root_depth_m: float
    p: float
    data_until: date | None = None
    day_of_season: int | None = None
    stage: str | None = None
    kc: float | None = None
    dr0_mm: float | None = None
    winter_balance_mm: float | None = None
    winter_window_start: date | None = None
    dr_mm: float | None = None
    water_pct: float | None = None  # 1 − Dr/TAW, %
    water_mm: float | None = None  # TAW − Dr
    raw_exceeded: bool | None = None
    ks: float | None = None
    stress_days_season: int | None = None
    percolation_mm: float | None = None
    stress_by_year: list[tuple[int, int | None]] = field(default_factory=list)  # bieżący + poprzednie lata
    mean_prev_stress_days: float | None = None
    horizon_kind: str | None = None  # "prognoza" | "scenariusz"
    horizon_dr: list[tuple[date, float]] = field(default_factory=list)
    days_to_stress: int | None = None  # 0 = stres trwa; None = brak w horyzoncie
    risk: str | None = None  # "niskie" | "średnie" | "wysokie"
    irrigation: Irrigation | None = None
    limitations: list[str] = field(default_factory=list)


def risk_class(days_to_stress: int | None) -> str:
    if days_to_stress is not None and days_to_stress <= RISK_HIGH_DAYS:
        return "wysokie"
    if days_to_stress is not None and days_to_stress <= RISK_MEDIUM_DAYS:
        return "średnie"
    return "niskie"


def climatology_horizon(w: DailyWeather, start: date, n: int, years: int = 10) -> list[HorizonDay]:
    """Scenariusz typowej pogody: mediana opadu i ET0 z tych samych dni w `years` poprzednich latach."""
    out = []
    for k in range(n):
        d = start + timedelta(days=k)
        idx = [_idx(w, shift_years(d, y)) for y in range(1, years + 1)]
        idx = [i for i in idx if 0 <= i < len(w.dates)]
        p = float(np.nanmedian(w.precip[idx])) if idx and not np.isnan(w.precip[idx]).all() else np.nan
        e = float(np.nanmedian(w.et0[idx])) if idx and not np.isnan(w.et0[idx]).all() else np.nan
        out.append(HorizonDay(d, p, e))
    return out


def _previous_years_stress(
    w: DailyWeather, crop: Crop, season_year: int, n_days: int, taw: float, raw: float, years: int,
    runoff_threshold: float, runoff_fraction: float,
) -> tuple[list[tuple[int, int | None]], list[int]]:
    """Dni stresu w tych samych `n_days` dniach sezonu w każdym z `years` poprzednich lat."""
    kc = kc_series(crop, 0, n_days)
    out: list[tuple[int, int | None]] = []
    prev: list[int] = []
    for k in range(1, years + 1):
        sk = crop.season(season_year - k)[0]
        i0 = _idx(w, sk)
        p_k, e_k = _segment(w.precip, i0, n_days), _segment(w.et0, i0, n_days)
        if p_k is None or e_k is None or np.isnan(p_k + e_k).mean() > MAX_MISSING_YEAR:
            out.append((season_year - k, None))
            continue
        d0k, _, _ = initial_depletion(w, sk, taw)
        sd = simulate(p_k, e_k, kc, taw, raw, d0k, runoff_threshold, runoff_fraction).stress_days
        out.append((season_year - k, sd))
        prev.append(sd)
    return out, prev


def soil_water_model(
    w: DailyWeather,
    crop: Crop,
    wod_mm: float,
    analysis_date: date,
    forecast: list[HorizonDay] | None = None,
    years: int = 10,
    runoff_threshold: float = RUNOFF_THRESHOLD_MM,
    runoff_fraction: float = RUNOFF_FRACTION,
) -> SoilWaterResult:
    """Model wody w glebie dla uprawy na datę analizy (dane do dnia przed datą).

    `forecast` – dni z Open-Meteo (także ostatnie dni przed datą analizy, gdy źródło historyczne
    ma opóźnienie); None → scenariusz klimatologiczny (data historyczna lub brak prognozy).
    """
    end = last_usable_day(analysis_date)
    taw = taw_from_wod(wod_mm, crop.root_depth_m)
    raw = crop.p * taw
    s, e = crop.season(end.year)
    res = SoilWaterResult(crop.id, "brak_danych", s, e, round(taw, 1), round(raw, 1), crop.root_depth_m, crop.p)
    lim = res.limitations

    if end < s:
        res.season_status = "przed_sezonem"
        lim.append(f"Poza sezonem wegetacji tej uprawy (sezon w modelu: {s:%d.%m}–{e:%d.%m}).")
        return res

    kbw = w.climatic_water_balance
    i_req = min(_idx(w, min(end, e)), len(w.dates) - 1)
    valid = np.flatnonzero(~np.isnan(kbw[: i_req + 1])) if i_req >= 0 else np.array([], dtype=int)
    data_until = w.dates[valid[-1]].astype(object) if valid.size else None
    if data_until is None or data_until < s:
        lim.append("Brak danych pogodowych od początku sezonu uprawy.")
        return res
    res.data_until = data_until
    after = end > e
    res.season_status = "po_sezonie" if after else "w_sezonie"
    if after:
        lim.append(
            f"Poza sezonem wegetacji tej uprawy (sezon w modelu: {s:%d.%m}–{e:%d.%m}) – "
            "pokazujemy tylko podsumowanie zakończonego sezonu."
        )

    # ── bieżący sezon: od startu do ostatniego dnia z danymi ──
    n = (data_until - s).days + 1
    i_s = _idx(w, s)
    kc = kc_series(crop, 0, n)
    dr0, wbal, wstart = initial_depletion(w, s, taw)
    res.dr0_mm, res.winter_balance_mm, res.winter_window_start = round(dr0, 1), wbal, wstart
    if wbal is None:
        lim.append(f"Brak danych o bilansie przed sezonem (od {format_date_pl(wstart)}) – start z pełnym profilem.")
    elif dr0 > 0:
        lim.append(
            f"Przed sezonem (od {format_date_pl(wstart, with_year=False)}) bilans wody {format_mm(wbal)} mm – "
            f"start sezonu z niepełnym zapasem (ubytek {round(dr0)} mm)."
        )
    run = simulate(w.precip[i_s : i_s + n], w.et0[i_s : i_s + n], kc, taw, raw, dr0, runoff_threshold, runoff_fraction)
    if run.missing:
        lim.append(f"{run.missing} dni sezonu bez danych pogodowych – stan gleby w tych dniach bez zmian.")
    dr = float(run.dr[-1])
    res.stress_days_season = run.stress_days
    res.percolation_mm = round(float(run.dp.sum()), 1)

    def compare(n_days: int) -> None:
        prev_list, prev = _previous_years_stress(
            w, crop, s.year, n_days, taw, raw, years, runoff_threshold, runoff_fraction
        )
        res.stress_by_year = [(s.year, res.stress_days_season)] + prev_list
        res.mean_prev_stress_days = round(float(np.mean(prev)), 1) if prev else None
        if len(prev) < years:
            lim.append(f"Dni stresu porównane z {len(prev)} z {years} poprzednich lat (pozostałe – niepełne dane).")

    if after:
        compare(n)
        return res  # po sezonie: bez stanu „na dziś”, bez ryzyka i nawadniania

    # ── luka między ostatnim dniem z danymi a dniem przed analizą (opóźnienie źródła) ──
    gap_days = (end - data_until).days
    fc = {h.day: h for h in (forecast or [])}
    if gap_days > 0:
        bridge = [fc.get(data_until + timedelta(days=k + 1)) for k in range(gap_days)]
        if all(b is not None for b in bridge):
            note = f"Ostatnie {gap_days} dni przed datą analizy uzupełnione danymi modelu Open-Meteo."
        else:
            bridge = climatology_horizon(w, data_until + timedelta(days=1), gap_days, years)
            note = f"Ostatnie {gap_days} dni przed datą analizy bez danych – uzupełnione scenariuszem typowej pogody."
        rb = simulate(
            np.array([b.precip for b in bridge]),
            np.array([b.et0 for b in bridge]),
            kc_series(crop, n, gap_days),
            taw, raw, dr, runoff_threshold, runoff_fraction,
        )
        dr = float(rb.dr[-1])
        res.stress_days_season = (res.stress_days_season or 0) + rb.stress_days
        lim.append(note)
    compare((end - s).days + 1)  # ten sam okres co bieżący sezon, łącznie z uzupełnionymi dniami

    day = (end - s).days  # indeks dnia sezonu „wczoraj”
    today_idx = min(day + 1, crop.length - 1)
    res.day_of_season = day + 2  # numer dnia sezonu w dacie analizy (1 = start)
    res.stage = crop.stage(today_idx)
    res.kc = round(crop.kc(today_idx), 2)
    res.dr_mm = round(dr, 1)
    res.water_mm = round(taw - dr, 1)
    res.water_pct = round(100 * (1 - dr / taw)) if taw > 0 else None
    res.raw_exceeded = dr > raw
    res.ks = round(ks_coefficient(dr, taw, raw), 2)

    # ── horyzont 16 dni od daty analizy: prognoza (dziś) albo scenariusz (data historyczna) ──
    remaining = crop.length - (day + 1)
    h = max(0, min(HORIZON_DAYS, remaining))
    future = [fc[d] for d in (analysis_date + timedelta(days=k) for k in range(h)) if d in fc]
    if forecast and h and len(future) >= min(7, h):
        res.horizon_kind, horizon = "prognoza", future
    else:
        res.horizon_kind, horizon = "scenariusz", climatology_horizon(w, analysis_date, h, years)
    if horizon:
        rh = simulate(
            np.array([x.precip for x in horizon]),
            np.array([x.et0 for x in horizon]),
            kc_series(crop, day + 1, len(horizon)),
            taw, raw, dr, runoff_threshold, runoff_fraction,
        )
        res.horizon_dr = [(x.day, round(float(v), 1)) for x, v in zip(horizon, rh.dr)]
        over = np.flatnonzero(rh.dr > raw)
        res.days_to_stress = 0 if dr > raw else (int(over[0]) + 1 if over.size else None)
    else:
        res.days_to_stress = 0 if dr > raw else None
    res.risk = risk_class(res.days_to_stress)
    if h < HORIZON_DAYS:
        lim.append(f"Sezon uprawy kończy się za {h} dni – horyzont ryzyka skrócony.")

    # ── nawadnianie: RAW przekroczone teraz lub w ciągu 7 dni ──
    if dr > raw:
        dose = round_dose(dr)
        res.irrigation = Irrigation(
            True, dose, analysis_date,
            f"Nawadnianie ma sens od razu: dawka ok. {dose} mm (do pojemności polowej)." + dose_hint(dose),
        )
    elif res.days_to_stress is not None and res.days_to_stress <= RISK_MEDIUM_DAYS and res.horizon_dr:
        when_day, when_dr = res.horizon_dr[res.days_to_stress - 1]
        dose = round_dose(when_dr)
        res.irrigation = Irrigation(
            True, dose, when_day,
            f"Nawadnianie ma sens ok. {when_day:%d.%m}: dawka ok. {dose} mm, jeśli nie spadnie deszcz." + dose_hint(dose),
        )
    else:
        res.irrigation = Irrigation(False)
    return res


# ── Model → pola kontraktu ──────────────────────────────────────────────────────────────────

RISK_STATUS = {"niskie": "ok", "średnie": "warn", "wysokie": "risk"}


@dataclass
class ModelIndicators:
    soil_water_pct: Indicator
    soil_water_mm: Indicator
    risk_7d: RiskIndicator
    stress_days_by_year: list[YearStress]
    irrigation: Recommendation | None


def _no_model(note: str) -> tuple[Indicator, Indicator, RiskIndicator]:
    tag = SourceTag(kind="brak_danych", source=MODEL_SOURCE)
    return (
        Indicator(value=None, unit="%", status="no_data", note=note, source_tag=tag),
        Indicator(value=None, unit="mm", status="no_data", note=note, source_tag=tag),
        RiskIndicator(value=None, unit="dni", status="no_data", note=note, source_tag=tag),
    )


def to_contract_indicators(res: SoilWaterResult, crop: Crop, analysis_date: date) -> ModelIndicators:
    years = [YearStress(year=y, stress_days=d, is_current=(i == 0)) for i, (y, d) in enumerate(res.stress_by_year)]
    if res.season_status != "w_sezonie" or res.water_pct is None:
        note = res.limitations[0] if res.limitations else "Brak danych do modelu wody w glebie."
        pct, mm, risk = _no_model(note)
        return ModelIndicators(pct, mm, risk, years, None)

    tag = SourceTag(kind="szacunek_modelu", date=last_usable_day(analysis_date), source=MODEL_SOURCE)
    status = "risk" if res.raw_exceeded else ("warn" if res.risk == "średnie" else "ok")
    pct = Indicator(
        value=res.water_pct,
        unit="%",
        label="rośliny odczuwają brak wody" if res.raw_exceeded else None,
        status=status,
        note=f"{res.water_mm:.0f} z {res.taw_mm:.0f} mm wody dostępnej w strefie korzeni ({crop.root_depth_m:g} m)",
        source_tag=tag,
    )
    mm = Indicator(value=res.water_mm, unit="mm", status=status, note=f"próg stresu: ubytek > {res.raw_mm:.0f} mm", source_tag=tag)

    if res.horizon_kind == "prognoza":
        rtag = SourceTag(kind="prognoza", date=analysis_date, source="Open-Meteo + " + MODEL_SOURCE)
        base = ""
    else:
        rtag = SourceTag(kind="szacunek_modelu", date=analysis_date, source="scenariusz typowej pogody (10 lat)")
        base = " (scenariusz typowej pogody)"
    d = res.days_to_stress
    if d == 0:
        note = "rośliny już odczuwają brak wody" + base
    elif d is None:
        note = f"brak stresu w ciągu {len(res.horizon_dr)} dni" + base
    else:
        note = f"stres za ok. {d} dni" + base
    rstatus = RISK_STATUS[res.risk or "niskie"]
    if d == 0 and res.ks is not None and res.ks < 0.5:
        rstatus = "danger"
    risk = RiskIndicator(
        value=d, unit="dni", label=(res.risk or "niskie").capitalize(), status=rstatus, note=note,
        days_to_stress=d, source_tag=rtag,
    )

    rec = None
    irr = res.irrigation
    if irr and irr.needed:
        when = "od razu" if irr.when == analysis_date else f"ok. {irr.when:%d.%m}"
        rec = Recommendation(
            id="nawadnianie-model",
            category="nawadnianie",
            title=f"Nawadnianie {when}",
            description=f"Dawka ok. {irr.dose_mm} mm – uzupełnia wodę do pojemności polowej." + dose_hint(irr.dose_mm or 0),
            why=(
                f"Woda w glebie {res.water_pct:.0f}% ({res.water_mm:.0f} z {res.taw_mm:.0f} mm). "
                f"Rośliny odczuwają brak wody, gdy ubytek przekroczy {res.raw_mm:.0f} mm"
                + ("; ten próg jest już przekroczony." if d == 0 else f"; według {'prognozy' if res.horizon_kind == 'prognoza' else 'scenariusza typowej pogody'} nastąpi to za ok. {d} dni.")
            ),
            inputs=[
                Evidence(name="Woda w glebie", value=res.water_pct, unit="%", source=MODEL_SOURCE, date=last_usable_day(analysis_date)),
                Evidence(name="Ubytek wody w strefie korzeni", value=res.dr_mm, unit="mm", source=MODEL_SOURCE),
                Evidence(name="Próg stresu (łatwo dostępna woda, RAW)", value=res.raw_mm, unit="mm", source="FAO-56 + IUNG (WOD)"),
                Evidence(name="Dni do stresu", value=d, unit="dni", source=rtag.source or MODEL_SOURCE),
            ],
            confidence="srednia" if res.horizon_kind == "prognoza" else "ograniczona",
            rule_id="nawadnianie.model_fao56",
        )
    return ModelIndicators(pct, mm, risk, years, rec)
