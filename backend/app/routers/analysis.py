"""GET /api/analysis?parcel_id=&crop=&date= – analiza wodna działki (SZKIELET, HTTP 501).

Kontrakt odpowiedzi: app/schemas/analysis.py (AnalysisResponse).

TODO (osoba A), kolejność z CLAUDE.md (P0):
1. działka: routers.parcel.resolve_parcel
2. równolegle (asyncio.gather, timeout, cache): pogoda 10 lat (load_weather_history – gotowe),
   prognoza (sources.weather_openmeteo), gleba (sources.iung) – tylko dane sprzed `date`
3. ET0 / bilans (analysis.et0, analysis.water_balance – gotowe), model wody w glebie FAO-56
4. ocena, pewność, przyczyny (analysis.scoring), rekomendacje z reguł YAML (analysis.recommendations)
5. awaria jednego źródła obniża pewność (reliability), nie wywraca analizy
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
from app.analysis.water_balance import (
    HorizonDay,
    SoilWaterResult,
    build_history,
    history_range,
    soil_water_model,
    to_contract_indicators,
)
from app.core.config import settings
from app.core.http import SourceError, http_error, in_poland, not_implemented
from app.routers.parcel import resolve_parcel
from app.schemas.analysis import (
    AnalysisResponse,
    CropId,
    History,
    Indicator,
    Recommendation,
    RiskIndicator,
    Soil,
    SourceStatus,
    YearStress,
)
from app.schemas.parcel import ErrorDetail
from app.sources import iung, kieg, weather_openmeteo, weather_power

router = APIRouter(prefix="/api", tags=["analiza"])


@router.get(
    "/analysis",
    response_model=AnalysisResponse,
    responses={404: {"model": ErrorDetail}, 501: {"description": "W budowie"}, 502: {"model": ErrorDetail}},
)
async def get_analysis(
    parcel_id: str = Query(description="Pełny identyfikator działki ULDK"),
    crop: CropId = Query(description="Uprawa (15 upraw IUNG SMSR)"),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś, maks. 10 lat wstecz)"),
) -> AnalysisResponse:
    raise not_implemented("Analiza wodna działki")


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
# Pogoda (A1) + gleba (A2) + model wody w glebie FAO-56 (A3) w formacie kontraktu.
# ZNIKNIE razem z modelami DevWater*, gdy /api/analysis zwróci prawdziwy wynik.


class DevWaterSeason(BaseModel):
    status: str = Field(description="w_sezonie | przed_sezonem | po_sezonie | brak_danych")
    start: dt.date
    end: dt.date
    day_of_season: int | None
    stage: str | None
    kc: float | None


class DevWaterModel(BaseModel):
    taw_mm: float
    raw_mm: float
    root_depth_m: float
    p: float
    dr_mm: float | None
    dr0_mm: float | None
    winter_balance_mm: float | None
    winter_window_start: dt.date | None
    raw_exceeded: bool | None
    ks: float | None
    percolation_mm: float | None
    stress_days_season: int | None
    mean_prev_stress_days: float | None
    horizon_kind: str | None = Field(description="prognoza | scenariusz")
    days_to_stress: int | None
    risk: str | None
    horizon: list[dict] = Field(description="[{date, dr_mm}] – ubytek wody w kolejnych dniach horyzontu")
    irrigation_text: str | None
    irrigation_dose_mm: int | None
    irrigation_date: dt.date | None


class DevWater(BaseModel):
    parcel_id: str
    crop: CropId
    crop_label: str
    analysis_date: dt.date
    soil: Soil = Field(description="Kontrakt: soil")
    non_agricultural: bool
    season: DevWaterSeason | None
    model: DevWaterModel | None
    soil_water_pct: Indicator = Field(description="Kontrakt: indicators.soil_water_pct")
    soil_water_mm: Indicator = Field(description="Kontrakt: indicators.soil_water_mm")
    risk_7d: RiskIndicator = Field(description="Kontrakt: indicators.risk_7d")
    stress_days_by_year: list[YearStress] = Field(description="Kontrakt: history.stress_days_by_year")
    irrigation: Recommendation | None = Field(description="Kontrakt: recommendations[] (kategoria nawadnianie)")
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
    """TYMCZASOWE: woda w glebie, ryzyko 7 dni, dni stresu i nawadnianie dla działki i uprawy."""
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
    res = None
    weather_source = "—"

    if isinstance(weather_res, SourceError):
        limitations.insert(0, f"Brak danych pogodowych ({weather_res.message}) – modelu wody w glebie nie policzono.")
        ind = to_contract_indicators(
            SoilWaterResult(crop, "brak_danych", *crop_obj.season(analysis_date.year), 0, 0, crop_obj.root_depth_m, crop_obj.p,
                            limitations=["Brak danych pogodowych."]),
            crop_obj, analysis_date,
        )
    elif soil_a.not_agricultural or soil_a.wod_mm is None:
        why = soil.non_agricultural_note or "Brak danych o glebie (WOD) – modelu wody w glebie nie policzono."
        ind = to_contract_indicators(
            SoilWaterResult(crop, "brak_danych", *crop_obj.season(analysis_date.year), 0, 0, crop_obj.root_depth_m, crop_obj.p,
                            limitations=[why]),
            crop_obj, analysis_date,
        )
        weather_source = weather_res.weather.source
    else:
        forecast = None if isinstance(fc_res, SourceError) or fc_res is None else fc_res
        if isinstance(fc_res, SourceError):
            limitations.append(f"Prognoza Open-Meteo niedostępna ({fc_res.message}) – ryzyko ze scenariusza typowej pogody.")
        res = soil_water_model(weather_res.weather, crop_obj, soil_a.wod_mm, analysis_date, forecast, settings.history_years)
        ind = to_contract_indicators(res, crop_obj, analysis_date)
        limitations = [f"Pogoda uśredniona dla obszaru {weather_res.weather.resolution} ({weather_res.weather.source})."] \
            + weather_res.notes + res.limitations + limitations
        weather_source = weather_res.weather.source
    t3 = perf_counter()

    return DevWater(
        parcel_id=p.id,
        crop=crop,
        crop_label=crop_obj.label,
        analysis_date=analysis_date,
        soil=soil,
        non_agricultural=soil_a.not_agricultural,
        season=None if res is None else DevWaterSeason(
            status=res.season_status, start=res.season_start, end=res.season_end,
            day_of_season=res.day_of_season, stage=res.stage, kc=res.kc,
        ),
        model=None if res is None else DevWaterModel(
            taw_mm=res.taw_mm, raw_mm=res.raw_mm, root_depth_m=res.root_depth_m, p=res.p, dr_mm=res.dr_mm,
            dr0_mm=res.dr0_mm, winter_balance_mm=res.winter_balance_mm, winter_window_start=res.winter_window_start,
            raw_exceeded=res.raw_exceeded, ks=res.ks, percolation_mm=res.percolation_mm,
            stress_days_season=res.stress_days_season, mean_prev_stress_days=res.mean_prev_stress_days,
            horizon_kind=res.horizon_kind, days_to_stress=res.days_to_stress, risk=res.risk,
            horizon=[{"date": d.isoformat(), "dr_mm": v} for d, v in res.horizon_dr],
            irrigation_text=res.irrigation.text if res.irrigation else None,
            irrigation_dose_mm=res.irrigation.dose_mm if res.irrigation else None,
            irrigation_date=res.irrigation.when if res.irrigation else None,
        ),
        soil_water_pct=ind.soil_water_pct,
        soil_water_mm=ind.soil_water_mm,
        risk_7d=ind.risk_7d,
        stress_days_by_year=ind.stress_days_by_year,
        irrigation=ind.irrigation,
        weather_source=weather_source,
        limitations=limitations,
        timings_ms={
            "uldk": int((t1 - t0) * 1000),
            "zrodla_rownolegle": int((t2 - t1) * 1000),
            "model": int((t3 - t2) * 1000),
            "razem": int((perf_counter() - t0) * 1000),
        },
    )
