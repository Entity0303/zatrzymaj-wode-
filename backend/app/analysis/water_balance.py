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
from functools import lru_cache
from math import ceil
from pathlib import Path

import numpy as np
import yaml

from app.analysis.crops import PHASE_LABELS, Crop, DayInfo, no_irrigation_sentence
from app.analysis.et0 import DailyWeather
from app.schemas.analysis import (
    BalanceRank,
    BandPoint,
    CropSeason,
    DrySpell,
    Evidence,
    History,
    Indicator,
    IrrigationPlan,
    MonthlyPrecip,
    Recommendation,
    RiskIndicator,
    SeasonSummary,
    SeriesPoint,
    SoilWaterState,
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
    """Zakres danych do pobrania: od 1 sierpnia (rok dnia przed analizą − years − 2) do dnia przed analizą.

    Pokrywa ciągły bilans modelu wody w glebie dla najstarszego sezonu porównawczego: okno od 1 XI
    (lub 1 VII) roku poprzedzającego sezon + 3 miesiące na stan początkowy (D28, D30). `season_start`
    zostawiony dla zgodności – zakres nie zależy już od sezonu bilansu KBW."""
    end = last_usable_day(analysis_date)
    return date(end.year - years - 2, 8, 1), end


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


@lru_cache
def _history_text() -> dict:
    return yaml.safe_load((Path(__file__).parent / "rules" / "history_text.yaml").read_text(encoding="utf-8"))["history_text"]


def history_sentence(lower_years: int | None, of_years: int) -> str:
    """Proste zdanie „Na tle 10 lat” z liczby lat suchszych od tegorocznego (progi i teksty: rules/history_text.yaml)."""
    cfg = _history_text()
    s = cfg["sentences"]
    if lower_years is None or of_years <= 0:
        return s["no_comparison"]
    t, share = cfg["thresholds"], lower_years / of_years
    kind = ("most_dry" if lower_years == 0 else "most_wet" if lower_years == of_years else
            "drier_only" if share <= t["drier_max_share"] else
            "slightly_drier" if share <= t["slightly_drier_max_share"] else
            "average" if share <= t["average_max_share"] else
            "slightly_wetter" if share <= t["slightly_wetter_max_share"] else "wetter")
    return s[kind].format(k=lower_years, n=of_years)


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
    by_year: list[tuple[int, float, bool]] = field(default_factory=list)  # (rok, bilans mm, bieżący) – A5e, słupki


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
    by_year: list[tuple[int, float, bool]] = []
    if rows:
        c = np.nancumsum(np.vstack(rows), axis=1)
        bmin, bmax, bmean = c.min(axis=0), c.max(axis=0), c.mean(axis=0)
        balance_band = [
            BandPoint(date=d, min=_r1(a), max=_r1(b), mean=_r1(m))
            for d, a, b, m in zip(series_dates, bmin, bmax, bmean)
        ]
        totals = c[:, -1]
        mean_total = float(totals.mean())
        lower_years = int((totals < current_total).sum())
        percentile = 100.0 * lower_years / len(totals)
        # jedno źródło liczby (A5e): wszędzie pokazujemy mm zaokrąglone do całości, a odchylenie = różnica tych
        # zaokrąglonych liczb (inaczej wychodziło −154 w jednym miejscu i −153 w drugim)
        current_total, mean_total = float(round(current_total)), float(round(mean_total))
        deviation = current_total - mean_total
        by_year = sorted([(y, float(round(t)), False) for y, t in zip(band_years, totals)]) + [
            (s0.year, current_total, True)]
    else:
        current_total = float(round(current_total))

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

    # ── podsumowanie – proste zdanie (YAML), liczby szczegółowo w `details` ──
    summary = history_sentence(lower_years, len(band_years))
    details = (
        f"Od {format_date_pl(s0, with_year=False)} do {format_date_pl(data_until)}: spadło minus wyparowało = "
        f"{format_mm(current_total)} mm."
    )
    if mean_total is not None and deviation is not None and lower_years is not None:
        more_less = "mniej" if deviation < 0 else "więcej"
        details += (
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
        details=details,
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
        by_year=by_year,
    )


# ═══════════════════════════════════════════════════════════════════════════════════════════
# Model wody w glebie FAO-56 – ciągły bilans przez cały rok (A3, poprawki A3b)
# ═══════════════════════════════════════════════════════════════════════════════════════════
#
# Profil 1 m (WOD z IUNG, D25) dzielony na dwie warstwy (D30):
#   strefa czynna 0..Zr(t) – korzenie uprawy albo warstwa parowania gołej gleby (Ze),
#   warstwa dolna Zr(t)..1 m.
# Stan: ubytki D1 (strefa) i D2 (dolna) [mm]; 0 = pojemność polowa. Zmiana Zr przenosi wodę
# między warstwami przy równym względnym ubytku w przenoszonym plastrze. Opad efektywny zasila
# strefę, nadmiar – warstwę dolną, dalszy nadmiar = przesiąkanie (zimowa odbudowa zapasu).
# Ewapotranspiracja z strefy czynnej: uprawa – Ks·Kc·ET0 (FAO-56 równ. 84), goła gleba –
# Kr·Kc_gleby·ET0 (dwuetapowe parowanie, FAO-56 rozdz. 7: REW, TEW = WOD·Ze).
# Siew zmienia tylko Kc i Zr – NIE resetuje zapasu. Stres = faza wrażliwa i D1 > RAW = p·TAW strefy.

PROFILE_DEPTH_M = 1.0  # WOD z IUNG odnosi się do profilu ok. 1 m (D25)
RUNOFF_THRESHOLD_MM = 20.0  # spływ: 20% części opadu powyżej 20 mm/dzień (D26) –
RUNOFF_FRACTION = 0.20  # parametry do nadpisania przez analizę terenu (NMT)
REW_MAX_MM = 9.0  # łatwo odparowująca woda gołej gleby (FAO-56 tab. 19: 8–10 mm dla glin)
INIT_DAYS = 92  # stan początkowy okna z bilansu 3 miesięcy przed oknem (D30)
HORIZON_DAYS = 16  # „stres za X dni” – tyle dni ma prognoza Open-Meteo
RISK_HIGH_DAYS = 3  # przekroczenie RAW w ≤ 3 dni (lub już) → wysokie (D27)
RISK_MEDIUM_DAYS = 7  # 4–7 dni → średnie; później / wcale w 16 dniach → niskie
CATEGORY_DOSE_MM = {1: 17.5, 2: 22.5, 3: 27.5, 4: 32.5}  # dawka jednorazowa wg kategorii gleby (D33)
DEFAULT_DOSE_MM = 22.5
MAX_DOSE_MM = 35.0
MODEL_SOURCE = "Model wody w glebie FAO-56"


def taw_from_wod(wod_mm: float, root_depth_m: float, profile_m: float = PROFILE_DEPTH_M) -> float:
    """TAW warstwy 0..Zr: WOD (profil ~1 m) × min(Zr, 1 m) / 1 m – głębiej brak danych o glebie (D25)."""
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


def kr_coefficient(de: float, tew: float, rew: float) -> float:
    """Redukcja parowania gołej gleby Kr (FAO-56, równanie 74)."""
    if de <= rew:
        return 1.0
    return max(0.0, (tew - de) / (tew - rew)) if tew > rew else 0.0


def window_start(crop: Crop, season_year: int) -> date:
    """Początek ciągłego bilansu: 1 XI roku poprzedzającego sezon; uprawy siewu letnio-jesiennego – 1 VII (D28)."""
    return date(season_year - 1, 11, 1) if crop.start[0] <= 6 else date(season_year, 7, 1)


@dataclass
class State:
    d1: float  # ubytek strefy czynnej [mm]
    d2: float  # ubytek warstwy dolnej [mm]
    zr: float  # głębokość strefy czynnej [m]

    def total(self) -> float:
        return self.d1 + self.d2


@dataclass
class Trace:
    dates: list[date]
    d1: np.ndarray
    dtot: np.ndarray
    raw1: np.ndarray
    zr: np.ndarray
    phase: list[str]
    stress: np.ndarray  # faza wrażliwa i D1 > RAW
    season_year: np.ndarray
    dp: np.ndarray  # przesiąkanie
    missing: int
    eta: np.ndarray | None = None  # ewapotranspiracja rzeczywista (Ks·Kc·ET0) [mm]
    etc: np.ndarray | None = None  # potencjalna uprawy (Kc·ET0) [mm] – do plonu FAO-33 (A5b-2a)


def _resize(st: State, z_new: float, wod: float) -> None:
    """Zmiana grubości strefy czynnej – przeniesienie plastra z równym względnym ubytkiem."""
    z_new = min(z_new, PROFILE_DEPTH_M)
    dz = z_new - st.zr
    if abs(dz) < 1e-9:
        return
    if dz > 0:  # korzenie rosną – plaster z warstwy dolnej
        lower = PROFILE_DEPTH_M - st.zr
        move = st.d2 * dz / lower if lower > 1e-9 else 0.0
        st.d2 -= move
        st.d1 += move
    else:  # strefa maleje (zbiór) – plaster wraca do warstwy dolnej
        move = st.d1 * (-dz) / st.zr if st.zr > 1e-9 else 0.0
        st.d1 -= move
        st.d2 += move
    st.zr = z_new


def run(
    crop: Crop,
    wod: float,
    dates: list[date],
    precip: np.ndarray,
    et0: np.ndarray,
    st: State,
    runoff_threshold: float = RUNOFF_THRESHOLD_MM,
    runoff_fraction: float = RUNOFF_FRACTION,
) -> Trace:
    """Dzienny bilans (sekwencyjny). Dzień bez opadu lub ET0 (NaN) nie zmienia stanu (`missing`)."""
    n = len(dates)
    pe = effective_precip(np.asarray(precip, float), runoff_threshold, runoff_fraction)
    et0 = np.asarray(et0, float)
    out_d1, out_dt, out_raw, out_zr = np.empty(n), np.empty(n), np.empty(n), np.empty(n)
    out_stress, out_sy, out_dp = np.zeros(n, bool), np.zeros(n, int), np.zeros(n)
    out_eta, out_etc = np.zeros(n), np.zeros(n)
    phases: list[str] = []
    missing = 0
    for i, d in enumerate(dates):
        info: DayInfo = crop.day_info(d)
        _resize(st, info.zr, wod)
        taw1 = wod * st.zr
        raw1 = crop.p * taw1
        if not (np.isnan(pe[i]) or np.isnan(et0[i])):
            if info.bare:
                rew = min(REW_MAX_MM, 0.5 * taw1)
                et = kr_coefficient(st.d1, taw1, rew) * info.kc * et0[i]
            else:
                et = ks_coefficient(st.d1, taw1, raw1) * info.kc * et0[i]
            st.d1 -= pe[i]
            if st.d1 < 0:  # nadmiar do warstwy dolnej
                st.d2 += st.d1
                st.d1 = 0.0
                if st.d2 < 0:  # dalej – przesiąkanie poniżej profilu
                    out_dp[i] = -st.d2
                    st.d2 = 0.0
            st.d1 = min(st.d1 + et, taw1)
            out_eta[i], out_etc[i] = et, info.kc * et0[i]
        else:
            missing += 1
        out_d1[i], out_dt[i], out_raw[i], out_zr[i] = st.d1, st.total(), raw1, st.zr
        out_stress[i] = info.sensitive and st.d1 > raw1
        out_sy[i] = info.season_year
        phases.append(info.phase)
    return Trace(dates, out_d1, out_dt, out_raw, out_zr, phases, out_stress, out_sy, out_dp, missing, out_eta, out_etc)


def initial_state(w: DailyWeather, crop: Crop, wod: float, start: date) -> tuple[State, float | None]:
    """Stan na początek okna: profil pełny, pomniejszony o deficyt bilansu P − ET0 z 3 miesięcy
    przed oknem (stan po lecie, D30); równy względny ubytek w obu warstwach."""
    taw_p = wod * PROFILE_DEPTH_M
    z = min(crop.day_info(start).zr, PROFILE_DEPTH_M)
    i1 = _idx(w, start)
    seg = _segment(w.climatic_water_balance, i1 - INIT_DAYS, INIT_DAYS)
    if seg is None or np.isnan(seg).mean() > MAX_MISSING_MONTH:
        return State(0.0, 0.0, z), None
    bal = float(np.nansum(seg))
    f = min(1.0, max(0.0, -bal) / taw_p) if taw_p > 0 else 0.0
    return State(f * wod * z, f * wod * (PROFILE_DEPTH_M - z), z), round(bal, 1)


def _days(a: date, b: date) -> list[date]:
    return [a + timedelta(days=k) for k in range((b - a).days + 1)]


def _observed(w: DailyWeather, a: date, b: date) -> tuple[np.ndarray, np.ndarray] | None:
    i0, i1 = _idx(w, a), _idx(w, b)
    if i0 < 0 or i1 >= len(w.dates):
        return None
    return w.precip[i0 : i1 + 1], w.et0[i0 : i1 + 1]


@dataclass
class HorizonDay:
    day: date
    precip: float
    et0: float


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


def data_until_for(w: DailyWeather, last: date) -> date | None:
    """Ostatni dzień z kompletem opadu i ET0, nie później niż `last`."""
    kbw = w.climatic_water_balance
    i_req = min(_idx(w, last), len(w.dates) - 1)
    valid = np.flatnonzero(~np.isnan(kbw[: i_req + 1])) if i_req >= 0 else np.array([], dtype=int)
    return w.dates[valid[-1]].astype(object) if valid.size else None


def bridged_inputs(
    w: DailyWeather, start: date, last: date, forecast: list[HorizonDay] | None, years: int = 10,
) -> tuple[list[float], list[float], date, list[str]] | None:
    """Opad i ET0 od `start` do `last`: obserwacje do ostatniego dnia z danymi, luka opóźnienia źródła – Open-Meteo
    (`past_days`), a gdy go brak – scenariusz typowej pogody (D27). None = za mało danych (też na stan początkowy)."""
    data_until = data_until_for(w, last)
    obs = _observed(w, start, data_until) if data_until and data_until >= start else None
    if obs is None or _idx(w, start) - INIT_DAYS < 0:
        return None
    p_in, e_in, notes = list(obs[0]), list(obs[1]), []
    gap = (last - data_until).days
    fc = {d.day: d for d in (forecast or [])}
    if gap > 0:
        bridge = [fc.get(data_until + timedelta(days=k + 1)) for k in range(gap)]
        if all(b is not None and not np.isnan(b.precip) and not np.isnan(b.et0) for b in bridge):
            notes.append(f"Ostatnie {gap} dni przed datą analizy uzupełnione danymi modelu Open-Meteo.")
        else:
            bridge = climatology_horizon(w, data_until + timedelta(days=1), gap, years)
            notes.append(f"Ostatnie {gap} dni przed datą analizy bez danych – uzupełnione scenariuszem typowej pogody.")
        p_in += [b.precip for b in bridge]
        e_in += [b.et0 for b in bridge]
    return p_in, e_in, data_until, notes


def risk_class(days_to_stress: int | None) -> str:
    if days_to_stress is not None and days_to_stress <= RISK_HIGH_DAYS:
        return "wysokie"
    if days_to_stress is not None and days_to_stress <= RISK_MEDIUM_DAYS:
        return "średnie"
    return "niskie"


def _fmt_mm(v: float) -> str:
    return f"{v:.1f}".replace(".", ",").replace(",0", "")


@dataclass
class IrrigationResult:
    status: str  # "zalecane" | "niepotrzebne" | "nieuzasadnione_w_fazie" | "brak_danych"
    message: str
    dose_mm: float | None = None
    first_date: date | None = None
    interval_days: int | None = None
    total_7d_mm: float | None = None
    doses_7d: int | None = None


@dataclass
class SoilWaterResult:
    crop_id: str
    status: str  # "ok" | "brak_danych"
    season_year: int
    season_start: date
    harvest: date
    phase: str
    phase_label: str
    sensitive: bool
    day_of_season: int | None = None
    kc: float | None = None
    root_depth_m: float | None = None
    taw_root_mm: float | None = None
    raw_root_mm: float | None = None
    taw_profile_mm: float | None = None
    d1_mm: float | None = None
    dtot_mm: float | None = None
    data_until: date | None = None
    window_start: date | None = None
    init_balance_mm: float | None = None
    scope: str = "profil"  # "strefa_korzeni" | "profil"
    depth_m: float = PROFILE_DEPTH_M
    water_pct: float | None = None
    water_mm: float | None = None
    description: str = ""
    rank_lower: int | None = None  # w ilu latach tego dnia było mniej wody
    rank_of: int | None = None
    stress_days_season: int | None = None
    season_complete: bool = False
    stress_by_year: list[tuple[int, int | None]] = field(default_factory=list)
    mean_prev_stress_days: float | None = None
    percolation_mm: float | None = None
    horizon_kind: str | None = None  # "prognoza" | "scenariusz"
    horizon: list[tuple[date, float, float, str]] = field(default_factory=list)  # (dzień, D1, RAW, faza)
    days_to_stress: int | None = None
    risk: str | None = None
    irrigation: IrrigationResult | None = None
    season_deficit_mm: float | None = None  # ETc − ETa w fazach uprawy bieżącego sezonu [mm]
    limitations: list[str] = field(default_factory=list)


def _metric(st: State, wod: float, scope: str) -> tuple[float, float, float]:
    """(woda %, woda mm, głębokość) – strefa korzeni albo cały profil."""
    if scope == "strefa_korzeni":
        taw = wod * st.zr
        return (100 * (1 - st.d1 / taw) if taw > 0 else 0.0), taw - st.d1, st.zr
    taw = wod * PROFILE_DEPTH_M
    return (100 * (1 - st.total() / taw) if taw > 0 else 0.0), taw - st.total(), PROFILE_DEPTH_M


IN_SEASON_SCOPE = {"poczatkowa", "rozwoj", "pelnia", "dojrzewanie"}


def soil_water_model(
    w: DailyWeather,
    crop: Crop,
    wod_mm: float,
    analysis_date: date,
    forecast: list[HorizonDay] | None = None,
    soil_category: int | None = None,
    years: int = 10,
    runoff_threshold: float = RUNOFF_THRESHOLD_MM,
    runoff_fraction: float = RUNOFF_FRACTION,
) -> SoilWaterResult:
    """Ciągły bilans od początku okna (1 XI / 1 VII) do dnia przed datą analizy, stan na datę analizy,
    dni stresu w sezonie na tle 10 lat, ryzyko 7 dni i plan nawadniania (tylko fazy wrażliwe)."""
    L = last_usable_day(analysis_date)
    sy = crop.season_year_for(L)
    s, h = crop.season(sy)
    ws = window_start(crop, sy)
    info = crop.day_info(analysis_date)
    res = SoilWaterResult(
        crop.id, "brak_danych", sy, s, h, info.phase, PHASE_LABELS[info.phase], info.sensitive,
        day_of_season=None if info.day_of_season is None else info.day_of_season + 1,
        kc=round(info.kc, 2), window_start=ws, taw_profile_mm=round(wod_mm * PROFILE_DEPTH_M, 1),
    )
    lim = res.limitations

    # ── dane: obserwacje do ostatniego dnia z kompletem, luka (opóźnienie źródła) – prognoza/scenariusz ──
    fc = {d.day: d for d in (forecast or [])}
    inputs = bridged_inputs(w, ws, L, forecast, years)
    if inputs is None:
        lim.append("Za mało danych pogodowych do modelu wody w glebie.")
        res.irrigation = IrrigationResult("brak_danych", "Brak danych do oceny nawadniania.")
        return res
    p_in, e_in, data_until, notes = inputs
    res.data_until = data_until
    lim += notes

    st, bal = initial_state(w, crop, wod_mm, ws)
    res.init_balance_mm = bal
    if bal is None:
        lim.append(f"Brak danych sprzed {format_date_pl(ws)} – bilans startuje z pełnym profilem.")
    tr = run(crop, wod_mm, _days(ws, L), np.array(p_in), np.array(e_in), st, runoff_threshold, runoff_fraction)
    if tr.missing:
        lim.append(f"{tr.missing} dni bez danych pogodowych – stan gleby w tych dniach bez zmian.")
    res.status = "ok"
    res.percolation_mm = round(float(tr.dp.sum()), 1)

    # ── stan na datę analizy ──
    scope = "strefa_korzeni" if info.phase in IN_SEASON_SCOPE else "profil"
    pct, mm, depth = _metric(st, wod_mm, scope)
    res.scope, res.water_pct, res.water_mm, res.depth_m = scope, round(pct), round(mm, 1), round(depth, 2)
    res.root_depth_m = round(st.zr, 2)
    res.taw_root_mm = round(wod_mm * st.zr, 1)
    res.raw_root_mm = round(crop.p * wod_mm * st.zr, 1)
    res.d1_mm, res.dtot_mm = round(st.d1, 1), round(st.total(), 1)

    # ── dni stresu w bieżącym sezonie (fazy wrażliwe, D32) ──
    in_season = tr.season_year == sy
    res.stress_days_season = int((tr.stress & in_season).sum())
    grow = in_season & np.isin(np.array(tr.phase), list(IN_SEASON_SCOPE))
    res.season_deficit_mm = round(float((tr.etc[grow] - tr.eta[grow]).sum()), 0)
    res.season_complete = L >= h

    # ── te same okresy w poprzednich latach: dni stresu i stan wody tego samego dnia ──
    by_year: list[tuple[int, int | None]] = [(sy, res.stress_days_season)]
    prev_stress, prev_metric = [], []
    for k in range(1, years + 1):
        wsk, Lk = window_start(crop, sy - k), shift_years(L, k)
        o = _observed(w, wsk, Lk)
        if o is None or _idx(w, wsk) - INIT_DAYS < 0 or np.isnan(o[0] + o[1]).mean() > MAX_MISSING_YEAR:
            by_year.append((sy - k, None))
            continue
        stk, _ = initial_state(w, crop, wod_mm, wsk)
        trk = run(crop, wod_mm, _days(wsk, Lk), o[0], o[1], stk, runoff_threshold, runoff_fraction)
        sd = int((trk.stress & (trk.season_year == sy - k)).sum())
        by_year.append((sy - k, sd))
        prev_stress.append(sd)
        prev_metric.append(_metric(stk, wod_mm, scope)[0])
    res.stress_by_year = by_year
    res.mean_prev_stress_days = round(float(np.mean(prev_stress)), 1) if prev_stress else None
    if prev_metric:
        res.rank_lower = int(sum(m < pct for m in prev_metric))
        res.rank_of = len(prev_metric)
    if len(prev_stress) < years:
        lim.append(f"Porównanie z {len(prev_stress)} z {years} poprzednich lat (pozostałe – niepełne dane).")

    # ── horyzont 16 dni: tylko w fazach wrażliwych (D32) ──
    stressed_now = info.sensitive and st.d1 > crop.p * wod_mm * st.zr
    if info.sensitive:
        future = [fc[d] for d in _days(analysis_date, analysis_date + timedelta(days=HORIZON_DAYS - 1)) if d in fc]
        if forecast and len(future) >= 7:
            res.horizon_kind, hz = "prognoza", future
        else:
            res.horizon_kind, hz = "scenariusz", climatology_horizon(w, analysis_date, HORIZON_DAYS, years)
        sth = State(st.d1, st.d2, st.zr)
        trh = run(crop, wod_mm, [x.day for x in hz], np.array([x.precip for x in hz]),
                  np.array([x.et0 for x in hz]), sth, runoff_threshold, runoff_fraction)
        res.horizon = [(d, round(float(a), 1), round(float(r), 1), ph)
                       for d, a, r, ph in zip(trh.dates, trh.d1, trh.raw1, trh.phase)]
        over = np.flatnonzero(trh.stress)
        res.days_to_stress = 0 if stressed_now else (int(over[0]) + 1 if over.size else None)
        res.risk = risk_class(res.days_to_stress)
        if crop.irrigation_practice == "not_practiced":  # D48: bez dawek i bez planu
            res.irrigation = IrrigationResult("nie_praktykowane", no_irrigation_sentence(crop) + ".")
        elif crop.irrigation_practice == "optional":  # D64: żadnych dawek – najwyżej informacja o niedoborze
            res.irrigation = optional_irrigation_info(res)
        else:
            res.irrigation = _irrigation_plan(crop, wod_mm, st, hz, res.days_to_stress, analysis_date, soil_category,
                                              runoff_threshold, runoff_fraction)
    elif crop.irrigation_practice == "not_practiced":
        res.irrigation = IrrigationResult("nie_praktykowane", no_irrigation_sentence(crop) + ".")
    else:
        res.irrigation = IrrigationResult(
            "nieuzasadnione_w_fazie", f"Nawadnianie nieuzasadnione w tej fazie uprawy ({res.phase_label})."
        )

    res.description = _describe(res, tr, info, stressed_now)
    return res


def _describe(res: SoilWaterResult, tr: Trace, info: DayInfo, stressed_now: bool) -> str:
    if info.phase in IN_SEASON_SCOPE:
        if info.phase == "dojrzewanie":
            return "dojrzewanie – niedobór wody nie wymaga już działań" if res.water_pct is not None and res.water_pct < 50 \
                else "dojrzewanie – wody wystarcza"
        if stressed_now:
            return f"{res.phase_label} – rośliny odczuwają brak wody"
        if res.days_to_stress is not None:
            return f"{res.phase_label} – rośliny zaczną odczuwać brak wody za ok. {res.days_to_stress} dni"
        return f"{res.phase_label} – wody wystarcza na najbliższe dni"
    prefix = "wschody jesienne" if info.phase == "wschody_jesienne" else "poza sezonem"
    refill = len(tr.dtot) > 30 and tr.dtot[-31] - tr.dtot[-1] > 1.0
    if res.water_pct is not None and res.water_pct < 50:
        return f"{prefix} – niedobór wody" + (" po suchym lecie" if tr.dates[-1].month >= 8 else " po suchym okresie")
    if refill:
        return f"{prefix} – gleba odbudowuje zapas wody"
    if res.water_pct is not None and res.water_pct >= 90:
        return f"{prefix} – zapas wody w glebie odbudowany"
    return f"{prefix} – zapas wody w normie"


OPTIONAL_DEFICIT_MIN_MM = 10.0
OPTIONAL_TAIL = ("nawadnianie opłaca się tylko przy własnym źródle wody i deszczowni; pobór wody może wymagać "
                 "pozwolenia wodnoprawnego – Wody Polskie")


def optional_irrigation_info(res: SoilWaterResult) -> IrrigationResult:
    """Uprawy nawadniane w Polsce rzadko (kukurydza, tytoń): bez dawek i harmonogramu (D64)."""
    d = res.season_deficit_mm or 0.0
    if d >= OPTIONAL_DEFICIT_MIN_MM:
        return IrrigationResult("informacyjne", f"W tym sezonie brakuje ok. {d:.0f} mm wody; {OPTIONAL_TAIL}")
    if res.days_to_stress is not None and res.days_to_stress <= RISK_MEDIUM_DAYS:
        return IrrigationResult("informacyjne", f"Rośliny wkrótce odczują brak wody; {OPTIONAL_TAIL}")
    return IrrigationResult("niepotrzebne", "Wody na razie wystarcza – w tym sezonie uprawie jej nie brakowało.")


MIN_DOSE_INTERVAL_DAYS = 2  # nie częściej niż co 2 dni – realna logistyka deszczowni (D33)


def _irrigation_plan(
    crop: Crop, wod: float, st: State, hz: list[HorizonDay], days_to_stress: int | None, analysis_date: date,
    soil_category: int | None, runoff_threshold: float, runoff_fraction: float,
) -> IrrigationResult:
    """Dawka jednorazowa wg kategorii gleby (≤ 35 mm); harmonogram dawek w 7 dniach z symulacji
    (dawka, gdy ubytek strefy korzeni przekroczy RAW, nie częściej niż co 2 dni); łączny niedobór (D33)."""
    if days_to_stress is None or days_to_stress > RISK_MEDIUM_DAYS:
        return IrrigationResult("niepotrzebne", "Nawadnianie niepotrzebne – zapas wody wystarczy na najbliższe 7 dni.")
    dose = min(MAX_DOSE_MM, CATEGORY_DOSE_MM.get(soil_category or 0, DEFAULT_DOSE_MM))
    week = hz[:7]
    pe = effective_precip(np.array([x.precip for x in week]), runoff_threshold, runoff_fraction)
    d_no, d_irr, need, net, doses = st.d1, st.d1, 0.0, [], []
    for k, (x, p) in enumerate(zip(week, pe)):
        info = crop.day_info(x.day)
        raw_k = crop.p * wod * min(info.zr, PROFILE_DEPTH_M)
        etc = info.kc * (0.0 if np.isnan(x.et0) else x.et0)
        p = 0.0 if np.isnan(p) else p
        if d_irr > raw_k and (not doses or k - doses[-1] >= MIN_DOSE_INTERVAL_DAYS):
            d_irr = max(0.0, d_irr - dose)
            doses.append(k)
        d_irr = max(0.0, d_irr + etc - p)
        d_no = max(0.0, d_no + etc - p)  # bez nawadniania, bez redukcji Ks – zapotrzebowanie
        need = max(need, d_no - raw_k)
        net.append(max(0.0, etc - p))
    if not doses:  # przekroczenie pod koniec tygodnia – jedna dawka w dniu przekroczenia
        doses = [max(0, days_to_stress - 1)]
    first = analysis_date + timedelta(days=doses[0])
    mean_net = float(np.mean(net)) if net else 0.0
    if len(doses) > 1:
        interval = doses[1] - doses[0]
    else:
        interval = None if mean_net < 0.5 else int(min(14, max(MIN_DOSE_INTERVAL_DAYS, dose // mean_net)))
    total = float(max(5, round(need / 5) * 5)) if need > 0 else dose
    when = "teraz" if first == analysis_date else f"ok. {first:%d.%m}"
    msg = f"{_fmt_mm(dose)} mm {when}"
    if len(doses) > 1:
        msg += f", powtórz za ok. {interval} dni (w 7 dniach {len(doses)} dawki, niedobór ok. {_fmt_mm(total)} mm)"
    elif interval:
        msg += f"; przy braku deszczu kolejna dawka za ok. {interval} dni"
    return IrrigationResult("zalecane", msg, dose, first, interval, total, len(doses))


# ── Model → pola kontraktu ──────────────────────────────────────────────────────────────────

RISK_STATUS = {"niskie": "ok", "średnie": "warn", "wysokie": "risk"}


@dataclass
class ModelOutputs:
    soil_water_pct: Indicator
    soil_water_mm: Indicator
    risk_7d: RiskIndicator
    stress_days_by_year: list[YearStress]
    crop_season: CropSeason
    soil_water: SoilWaterState
    irrigation: IrrigationPlan
    irrigation_rec: Recommendation | None


def to_contract(res: SoilWaterResult, crop: Crop, analysis_date: date, no_model_note: str | None = None) -> ModelOutputs:
    """Wynik modelu → indicators.soil_water_*, risk_7d, history.stress_days_by_year, crop_season,
    soil_water, irrigation i rekomendacja „nawadnianie” (gdy zalecane)."""
    crop_season = CropSeason(
        phase=res.phase, phase_label=res.phase_label, season_year=res.season_year, season_start=res.season_start,
        harvest=res.harvest, day_of_season=res.day_of_season, sensitive=res.sensitive, root_depth_m=res.root_depth_m,
    )
    years = [YearStress(year=y, stress_days=d, is_current=(i == 0)) for i, (y, d) in enumerate(res.stress_by_year)]
    model_tag = SourceTag(kind="szacunek_modelu", date=last_usable_day(analysis_date), source=MODEL_SOURCE)

    if res.status != "ok" or no_model_note:
        note = no_model_note or (res.limitations[0] if res.limitations else "Brak danych do modelu wody w glebie.")
        tag = SourceTag(kind="brak_danych", source=MODEL_SOURCE)
        return ModelOutputs(
            Indicator(value=None, unit="%", status="no_data", note=note, source_tag=tag),
            Indicator(value=None, unit="mm", status="no_data", note=note, source_tag=tag),
            RiskIndicator(value=None, unit="dni", status="no_data", note=note, source_tag=tag),
            years,
            crop_season,
            SoilWaterState(scope="profil", depth_m=PROFILE_DEPTH_M, description=note),
            IrrigationPlan(status="brak_danych", message=note, practice=crop.irrigation_practice, source_tag=tag),
            None,
        )

    zone = f"strefa korzeni {res.depth_m:g} m" if res.scope == "strefa_korzeni" else "profil ok. 1 m"
    if res.sensitive:
        status = "risk" if res.days_to_stress == 0 else ("warn" if res.risk == "średnie" else "ok")
    else:
        status = "warn" if (res.water_pct or 0) < 50 else "ok"
    pct = Indicator(value=res.water_pct, unit="%", label=res.phase_label, status=status,
                    note=f"{res.description} ({zone})", source_tag=model_tag)
    mm = Indicator(value=res.water_mm, unit="mm", status=status,
                   note=f"woda dostępna dla roślin, {zone}", source_tag=model_tag)

    if res.sensitive:
        if res.horizon_kind == "prognoza":
            rtag = SourceTag(kind="prognoza", date=analysis_date, source="Open-Meteo + " + MODEL_SOURCE)
            base = ""
        else:
            rtag = SourceTag(kind="szacunek_modelu", date=analysis_date, source="scenariusz typowej pogody (10 lat)")
            base = " (scenariusz typowej pogody)"
        d = res.days_to_stress
        note = ("rośliny już odczuwają brak wody" if d == 0 else
                f"brak stresu w ciągu {HORIZON_DAYS} dni" if d is None else f"stres za ok. {d} dni") + base
        risk = RiskIndicator(value=d, unit="dni", label=(res.risk or "niskie").capitalize(),
                             status=RISK_STATUS[res.risk or "niskie"], note=note, days_to_stress=d, source_tag=rtag)
    else:
        rtag = model_tag
        risk = RiskIndicator(value=None, unit="dni", label="Nie dotyczy", status="ok",
                             note=f"{res.phase_label} – poza fazą wrażliwą na brak wody", source_tag=model_tag)

    last = SeasonSummary(year=res.season_year, stress_days=res.stress_days_season,
                         mean_prev_stress_days=res.mean_prev_stress_days) if res.season_complete else None
    soil_water = SoilWaterState(
        scope=res.scope, depth_m=res.depth_m, description=res.description,
        rank=BalanceRank(lower_years=res.rank_lower, of_years=res.rank_of) if res.rank_of else None,
        last_season=last,
    )
    irr = res.irrigation or IrrigationResult("brak_danych", "Brak danych do oceny nawadniania.")
    plan = IrrigationPlan(status=irr.status, message=irr.message, dose_mm=irr.dose_mm, first_date=irr.first_date,
                          interval_days=irr.interval_days, total_7d_mm=irr.total_7d_mm, doses_7d=irr.doses_7d,
                          practice=crop.irrigation_practice, source_tag=rtag)
    rec = None
    if irr.status == "zalecane" and crop.irrigation_practice != "not_practiced":
        rec = Recommendation(
            id="nawadnianie-model",
            category="nawadnianie",
            when="teraz", when_label="teraz", permit="required",
            permit_note="Wymaga pozwolenia wodnoprawnego (pobór wody) – Wody Polskie.",
            permit_url="https://www.gov.pl/web/wody-polskie",
            title="Nawadnianie " + ("teraz" if irr.first_date == analysis_date else f"ok. {irr.first_date:%d.%m}"),
            description=irr.message + ".",
            why=(
                f"Woda w strefie korzeni {res.water_pct:.0f}% ({res.water_mm:.0f} mm). Rośliny odczuwają brak wody, "
                f"gdy ubytek przekroczy {res.raw_root_mm:.0f} mm"
                + ("; ten próg jest już przekroczony." if res.days_to_stress == 0 else
                   f"; według {'prognozy' if res.horizon_kind == 'prognoza' else 'scenariusza typowej pogody'} "
                   f"nastąpi to za ok. {res.days_to_stress} dni.")
                + f" Dawka jednorazowa {_fmt_mm(irr.dose_mm or 0)} mm dobrana do gleby."
            ),
            inputs=[
                Evidence(name="Woda w strefie korzeni", value=res.water_pct, unit="%", source=MODEL_SOURCE,
                         date=last_usable_day(analysis_date)),
                Evidence(name="Próg stresu (łatwo dostępna woda, RAW)", value=res.raw_root_mm, unit="mm",
                         source="FAO-56 + IUNG (WOD)"),
                Evidence(name="Dni do stresu", value=res.days_to_stress, unit="dni", source=rtag.source or MODEL_SOURCE),
                Evidence(name="Niedobór do uzupełnienia w 7 dniach", value=irr.total_7d_mm, unit="mm", source=MODEL_SOURCE),
            ],
            confidence="srednia" if res.horizon_kind == "prognoza" else "ograniczona",
            rule_id="nawadnianie.model_fao56",
        )
    return ModelOutputs(pct, mm, risk, years, crop_season, soil_water, plan, rec)


# ── Sumy sezonu (przyczyny, reguły) ─────────────────────────────────────────────────────────


@dataclass
class SeasonSums:
    season_start: date
    until: date | None
    days: int
    precip_mm: float | None
    precip_mean_mm: float | None
    et0_mm: float | None
    et0_mean_mm: float | None
    et0_recent_mm_day: float | None  # średnie ET0 z ostatnich 7 dni z danymi


def season_sums(w: DailyWeather, analysis_date: date, season_start: date | None = None, years: int = 10) -> SeasonSums:
    """Opad i ET0 od początku sezonu bilansu (1 III) do ostatniego dnia z danymi oraz średnie z tych samych
    okresów w `years` poprzednich latach (lata z > 10% braków pominięte)."""
    end = last_usable_day(analysis_date)
    s0 = season_start or default_season_start(analysis_date)
    kbw = w.climatic_water_balance
    i_req = min(_idx(w, end), len(w.dates) - 1)
    valid = np.flatnonzero(~np.isnan(kbw[: i_req + 1])) if i_req >= 0 else np.array([], dtype=int)
    until = w.dates[valid[-1]].astype(object) if valid.size else None
    i0 = _idx(w, s0)
    if until is None or until < s0 or i0 < 0:
        return SeasonSums(s0, until, 0, None, None, None, None, None)
    n = (until - s0).days + 1
    p_cur = float(np.nansum(w.precip[i0 : i0 + n]))
    e_cur = float(np.nansum(w.et0[i0 : i0 + n]))
    ps, es = [], []
    for k in range(1, years + 1):
        ik = _idx(w, shift_years(s0, k))
        p_k, e_k = _segment(w.precip, ik, n), _segment(w.et0, ik, n)
        if p_k is None or e_k is None or np.isnan(p_k + e_k).mean() > MAX_MISSING_YEAR:
            continue
        ps.append(float(np.nansum(p_k)))
        es.append(float(np.nansum(e_k)))
    i_until = _idx(w, until)
    recent = w.et0[max(0, i_until - 6) : i_until + 1]
    return SeasonSums(
        s0, until, n, round(p_cur, 1), round(float(np.mean(ps)), 1) if ps else None,
        round(e_cur, 1), round(float(np.mean(es)), 1) if es else None,
        round(float(np.nanmean(recent)), 2) if recent.size and not np.isnan(recent).all() else None,
    )


# ── Bilans opad − ET0 z ostatnich tygodni (status poza sezonem i bez uprawy, A5b-1) ──────────

RECENT_DAYS = 30


@dataclass
class RecentBalance:
    days: int
    start: date | None
    until: date | None
    balance_mm: float | None
    mean_mm: float | None
    deviation_mm: float | None
    lower_years: int | None
    of_years: int
    percentile: float | None  # % lat z NIŻSZYM bilansem w tym samym oknie (0 = najgorszy)


def recent_balance(w: DailyWeather, analysis_date: date, days: int = RECENT_DAYS, years: int = 10) -> RecentBalance:
    """KBW = opad − ET0 z ostatnich `days` dni z danymi (do dnia przed analizą) i te same dni w `years` latach."""
    until = data_until_for(w, last_usable_day(analysis_date))
    if until is None:
        return RecentBalance(days, None, None, None, None, None, None, 0, None)
    start = until - timedelta(days=days - 1)
    kbw = w.climatic_water_balance
    seg = _segment(kbw, _idx(w, start), days)
    if seg is None or np.isnan(seg).mean() > MAX_MISSING_MONTH:
        return RecentBalance(days, start, until, None, None, None, None, 0, None)
    cur = float(round(float(np.nansum(seg))))  # mm do całości; odchylenie = różnica zaokrąglonych (jedno źródło liczby)
    prev = []
    for k in range(1, years + 1):
        sk = _segment(kbw, _idx(w, shift_years(start, k)), days)
        if sk is not None and np.isnan(sk).mean() <= MAX_MISSING_MONTH:
            prev.append(float(np.nansum(sk)))
    if not prev:
        return RecentBalance(days, start, until, cur, None, None, None, 0, None)
    lower = int(sum(x < float(np.nansum(seg)) for x in prev))
    mean = float(round(float(np.mean(prev))))
    return RecentBalance(days, start, until, cur, mean, cur - mean, lower, len(prev),
                         round(100.0 * lower / len(prev), 1))
