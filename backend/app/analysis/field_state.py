"""Stan działki bez względu na uprawę (A5b-1, punkt 1 przepływu panelu: „Stan działki”).

Nie wiemy, co rośnie na działce (deklaracje ARiMR nie są publiczne), więc stan wody liczymy dla POKRYCIA
REFERENCYJNEGO FAO-56 (D50): hipotetyczna trawa, dla której definiuje się ET0 (Allen i in. 1998, rozdz. 2) –
Kc = 1 przez cały rok, korzenie w całym profilu ~1 m (WOD z IUNG, D25), p = 0,5 (FAO-56 tab. 22: pastwiska 0,6,
trawniki chłodnego klimatu 0,4), redukcja ewapotranspiracji Ks przy przesychaniu (równ. 84). To ta sama
powierzchnia, dla której IUNG liczy klimatyczny bilans wodny (KBW = opad − ET0), więc wynik jest spójny z KBW.
Goła gleba (ugór czarny) zaniżałaby przesychanie latem – woda paruje tylko z wierzchnich ~12 cm.

Wynik: zapas wody w profilu dziś, jego przebieg od 1 listopada (początek roku hydrologicznego; gdy od 1 XI minęło
< 30 dni – od 1 XI roku wcześniej) z pasmem z 10 lat, porównanie z tym samym dniem w 10 latach, bilans 30 dni.
"""

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from app.analysis.crops import KC_BARE, ZE_M, DayInfo
from app.analysis.et0 import DailyWeather
from app.analysis.water_balance import (
    MAX_MISSING_YEAR,
    PROFILE_DEPTH_M,
    HorizonDay,
    RecentBalance,
    _days,
    _observed,
    bridged_inputs,
    initial_state,
    last_usable_day,
    run,
    shift_years,
)

REFERENCE_KC = 1.0
REFERENCE_P = 0.5
# A18: dla rolnika bez symboli (Kc = 1 – tylko w źródle FIELD_SOURCE)
COVER_LABEL = ("liczone dla typowego pola z roślinami od marca do lipca, a po typowym terminie zbioru – dla gołej gleby; "
               "profil ok. 1 m")
FIELD_SOURCE = "Model wody w glebie FAO-56 – pokrycie referencyjne"
MIN_SERIES_DAYS = 30


GROWING_MONTHS = (3, 7)  # marzec–lipiec: okres wegetacji typowej uprawy polowej
_GROWING = DayInfo("referencja", REFERENCE_KC, PROFILE_DEPTH_M, False, False, 0, None)
_BARE = DayInfo("gola_gleba", KC_BARE, ZE_M, False, True, 0, None)


class ReferenceCover:
    """„Uprawa” referencyjna dla funkcji modelu (run, initial_state) – ten sam bilans co dla upraw."""

    id = "referencja"
    label = "pokrycie referencyjne"
    p = REFERENCE_P

    def day_info(self, d: date) -> DayInfo:
        """1 III–31 VII: pokrycie referencyjne (Kc = 1, korzenie w profilu 1 m); od 1 VIII (po typowym zbiorze zbóż)
        do końca lutego: goła gleba – parowanie tylko z wierzchniej warstwy (FAO-56 rozdz. 7), D65."""
        if GROWING_MONTHS[0] <= d.month <= GROWING_MONTHS[1]:
            return _GROWING
        return _BARE


REFERENCE = ReferenceCover()


def series_start(last: date) -> date:
    """1 listopada (rok hydrologiczny); gdy od niego minęło < 30 dni – 1 listopada rok wcześniej."""
    h = date(last.year, 11, 1) if last >= date(last.year, 11, 1) else date(last.year - 1, 11, 1)
    return h if (last - h).days >= MIN_SERIES_DAYS else date(h.year - 1, 11, 1)


@dataclass
class FieldStateResult:
    status: str  # "ok" | "brak_danych"
    series_start: date
    data_until: date | None = None
    water_pct: float | None = None
    water_mm: float | None = None
    taw_mm: float | None = None
    description: str = ""
    rank_lower: int | None = None
    rank_of: int | None = None
    series: list[tuple[date, float]] = field(default_factory=list)
    band: list[tuple[date, float, float, float]] = field(default_factory=list)  # (dzień, min, max, średnia)
    limitations: list[str] = field(default_factory=list)


def _pct(dtot: np.ndarray, taw: float) -> np.ndarray:
    return 100.0 * (1.0 - dtot / taw) if taw > 0 else np.zeros_like(dtot)


def describe(pct: float, pct_30_days_ago: float | None) -> str:
    rising = pct_30_days_ago is not None and pct - pct_30_days_ago > 1.0
    falling = pct_30_days_ago is not None and pct_30_days_ago - pct > 1.0
    if pct >= 90:
        return "zapas wody w glebie pełny"
    if pct < 30:
        return "bardzo mało wody w glebie" + (" – gleba nadal przesycha" if falling else "")
    if rising:
        return "gleba odbudowuje zapas wody"
    if pct < 50:
        return "mało wody w glebie" + (" – gleba przesycha" if falling else "")
    if falling:
        return "gleba traci wodę"
    return "zapas wody w normie"


def field_state_model(
    w: DailyWeather, wod_mm: float, analysis_date: date, forecast: list[HorizonDay] | None = None, years: int = 10,
) -> FieldStateResult:
    """Ciągły bilans pokrycia referencyjnego od 1 XI do dnia przed analizą + te same okresy w `years` latach."""
    L = last_usable_day(analysis_date)
    s0 = series_start(L)
    res = FieldStateResult("brak_danych", s0, taw_mm=round(wod_mm * PROFILE_DEPTH_M, 1))
    taw = wod_mm * PROFILE_DEPTH_M
    inputs = bridged_inputs(w, s0, L, forecast, years)
    if inputs is None or taw <= 0:
        res.limitations.append("Za mało danych pogodowych do stanu wody na działce.")
        return res
    p_in, e_in, res.data_until, notes = inputs
    res.limitations += notes
    st, bal = initial_state(w, REFERENCE, wod_mm, s0)
    if bal is None:
        res.limitations.append("Brak danych sprzed 1 listopada – stan wody na działce liczony od pełnego profilu.")
    days = _days(s0, L)
    tr = run(REFERENCE, wod_mm, days, np.array(p_in), np.array(e_in), st)
    pct = _pct(tr.dtot, taw)
    res.status = "ok"
    res.water_pct = round(float(pct[-1]))
    res.water_mm = round(taw - float(tr.dtot[-1]), 1)
    res.series = [(d, round(float(v), 1)) for d, v in zip(days, pct)]
    res.description = describe(float(pct[-1]), float(pct[-31]) if len(pct) > 30 else None)

    rows, finals = [], []
    for k in range(1, years + 1):
        sk, lk = shift_years(s0, k), shift_years(L, k)
        o = _observed(w, sk, lk)
        if o is None or np.isnan(o[0] + o[1]).mean() > MAX_MISSING_YEAR:
            continue
        stk, bk = initial_state(w, REFERENCE, wod_mm, sk)
        if bk is None:
            continue
        trk = run(REFERENCE, wod_mm, _days(sk, lk), o[0], o[1], stk)
        pk = _pct(trk.dtot, taw)
        finals.append(float(pk[-1]))
        rows.append(pk)
    if finals:
        res.rank_lower = int(sum(x < float(pct[-1]) for x in finals))
        res.rank_of = len(finals)
        n = min(len(pct), *(len(r) for r in rows))
        m = np.vstack([r[:n] for r in rows])
        res.band = [(days[i], round(float(m[:, i].min()), 1), round(float(m[:, i].max()), 1), round(float(m[:, i].mean()), 1))
                    for i in range(n)]
    if len(finals) < years:
        res.limitations.append(f"Stan wody na działce porównany z {len(finals)} z {years} poprzednich lat.")
    return res


def recent_note(rb: RecentBalance) -> str | None:
    if rb.balance_mm is None or rb.until is None:
        return None
    txt = f"{rb.start:%d.%m}–{rb.until:%d.%m.%Y}"
    if rb.deviation_mm is None:
        return txt
    if abs(rb.deviation_mm) < 5:
        return f"{txt}, tyle co zwykle"
    more = "mniej" if rb.deviation_mm < 0 else "więcej"
    return f"{txt}, o {abs(rb.deviation_mm):.0f} mm {more} niż zwykle (niższy w {rb.lower_years} z {rb.of_years} lat)"


# ── Wynik → kontrakt (schemas/analysis.py: FieldState) ──────────────────────────────────────


def water_indicators(res: FieldStateResult, analysis_date: date, level: str | None = None):
    """(soil_water_pct, soil_water_mm, SoilWaterState) – profil ~1 m pod pokryciem referencyjnym. A20: status wskaźnika
    = stopień ze scoring.drought_level (te same progi co status działki)."""
    from app.schemas.analysis import BalanceRank, Indicator, SoilWaterState, SourceTag

    if res.status != "ok":
        note = res.limitations[0] if res.limitations else "Brak danych do stanu wody na działce."
        tag = SourceTag(kind="brak_danych", source=FIELD_SOURCE)
        return (Indicator(value=None, unit="%", status="no_data", note=note, source_tag=tag),
                Indicator(value=None, unit="mm", status="no_data", note=note, source_tag=tag),
                SoilWaterState(scope="profil", depth_m=PROFILE_DEPTH_M, description=note))
    # A20: data = ostatni dzień danych pogodowych (dni po nim to prognoza / scenariusz typowej pogody)
    tag = SourceTag(kind="szacunek_modelu", date=res.data_until or last_usable_day(analysis_date), source=FIELD_SOURCE)
    if level is None or level == "no_data":
        from app.analysis.scoring import drought_level

        level = drought_level(res.water_pct, res.rank_lower if (res.rank_of or 0) >= 5 else None)
    status = level
    pct = Indicator(value=res.water_pct, unit="%", label="stan działki", status=status,
                    note=f"{res.description} (profil ok. 1 m, typowe pole z roślinami)", source_tag=tag)
    mm = Indicator(value=res.water_mm, unit="mm", status=status, note="woda dostępna dla roślin, profil ok. 1 m",
                   source_tag=tag)
    sw = SoilWaterState(scope="profil", depth_m=PROFILE_DEPTH_M, description=res.description,
                        rank=BalanceRank(lower_years=res.rank_lower, of_years=res.rank_of) if res.rank_of else None)
    return pct, mm, sw


def balance_30d_indicator(rb: RecentBalance, source: str):
    from app.schemas.analysis import Indicator, SourceTag

    if rb.balance_mm is None:
        return Indicator(value=None, unit="mm", status="no_data", note="brak danych pogodowych z ostatnich 30 dni",
                         source_tag=SourceTag(kind="brak_danych", source=source))
    p = rb.percentile
    status = "no_data" if p is None else ("risk" if p < 20 else "warn" if p < 40 else "ok")
    return Indicator(value=rb.balance_mm, unit="mm", label="ostatnie 30 dni", status=status, note=recent_note(rb),
                     source_tag=SourceTag(kind="obliczenia", date=rb.until, source=source))


def to_contract(res: FieldStateResult, rb: RecentBalance, status, analysis_date: date, weather_source: str):
    from app.schemas.analysis import BalanceRank, BandPoint, FieldState, SeriesPoint, SourceTag

    pct, mm, sw = water_indicators(res, analysis_date, getattr(status, "level", None))
    return FieldState(
        status=status, cover=COVER_LABEL, soil_water_pct=pct, soil_water_mm=mm, soil_water=sw,
        series_start=res.series_start,
        series=[SeriesPoint(date=d, value=v) for d, v in res.series],
        series_band=[BandPoint(date=d, min=a, max=b, mean=m) for d, a, b, m in res.band],
        balance_30d=balance_30d_indicator(rb, weather_source),
        balance_30d_rank=BalanceRank(lower_years=rb.lower_years, of_years=rb.of_years) if rb.lower_years is not None else None,
        source_tag=pct.source_tag if res.status == "ok" else SourceTag(kind="brak_danych", source=FIELD_SOURCE),
    )
