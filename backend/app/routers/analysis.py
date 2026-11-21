"""GET /api/analysis?parcel_id=&crop=&date= – pełna analiza wodna działki (kamień milowy 1).

Kontrakt odpowiedzi: app/schemas/analysis.py (AnalysisResponse).

Kolejność (A4/A5): ULDK → równolegle pogoda 10 lat (NASA POWER, zapasowo archiwum Open-Meteo), gleba IUNG,
klasy EGiB, frakcje SoilGrids, mapa glebowo-rolnicza, prognoza Open-Meteo (gdy data = dziś) → bilans wody i model FAO-56 (analysis.water_balance)
→ ocena (analysis.scoring) → pewność (analysis.confidence) → przyczyny (analysis.causes) → rekomendacje
(analysis.recommendations, reguły YAML). Awaria jednego źródła obniża pewność, nie wywraca analizy.
Endpointy /api/dev/* – TYMCZASOWE (usunąć przy końcowym sprzątaniu).
"""

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.analysis.et0 import DailyWeather
from app.analysis.crops import get_crop
from app.analysis.soil import assess_soil
from app.analysis.soil import to_contract as soil_to_contract
from app.analysis.causes import build_causes
from app.analysis.confidence import ConfidenceInputs, reliability
from app.analysis.crops import CROPS, PHASE_LABELS
from app.analysis.facts import build_facts
from app.analysis.recommendations import Evaluation, evaluate
from app.analysis.scoring import overall_status
from app.analysis.soil_texture import enrich_soil
from app.analysis.water_balance import (
    HorizonDay,
    SoilWaterResult,
    build_history,
    history_range,
    season_sums,
    shift_years,
    soil_water_model,
)
from app.analysis.water_balance import to_contract as model_to_contract
from app.core.cache import stale_scope
from app.core.config import settings
from app.core.http import SourceError, http_error, in_poland
from app.routers.parcel import parcel_out, resolve_parcel
from app.schemas.analysis import (
    AnalysisResponse,
    CropId,
    History,
    CropSeason,
    Indicator,
    Indicators,
    IrrigationPlan,
    LoadingStep,
    Recommendation,
    RiskIndicator,
    SatelliteIndicator,
    Soil,
    SoilWaterState,
    SourceStatus,
    SourceTag,
    YearStress,
)
from app.schemas.parcel import ErrorDetail
from app.sources import iung, kieg, soil_map, soilgrids, weather_openmeteo, weather_power

router = APIRouter(prefix="/api", tags=["analiza"])


# ── Pogoda z 10 lat: główne źródło NASA POWER, zapasowe archiwum Open-Meteo (D1) ────────────


@dataclass
class WeatherLoad:
    weather: DailyWeather
    start: dt.date
    end: dt.date
    fallback_used: bool
    fetch_ms: int
    notes: list[str] = field(default_factory=list)


async def load_weather_history(
    lon: float, lat: float, analysis_date: dt.date, season_start: dt.date | None = None
) -> WeatherLoad:
    """Dane dobowe od 1 stycznia (rok sezonu − 10) do dnia przed datą analizy.

    NASA POWER nie odpowie (timeout, 5xx, 429…) → archiwum Open-Meteo. Oba zawiodą → SourceError.
    """
    start, end = history_range(analysis_date, season_start, settings.history_years)
    t0 = perf_counter()
    notes: list[str] = []
    try:
        w = await weather_power.fetch(lon, lat, start, end)
        fallback = False
    except SourceError as primary:
        notes.append(f"{weather_power.SOURCE_SHORT} niedostępne ({primary.message}) – użyto archiwum Open-Meteo.")
        try:
            w = await weather_openmeteo.fetch_archive(lon, lat, start, end)
        except SourceError as backup:
            raise SourceError(
                f"{weather_power.SOURCE_SHORT} i {weather_openmeteo.ARCHIVE_SOURCE_SHORT}",
                f"{primary.message}; {backup.message}",
            ) from backup
        fallback = True
    return WeatherLoad(w, start, end, fallback, int((perf_counter() - t0) * 1000), notes)


# ── TYMCZASOWE (deweloperskie) ──────────────────────────────────────────────────────────────
# GET /api/dev/weather-history – podgląd sekcji `history` przed powstaniem pełnego /api/analysis.
# ZNIKNIE razem z modelami Dev* poniżej, gdy /api/analysis zwróci prawdziwy wynik.
# Modele Dev* celowo NIE są w schemas/ – to nie jest kontrakt z frontendem.


class DevWeatherSource(BaseModel):
    name: str
    url: str
    resolution: str
    period_start: dt.date = Field(description="Początek pobranego zakresu")
    period_end: dt.date = Field(description="Koniec pobranego zakresu (dzień przed datą analizy)")
    data_until: dt.date | None = Field(description="Ostatni dzień z kompletem opadu i ET0")
    fallback_used: bool
    et0_methods: dict[str, int] = Field(description="Liczba dni wg metody ET0 w całym zakresie: PM / HG / OM / '' (brak)")
    et0_methods_season: dict[str, int]
    fetch_ms: int
    notes: list[str]


class DevBalanceMetrics(BaseModel):
    season_start: dt.date
    current_balance_mm: float | None
    mean_balance_mm: float | None
    deviation_mm: float | None
    percentile: float | None = Field(description="% lat porównawczych z niższym bilansem (0 = najgorszy)")
    lower_years: int | None
    band_years: list[int]
    excluded_years: list[int]
    longest_dry_spell_days: int | None
    longest_dry_spell_end: dt.date | None
    missing_days_season: int


class DevWeatherHistory(BaseModel):
    history: History
    source: DevWeatherSource
    metrics: DevBalanceMetrics
    limitations: list[str]


@router.get(
    "/dev/weather-history",
    response_model=DevWeatherHistory,
    tags=["deweloperskie (tymczasowe)"],
    responses={404: {"model": ErrorDetail}, 502: {"model": ErrorDetail}},
)
async def dev_weather_history(
    lat: float,
    lon: float,
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś)"),
) -> DevWeatherHistory:
    """TYMCZASOWE: sekcja historii pogody i bilansu wody dla punktu."""
    analysis_date = date or dt.date.today()
    if analysis_date > dt.date.today():
        raise HTTPException(status_code=422, detail={"message": "Data analizy nie może być z przyszłości."})
    if not in_poland(lon, lat):
        raise HTTPException(status_code=404, detail={"source": None, "message": "Punkt leży poza Polską."})
    try:
        load = await load_weather_history(lon, lat, analysis_date)
    except SourceError as exc:
        raise http_error(exc) from exc
    w = load.weather
    res = build_history(w, analysis_date, years=settings.history_years)
    limitations = [f"Pogoda uśredniona dla obszaru {w.resolution} ({w.source})."] + load.notes + res.limitations
    return DevWeatherHistory(
        history=res.history,
        source=DevWeatherSource(
            name=w.source,
            url=w.source_url,
            resolution=w.resolution,
            period_start=load.start,
            period_end=load.end,
            data_until=res.data_until,
            fallback_used=load.fallback_used,
            et0_methods=w.method_counts(),
            et0_methods_season=res.et0_methods_season,
            fetch_ms=load.fetch_ms,
            notes=load.notes,
        ),
        metrics=DevBalanceMetrics(
            season_start=res.season_start,
            current_balance_mm=res.current_balance_mm,
            mean_balance_mm=res.mean_balance_mm,
            deviation_mm=res.deviation_mm,
            percentile=res.percentile,
            lower_years=res.lower_years,
            band_years=res.band_years,
            excluded_years=res.excluded_years,
            longest_dry_spell_days=res.longest_dry_spell_days,
            longest_dry_spell_end=res.longest_dry_spell_end,
            missing_days_season=res.missing_days_season,
        ),
        limitations=limitations,
    )


# ── TYMCZASOWE (deweloperskie): GET /api/dev/soil?parcel_id= ────────────────────────────────
# Podgląd gleby działki przed powstaniem pełnego /api/analysis. ZNIKNIE razem z modelami DevSoil*.


class DevSoilShare(BaseModel):
    code: int
    label: str
    share: float


class DevSoil(BaseModel):
    parcel_id: str
    area_ha: float
    soil_capacity: Indicator = Field(description="Kontrakt: indicators.soil_capacity")
    dominant_code: int | None
    dominant_label: str | None
    shares: list[DevSoilShare]
    agricultural_share: float | None
    wod_mm: float | None
    classes: list[str] | None = Field(description="Klasy bonitacyjne EGiB (informacyjnie)")
    land_use: list[str] | None
    not_agricultural: bool
    not_agricultural_reason: str | None
    method: str | None = Field(description="wcs | punkty")
    cells: int | None
    sources: list[SourceStatus] = Field(description="Kontrakt: reliability.sources")
    limitations: list[str] = Field(description="Kontrakt: reliability.limitations")
    degrades_confidence: bool
    timings_ms: dict[str, int]


@router.get(
    "/dev/soil",
    response_model=DevSoil,
    tags=["deweloperskie (tymczasowe)"],
    responses={404: {"model": ErrorDetail}, 409: {"description": "Kilka działek"}, 502: {"model": ErrorDetail}},
)
async def dev_soil(parcel_id: str = Query(description="Identyfikator działki ULDK")) -> DevSoil:
    """TYMCZASOWE: gleba działki – IUNG (WCS, zapasowo punkty) + klasy EGiB, równolegle."""
    t0 = perf_counter()
    try:
        p = await resolve_parcel(parcel_id, None, None)
    except SourceError as exc:
        raise http_error(exc) from exc
    t1 = perf_counter()

    async def timed(coro):
        s = perf_counter()
        try:
            return await coro, int((perf_counter() - s) * 1000)
        except SourceError as exc:  # awaria jednego źródła nie wywraca wyniku
            return exc, int((perf_counter() - s) * 1000)

    (iung_res, iung_ms), (kieg_res, kieg_ms) = await asyncio.gather(
        timed(iung.soil_for_parcel(p.geom_2180)), timed(kieg.classes_for_parcel(p.id, p.geom_2180))
    )
    a = assess_soil(iung_res, kieg_res)
    return DevSoil(
        parcel_id=p.id,
        area_ha=p.area_ha,
        soil_capacity=a.soil_capacity,
        dominant_code=a.dominant_code,
        dominant_label=a.dominant_label,
        shares=[DevSoilShare(code=s.code, label=s.label, share=s.share) for s in a.shares],
        agricultural_share=a.agricultural_share,
        wod_mm=a.wod_mm,
        classes=a.classes,
        land_use=a.land_use,
        not_agricultural=a.not_agricultural,
        not_agricultural_reason=a.not_agricultural_reason,
        method=a.method,
        cells=a.cells,
        sources=a.sources,
        limitations=a.limitations,
        degrades_confidence=a.degrades_confidence,
        timings_ms={
            "uldk": int((t1 - t0) * 1000),
            "iung": iung_ms,
            "kieg": kieg_ms,
            "razem": int((perf_counter() - t0) * 1000),
        },
    )


# ── TYMCZASOWE (deweloperskie): GET /api/dev/water?parcel_id=&crop=&date= ───────────────────
# Pogoda (A1) + gleba (A2) + ciągły model wody w glebie FAO-56 (A3/A3b) w formacie kontraktu.
# ZNIKNIE razem z modelami DevWater*, gdy /api/analysis zwróci prawdziwy wynik.


class DevWaterModel(BaseModel):
    window_start: dt.date | None
    init_balance_mm: float | None
    data_until: dt.date | None
    root_depth_m: float | None
    taw_root_mm: float | None
    raw_root_mm: float | None
    taw_profile_mm: float | None
    d1_mm: float | None = Field(description="Ubytek wody w strefie czynnej")
    dtot_mm: float | None = Field(description="Ubytek wody w profilu 1 m")
    percolation_mm: float | None
    stress_days_season: int | None
    mean_prev_stress_days: float | None
    horizon_kind: str | None
    days_to_stress: int | None
    risk: str | None
    horizon: list[dict] = Field(description="[{date, d1_mm, raw_mm, phase}]")


class DevWater(BaseModel):
    parcel_id: str
    crop: CropId
    crop_label: str
    analysis_date: dt.date
    soil: Soil = Field(description="Kontrakt: soil")
    non_agricultural: bool
    crop_season: CropSeason = Field(description="Kontrakt: crop_season")
    soil_water: SoilWaterState = Field(description="Kontrakt: soil_water")
    irrigation: IrrigationPlan = Field(description="Kontrakt: irrigation")
    soil_water_pct: Indicator = Field(description="Kontrakt: indicators.soil_water_pct")
    soil_water_mm: Indicator = Field(description="Kontrakt: indicators.soil_water_mm")
    risk_7d: RiskIndicator = Field(description="Kontrakt: indicators.risk_7d")
    stress_days_by_year: list[YearStress] = Field(description="Kontrakt: history.stress_days_by_year")
    irrigation_recommendation: Recommendation | None = Field(description="Kontrakt: recommendations[] (nawadnianie)")
    model: DevWaterModel | None
    weather_source: str
    limitations: list[str]
    timings_ms: dict[str, int]


async def _forecast_days(lon: float, lat: float) -> list[HorizonDay]:
    """Open-Meteo: 7 ostatnich dni (uzupełnienie opóźnienia NASA POWER) + 16 dni prognozy."""
    fc = await weather_openmeteo.fetch(lon, lat, days=16, past_days=7)
    return [
        HorizonDay(d.day, np.nan if d.precip_mm is None else d.precip_mm, np.nan if d.et0_mm is None else d.et0_mm)
        for d in fc.days
    ]


@router.get(
    "/dev/water",
    response_model=DevWater,
    tags=["deweloperskie (tymczasowe)"],
    responses={404: {"model": ErrorDetail}, 409: {"description": "Kilka działek"}, 502: {"model": ErrorDetail}},
)
async def dev_water(
    parcel_id: str = Query(description="Identyfikator działki ULDK"),
    crop: CropId = Query(description="Uprawa"),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś)"),
) -> DevWater:
    """TYMCZASOWE: stan wody w glebie (także poza sezonem), faza uprawy, ryzyko 7 dni, dni stresu, nawadnianie."""
    t0 = perf_counter()
    today = dt.date.today()
    analysis_date = date or today
    if analysis_date > today:
        raise HTTPException(status_code=422, detail={"message": "Data analizy nie może być z przyszłości."})
    try:
        p = await resolve_parcel(parcel_id, None, None)
    except SourceError as exc:
        raise http_error(exc) from exc
    c = p.geom_4326.centroid
    t1 = perf_counter()

    async def safe(coro):
        try:
            return await coro
        except SourceError as exc:  # awaria jednego źródła nie wywraca wyniku
            return exc

    weather_res, iung_res, kieg_res, fc_res = await asyncio.gather(
        safe(load_weather_history(c.x, c.y, analysis_date)),
        safe(iung.soil_for_parcel(p.geom_2180)),
        safe(kieg.classes_for_parcel(p.id, p.geom_2180)),
        safe(_forecast_days(c.x, c.y)) if analysis_date == today else asyncio.sleep(0, result=None),
    )
    t2 = perf_counter()
    soil_a = assess_soil(iung_res, kieg_res)
    soil = soil_to_contract(soil_a)
    crop_obj = get_crop(crop)
    limitations = list(soil_a.limitations)
    weather_source = "—"
    res: SoilWaterResult | None = None
    no_model = None
    if isinstance(weather_res, SourceError):
        no_model = f"Brak danych pogodowych ({weather_res.message}) – modelu wody w glebie nie policzono."
    elif soil_a.not_agricultural or soil_a.wod_mm is None:
        no_model = soil.non_agricultural_note or "Brak danych o glebie (WOD) – modelu wody w glebie nie policzono."
        weather_source = weather_res.weather.source
    else:
        forecast = None if fc_res is None or isinstance(fc_res, SourceError) else fc_res
        if isinstance(fc_res, SourceError):
            limitations.append(f"Prognoza Open-Meteo niedostępna ({fc_res.message}) – ryzyko ze scenariusza typowej pogody.")
        w = weather_res.weather
        res = soil_water_model(
            w, crop_obj, soil_a.wod_mm, analysis_date, forecast,
            soil_category=soil_a.dominant_mineral, years=settings.history_years,
        )
        limitations = (
            [f"Pogoda uśredniona dla obszaru {w.resolution} ({w.source})."] + weather_res.notes + res.limitations + limitations
        )
        weather_source = w.source
    if res is None:
        limitations.insert(0, no_model)
        s0, h0 = crop_obj.season(crop_obj.season_year_for(analysis_date))
        info = crop_obj.day_info(analysis_date)
        res = SoilWaterResult(crop, "brak_danych", s0.year, s0, h0, info.phase, PHASE_LABELS[info.phase], info.sensitive)
    out = model_to_contract(res, crop_obj, analysis_date, no_model_note=no_model)
    t3 = perf_counter()
    return DevWater(
        parcel_id=p.id,
        crop=crop,
        crop_label=crop_obj.label,
        analysis_date=analysis_date,
        soil=soil,
        non_agricultural=soil_a.not_agricultural,
        crop_season=out.crop_season,
        soil_water=out.soil_water,
        irrigation=out.irrigation,
        soil_water_pct=out.soil_water_pct,
        soil_water_mm=out.soil_water_mm,
        risk_7d=out.risk_7d,
        stress_days_by_year=out.stress_days_by_year,
        irrigation_recommendation=out.irrigation_rec,
        model=None if no_model else DevWaterModel(
            window_start=res.window_start, init_balance_mm=res.init_balance_mm, data_until=res.data_until,
            root_depth_m=res.root_depth_m, taw_root_mm=res.taw_root_mm, raw_root_mm=res.raw_root_mm,
            taw_profile_mm=res.taw_profile_mm, d1_mm=res.d1_mm, dtot_mm=res.dtot_mm,
            percolation_mm=res.percolation_mm, stress_days_season=res.stress_days_season,
            mean_prev_stress_days=res.mean_prev_stress_days, horizon_kind=res.horizon_kind,
            days_to_stress=res.days_to_stress, risk=res.risk,
            horizon=[{"date": d.isoformat(), "d1_mm": a, "raw_mm": r, "phase": ph} for d, a, r, ph in res.horizon],
        ),
        weather_source=weather_source,
        limitations=limitations,
        timings_ms={
            "uldk": int((t1 - t0) * 1000),
            "zrodla_rownolegle": int((t2 - t1) * 1000),
            "model": int((t3 - t2) * 1000),
            "razem": int((perf_counter() - t0) * 1000),
        },
    )


# ═══ PEŁNE /api/analysis (A4) ═══════════════════════════════════════════════════════════════

ANALYSIS_BUDGET_S = 27.0  # cała analiza < 30 s (wymóg KOWR) – zapas na serializację


def _step(id_: str, label: str, state: str, note: str | None = None, ms: int | None = None) -> LoadingStep:
    return LoadingStep(id=id_, label=label, state=state, note=note, duration_ms=ms)


def _no_model_result(crop_obj, analysis_date: dt.date) -> SoilWaterResult:
    s0, h0 = crop_obj.season(crop_obj.season_year_for(analysis_date))
    info = crop_obj.day_info(analysis_date)
    return SoilWaterResult(crop_obj.id, "brak_danych", s0.year, s0, h0, info.phase, PHASE_LABELS[info.phase], info.sensitive)


def _balance_indicator(wb) -> Indicator:
    if wb is None or wb.current_balance_mm is None:
        return Indicator(value=None, unit="mm", status="no_data", note="brak danych pogodowych",
                         source_tag=SourceTag(kind="brak_danych", source="NASA POWER"))
    p = wb.percentile
    status = "no_data" if p is None else ("risk" if p < 20 else "warn" if p < 40 else "ok")
    note = None
    if wb.deviation_mm is not None and wb.mean_balance_mm is not None:
        more = "mniej" if wb.deviation_mm < 0 else "więcej"
        note = (f"o {abs(wb.deviation_mm):.0f} mm {more} niż zwykle (średnia 10 lat {wb.mean_balance_mm:.0f} mm), "
                f"od {wb.season_start:%d.%m}")
    return Indicator(value=wb.current_balance_mm, unit="mm", status=status, note=note,
                     source_tag=wb.history.source_tag)


def _hg_share(w, sums) -> float | None:
    if sums is None or sums.until is None or sums.days <= 0:
        return None
    i0 = int((np.datetime64(sums.season_start, "D") - w.dates[0]).astype(int))
    m = w.et0_method[max(0, i0) : i0 + sums.days]
    return float((m == "HG").mean()) if len(m) else None


def validate_params(crop: str | None, analysis_date: dt.date, previous_crop: str | None, today: dt.date) -> None:
    if not crop:
        raise HTTPException(status_code=422, detail={"message": "Wybierz uprawę – od niej zależy ocena wody w glebie."})
    if crop not in CROPS:
        raise HTTPException(status_code=422, detail={"message": f"Nieznana uprawa: {crop}."})
    if previous_crop and previous_crop != "nie_wiem" and previous_crop not in CROPS:
        raise HTTPException(status_code=422, detail={"message": f"Nieznana uprawa z poprzedniego roku: {previous_crop}."})
    if analysis_date > today:
        raise HTTPException(status_code=422, detail={"message": "Data analizy nie może być z przyszłości."})
    if analysis_date < shift_years(today, settings.history_years):
        raise HTTPException(status_code=422, detail={"message": f"Data analizy może być najwyżej {settings.history_years} lat wstecz."})


async def run_analysis(
    parcel_id: str, crop: str | None, analysis_date: dt.date | None = None, previous_crop: str | None = None
) -> AnalysisResponse:
    """Pełna analiza (wspólna dla /api/analysis, raportu PDF i rozgrzewki przykładów demo)."""
    with stale_scope() as stale_hits:
        return await _run(parcel_id, crop, analysis_date, previous_crop, stale_hits)


async def _run(parcel_id: str, crop: str | None, date: dt.date | None, previous_crop: str | None,
               stale_hits: list) -> AnalysisResponse:
    t0 = perf_counter()
    today = dt.date.today()
    analysis_date = date or today
    validate_params(crop, analysis_date, previous_crop, today)
    crop_obj = get_crop(crop)
    steps: list[LoadingStep] = []

    # ── 1. działka (ULDK) ──
    s = perf_counter()
    try:
        p = await asyncio.wait_for(resolve_parcel(parcel_id, None, None), timeout=settings.uldk_timeout_s * 2 + 1)
    except SourceError as exc:
        raise http_error(exc) from exc
    except asyncio.TimeoutError as exc:
        raise http_error(SourceError("ULDK GUGiK", "usługa nie odpowiada")) from exc
    steps.append(_step("parcel", "Szukam działki (ULDK GUGiK)", "done", ms=int((perf_counter() - s) * 1000)))
    c = p.geom_4326.centroid
    rp = p.geom_4326.representative_point()

    # ── 2. źródła równolegle, z łącznym limitem czasu ──
    remaining = max(3.0, ANALYSIS_BUDGET_S - (perf_counter() - t0))

    async def timed(name: str, coro):
        st = perf_counter()
        try:
            res = await asyncio.wait_for(coro, timeout=remaining)
        except SourceError as exc:
            res = exc
        except asyncio.TimeoutError:
            res = SourceError(name, "przekroczono limit czasu analizy")
        return res, int((perf_counter() - st) * 1000)

    is_today = analysis_date == today
    (
        (w_res, w_ms), (iung_res, iung_ms), (kieg_res, kieg_ms), (fc_res, fc_ms), (sg_res, sg_ms), (sm_res, sm_ms),
    ) = await asyncio.gather(
        timed("NASA POWER", load_weather_history(c.x, c.y, analysis_date)),
        timed("IUNG-PIB", iung.soil_for_parcel(p.geom_2180)),
        timed("KIEG / EGiB GUGiK", kieg.classes_for_parcel(p.id, p.geom_2180)),
        timed("Open-Meteo (prognoza)", _forecast_days(c.x, c.y)) if is_today else asyncio.sleep(0, result=(None, 0)),
        timed(soilgrids.SOURCE, soilgrids.texture_at(rp.x, rp.y)),
        timed(soil_map.SOURCE, soil_map.soil_map_at(rp.x, rp.y)),
    )
    if isinstance(w_res, SourceError):  # bez pogody nic nie da się policzyć
        raise http_error(w_res)
    w = w_res.weather

    def state(res) -> str:
        return "error" if isinstance(res, SourceError) else "done"

    def err(res) -> str | None:
        return res.message if isinstance(res, SourceError) else None

    steps.append(_step("weather", f"Pobieram pogodę z 10 lat ({w.source})", "done",
                       note="źródło zapasowe" if w_res.fallback_used else None, ms=w_ms))
    steps.append(_step("soil", "Sprawdzam glebę (IUNG-PIB)", state(iung_res), note=err(iung_res), ms=iung_ms))
    kieg_note = err(kieg_res) or (kieg_res.note if kieg_res else None)
    steps.append(_step("egib", "Klasy bonitacyjne (EGiB)", state(kieg_res), note=kieg_note, ms=kieg_ms))
    steps.append(_step("soilgrids", "Frakcje i przepuszczalność gleby (SoilGrids)", state(sg_res), note=err(sg_res), ms=sg_ms))
    sm_note = err(sm_res) or (None if sm_res is not None else "brak konturu w tym miejscu")
    steps.append(_step("soil_map", "Mapa glebowo-rolnicza (GUGiK)", state(sm_res), note=sm_note, ms=sm_ms))
    if is_today:
        steps.append(_step("forecast", "Prognoza pogody (Open-Meteo)", state(fc_res), note=err(fc_res), ms=fc_ms))
    else:
        steps.append(_step("forecast", "Prognoza pogody", "done", note="data historyczna – scenariusz typowej pogody", ms=0))
    steps.append(_step("satellite", "Zdjęcia satelitarne", "pending", note="w przygotowaniu – brak danych"))
    steps.append(_step("terrain", "Analizuję teren", "pending", note="w przygotowaniu – brak danych"))

    # ── 3. obliczenia ──
    s = perf_counter()
    soil_a = assess_soil(iung_res, kieg_res)
    soil_c, soil_lim = enrich_soil(soil_to_contract(soil_a), sg_res, sm_res)
    wb = build_history(w, analysis_date, years=settings.history_years)
    sums = season_sums(w, analysis_date, years=settings.history_years)
    forecast = None if fc_res is None or isinstance(fc_res, SourceError) else fc_res
    no_model = None
    if soil_a.not_agricultural or soil_a.wod_mm is None:
        no_model = soil_c.non_agricultural_note or "Brak danych o glebie (WOD) – modelu wody w glebie nie policzono."
        model = None
    else:
        model = soil_water_model(w, crop_obj, soil_a.wod_mm, analysis_date, forecast,
                                 soil_category=soil_a.dominant_mineral, years=settings.history_years)
    out = model_to_contract(model or _no_model_result(crop_obj, analysis_date), crop_obj, analysis_date, no_model_note=no_model)
    steps.append(_step("balance", "Liczę bilans wody i wodę w glebie (FAO-56)", "done" if model else "error",
                       note=no_model, ms=int((perf_counter() - s) * 1000)))

    s = perf_counter()
    prev = previous_crop if previous_crop in CROPS else None
    facts = build_facts(crop_obj, analysis_date, soil_a, model, wb, sums, soil_c=soil_c, previous_crop=prev)
    status = overall_status(facts, soil_c)
    causes = [] if soil_a.not_agricultural else build_causes(facts)
    evaluation = evaluate(facts) if model and not soil_a.not_agricultural else Evaluation([])
    sm_status = None if isinstance(sm_res, SourceError) else ("ok" if sm_res is not None else "brak_konturu")
    rel, _premises, _points = reliability(ConfidenceInputs(
        analysis_date=analysis_date, today=today, parcel_fetched=p.fetched_at.date(), weather_name=w.source,
        weather_resolution=w.resolution, weather_fallback=w_res.fallback_used, weather_notes=w_res.notes,
        weather_until=wb.data_until, forecast_ok=(None if not is_today else forecast is not None),
        forecast_error=err(fc_res), soil=soil_a, model=model, wb=wb,
        hg_share_season=_hg_share(w, sums), extra_limitations=soil_lim,
        soilgrids="brak" if isinstance(sg_res, SourceError) else "ok", soilgrids_error=err(sg_res),
        soil_map=sm_status or "brak", soil_map_error=err(sm_res),
        soil_map_year=sm_res.mapped_year if sm_status == "ok" else None,
        stale=list(stale_hits),
    ))
    history = wb.history.model_copy(update={"stress_days_by_year": out.stress_days_by_year})
    no_sat = SourceTag(kind="brak_danych", source="Sentinel-2 L2A")
    indicators = Indicators(
        soil_water_pct=out.soil_water_pct,
        soil_water_mm=out.soil_water_mm,
        risk_7d=out.risk_7d,
        crop_health=SatelliteIndicator(value=None, unit="pkt", status="no_data", note="zdjęcia satelitarne – w przygotowaniu", source_tag=no_sat),
        plant_moisture=SatelliteIndicator(value=None, unit="pkt", status="no_data", note="zdjęcia satelitarne – w przygotowaniu", source_tag=no_sat),
        water_balance_season=_balance_indicator(wb),
        soil_capacity=soil_a.soil_capacity,
    )
    steps.append(_step("scoring", "Ocena, pewność, przyczyny i rekomendacje", "done", ms=int((perf_counter() - s) * 1000)))
    steps.append(_step("total", "Cała analiza", "done", ms=int((perf_counter() - t0) * 1000)))

    return AnalysisResponse(
        parcel=parcel_out(p),
        crop=crop,
        previous_crop=previous_crop or None,
        analysis_date=analysis_date,
        historical=analysis_date < today,
        generated_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0),
        status=status,
        indicators=indicators,
        crop_season=out.crop_season,
        soil_water=out.soil_water,
        irrigation=out.irrigation,
        soil=soil_c,
        history=history,
        causes=causes,
        recommendations=evaluation.recommendations,
        reliability=rel,
        steps=steps,
    )


@router.get(
    "/analysis",
    response_model=AnalysisResponse,
    responses={404: {"model": ErrorDetail}, 409: {"description": "Kilka działek"}, 422: {"description": "Brak uprawy / zła data"},
               502: {"model": ErrorDetail}},
)
async def get_analysis(
    parcel_id: str = Query(description="Pełny identyfikator działki ULDK (albo „obręb numer”)"),
    crop: str | None = Query(None, description="Uprawa (15 upraw IUNG SMSR)"),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś, maks. 10 lat wstecz)"),
    previous_crop: str | None = Query(None, description="Uprawa w poprzednim roku (15 upraw albo 'nie_wiem') – płodozmian"),
) -> AnalysisResponse:
    """Pełna analiza wodna działki: ULDK → równolegle pogoda 10 lat, gleba IUNG, klasy EGiB, SoilGrids, mapa
    glebowo-rolnicza, prognoza (dla dziś) → model wody w glebie → ocena → pewność → przyczyny → rekomendacje.
    Awaria jednego źródła = brak danych i niższa pewność; 502 tylko bez działki (ULDK) albo bez pogody."""
    return await run_analysis(parcel_id, crop, date, previous_crop)
