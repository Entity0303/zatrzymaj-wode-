"""GET /api/analysis?parcel_id=&crop=&date= – pełna analiza wodna działki (kamień milowy 1).

Kontrakt odpowiedzi: app/schemas/analysis.py (AnalysisResponse).

Kolejność (A4/A5): ULDK → równolegle pogoda 10 lat (NASA POWER, zapasowo archiwum Open-Meteo), gleba IUNG,
klasy EGiB, frakcje SoilGrids, mapa glebowo-rolnicza, prognoza Open-Meteo (gdy data = dziś) → bilans wody i model FAO-56 (analysis.water_balance)
→ ocena (analysis.scoring) → pewność (analysis.confidence) → przyczyny (analysis.causes) → rekomendacje
(analysis.recommendations, reguły YAML). Awaria jednego źródła obniża pewność, nie wywraca analizy.
Endpointy /api/dev/* – TYMCZASOWE (usunąć przy końcowym sprzątaniu).
"""

import asyncio
from typing import Literal
import datetime as dt
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.format import date_pl, num
from app.analysis.et0 import DailyWeather
from app.analysis.crops import get_crop, with_sowing
from app.analysis.soil import assess_soil
from app.analysis.soil import to_contract as soil_to_contract
from app.analysis.causes import build_causes
from app.analysis.confidence import ConfidenceInputs, reliability
from app.analysis.crops import ALL_CROPS, CROPS, PHASE_LABELS
from app.analysis import field_state as fs
from app.analysis import approx_area, drawn_field, soil_consistency, soil_label
from app.analysis import choice as choice_mod
from app.analysis import precip as precip_mod
from app.analysis import satellite as satellite_mod
from app.analysis import verdict as verdict_mod
from app.analysis import suggestions as sugg
from app.analysis import variants as variants_mod
from app.analysis import terrain_interpret
from app.analysis import hydro as hydro_mod
from app.analysis import period as period_mod
from app.analysis import prices as prices_mod
from app.analysis import terrain as terrain_mod
from app.analysis.terrain import terrain_for_parcel
from app.analysis.facts import CROP_OFF_PHASES, IN_SEASON_PHASES, build_facts, field_facts
from app.analysis.recommendations import Evaluation, evaluate
from app.analysis.scoring import overall_status, reserve_status
from app.analysis.soil_texture import enrich_soil
from app.analysis.water_balance import (
    HorizonDay,
    SoilWaterResult,
    build_history,
    format_date_pl,
    history_range,
    last_usable_day,
    recent_balance,
    season_sums,
    shift_years,
    soil_water_model,
)
from app.analysis.water_balance import to_contract as model_to_contract
from app.core.cache import stale_scope
from app.core.config import settings
from app.core.http import NotFoundError, SourceError, http_error, in_poland, log_source_error
from app.routers.parcel import parcel_out, resolve_parcel
from app.schemas.analysis import (
    TerrainPending,
    AnalysisRequest,
    ApproximateArea,
    PrecipSources,
    PrecipStation,
    PrecipWindow,
    SeasonalBalanceYear,
)
from app.sources import imgw
from app.schemas.parcel import DataSource
from app.sources import uldk
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

TERRAIN_PENDING = "liczony w tle"  # A9: znacznik – teren nie był w cache, liczenie uruchomione w tle

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
    precip: "precip_mod.PrecipInfo | None" = None  # A7: skąd opad (stacje IMGW / NASA)
    raw_precip: "np.ndarray | None" = None  # A21: opad źródła pogody (NASA) przed podmianą na stacje – wariant widełek


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
    # A7 (D82): opad ze stacji IMGW (magazyn w repo, bez sieci); ET0 zostaje z modelu pogodowego
    raw_precip = w.precip
    w, pinfo = precip_mod.apply(w, lon, lat, analysis_date)
    return WeatherLoad(w, start, end, fallback, int((perf_counter() - t0) * 1000), notes, pinfo, raw_precip)


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
# twardy limit całego pobrania na źródło (D45) – limit httpx dotyczy pojedynczej operacji, nie całego zapytania
SOURCE_LIMIT_S = {"IUNG-PIB": 15.0, "KIEG / EGiB GUGiK": 6.5, "Open-Meteo (prognoza)": 10.0,
                  "SoilGrids (ISRIC)": 12.5, "Mapa glebowo-rolnicza (GUGiK)": 8.0, "NMT GUGiK": 16.0}


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
        mean = f"{wb.mean_balance_mm:.0f}".replace("-", "−")
        note = f"o {abs(wb.deviation_mm):.0f} mm {more} niż zwykle (średnia 10 lat {mean} mm), od {date_pl(wb.season_start)}"
    return Indicator(value=wb.current_balance_mm, unit="mm", status=status, note=note,
                     source_tag=wb.history.source_tag)


def _hg_share(w, sums) -> float | None:
    if sums is None or sums.until is None or sums.days <= 0:
        return None
    i0 = int((np.datetime64(sums.season_start, "D") - w.dates[0]).astype(int))
    m = w.et0_method[max(0, i0) : i0 + sums.days]
    return float((m == "HG").mean()) if len(m) else None


def parse_history(crop_history: str | None) -> list[str]:
    try:
        return sugg.parse_history(crop_history)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "message": f"Nieznana uprawa w historii pola: {exc}. Podaj 1–3 uprawy po przecinku albo „nie_wiem”."}) from exc


SAT_LEVEL_STATUS = {"ok": "ok", "info": "ok", "warn": "warn", "bad": "risk"}


def _sat_note(sat, which: str) -> str:
    """A15: słowami dla rolnika – „Kondycja roślin: gęsta zieleń · zdjęcie z 16.11.2026” (wartość w `index_value`)."""
    kond, wilg = satellite_mod.plant_words(sat.ndvi, sat.ndmi, sat.date)
    word = kond if which == "ndvi" else wilg
    head = "Kondycja roślin" if which == "ndvi" else "Wilgotność roślin"
    return f"{head}: {word} · zdjęcie z {date_pl(sat.date)}" if word else f"{head} · zdjęcie z {date_pl(sat.date)}"


def _sat_indicator(sat, which: str, no_sat: SourceTag) -> SatelliteIndicator:
    """Wskaźniki kondycji (NDVI → 0–100) i wilgotności roślin (NDMI −0,4…0,4 → 0–100) z wyniku Sentinel-2 (A11)."""
    if sat is None or sat.status != "ok":
        note = "zdjęcie satelitarne pobierane osobno" if sat is not None and sat.status == "pending" else \
            "brak bezchmurnego zdjęcia satelitarnego"
        return SatelliteIndicator(value=None, unit="pkt", status="no_data", note=note, source_tag=no_sat)
    raw = sat.ndvi if which == "ndvi" else sat.ndmi
    if raw is None:
        return SatelliteIndicator(value=None, unit="pkt", status="no_data", note="brak wartości", source_tag=no_sat)
    pts = (min(1.0, max(0.0, raw)) if which == "ndvi" else min(1.0, max(0.0, (raw + 0.4) / 0.8))) * 100
    label = sat.ndvi_label if which == "ndvi" else (sat.ndmi_label or "ocena tylko w sezonie przy gęstym łanie")
    return SatelliteIndicator(
        value=round(pts), unit="pkt", label=label, status=SAT_LEVEL_STATUS.get(sat.level or "info", "ok"),
        note=_sat_note(sat, which), index_value=raw,
        source_tag=SourceTag(kind="pomiar", date=sat.date, source="Sentinel-2 L2A"))


HISTORICAL_NOW = "w dniu analizy"  # A20: zamiast „teraz” przy dacie historycznej


def _until_weather(ind: Indicator, data_until: dt.date | None) -> Indicator:
    """A20: data zapasu wody = ostatni dzień danych pogodowych (nie dzień przed analizą, gdy pogoda kończy się wcześniej)."""
    tag = ind.source_tag
    if tag is None or tag.date is None or data_until is None or tag.date <= data_until:
        return ind
    return ind.model_copy(update={"source_tag": tag.model_copy(update={"date": data_until})})


def precip_contract(info: "precip_mod.PrecipInfo | None", data_until: dt.date | None) -> PrecipSources:
    """PrecipInfo → kontrakt `precip_sources` (None = opad z NASA, jak przed A7)."""
    info = info or precip_mod.PrecipInfo(main="nasa", sentence=precip_mod.cfg()["sentences"]["nasa_no_store"])
    c = precip_mod.cfg()
    measured = info.main != "nasa"
    return PrecipSources(
        main=info.main, main_label=c["main_labels"][info.main],
        stations=[PrecipStation(code=p.code, name=p.name, kind=p.kind, kind_label=imgw.KIND_LABEL[p.kind],
                                distance_km=p.dist_km, weight=wgt, coverage_pct=round(100 * p.coverage, 1),
                                lon=round(p.lon, 5), lat=round(p.lat, 5)) for p, wgt in info.stations],
        nasa_factor=info.factor, nasa_vs_imgw_pct=info.nasa_vs_imgw_pct, common_days=info.common_days,
        filled_days=info.filled_days, filled_from=info.filled_from, filled_earlier_days=info.filled_earlier_days,
        agreement=info.agreement, agreement_label=c["labels"][info.agreement],
        windows=[PrecipWindow(key=x.key, label=x.label, start=x.start, end=x.end, imgw_mm=x.imgw_mm, nasa_mm=x.nasa_mm,
                              difference_pct=x.difference_pct, rating=x.rating) for x in info.windows],
        sentence=info.sentence, details=list(info.details), confidence_lowered=info.confidence_lowered,
        precip_disagreement=list(info.disagreement_years), precip_disagreement_source=info.disagreement_source,
        source_tag=SourceTag(kind="pomiar" if measured else "szacunek_modelu", date=data_until,
                             source=imgw.SOURCE if measured else precip_mod.NASA_LABEL))


def species_to_group(crop_id: str | None) -> str | None:
    """A5e-2 (D80): gatunek z rankingu (pszenica_ozima, łubin…) w `crop` / `previous_crop` → uprawa IUNG jego grupy
    (zboza_ozime, straczkowe…), bo model wody liczy grupy (15 upraw)."""
    if crop_id and crop_id not in CROPS and crop_id in ALL_CROPS and ALL_CROPS[crop_id].group_id in CROPS:
        return ALL_CROPS[crop_id].group_id
    return crop_id


def validate_params(crop: str | None, analysis_date: dt.date, previous_crop: str | None, today: dt.date) -> None:
    """Uprawa opcjonalna (A5b-1): bez niej – „Stan działki”. Nieznana uprawa / zła data – 422."""
    if crop and crop not in CROPS:
        raise HTTPException(status_code=422, detail={"message": f"Nieznana uprawa: {crop}."})
    if previous_crop and previous_crop != "nie_wiem" and previous_crop not in CROPS:
        raise HTTPException(status_code=422, detail={"message": f"Nieznana uprawa z poprzedniego roku: {previous_crop}."})
    if analysis_date > today:
        raise HTTPException(status_code=422, detail={"message": "Data analizy nie może być z przyszłości."})
    if analysis_date < shift_years(today, settings.history_years):
        raise HTTPException(status_code=422, detail={"message": f"Data analizy może być najwyżej {settings.history_years} lat wstecz."})


async def run_analysis(
    parcel_id: str | None, crop: str | None, analysis_date: dt.date | None = None, previous_crop: str | None = None,
    crop_history: str | None = None, cultivated_area_ha: float | None = None,
    lon: float | None = None, lat: float | None = None, geometry: dict | None = None,
    planned_crops: str | list[str] | None = None,
    period: str | None = None, date_from: dt.date | None = None, date_to: dt.date | None = None,
    sowing_date: dt.date | None = None, wait_variants: bool = False,
) -> AnalysisResponse:
    """Pełna analiza (wspólna dla /api/analysis, raportu PDF i rozgrzewki przykładów demo). `wait_variants` (A21):
    czekaj na widełki rankingu do końca (raport PDF); inaczej najwyżej `ranking_variants_wait_s`."""
    with stale_scope() as stale_hits:
        return await _run(parcel_id, crop, analysis_date, previous_crop, stale_hits, crop_history, cultivated_area_ha,
                          lon, lat, geometry, planned_crops, period, date_from, date_to, sowing_date,
                          None if wait_variants else settings.ranking_variants_wait_s)


async def _resolve_point(lon: float, lat: float) -> tuple[uldk.Parcel, ApproximateArea | None]:
    """Działka w punkcie (znane działki → ULDK); gdy się nie da – obszar przybliżony 1 ha (D69)."""
    if not in_poland(lon, lat):
        raise HTTPException(status_code=404, detail={"source": None, "message": "Wskazany punkt leży poza Polską."})
    try:
        return await asyncio.wait_for(uldk.by_point(lon, lat),
                                      timeout=settings.uldk_timeout_s + settings.uldk_retry_timeout_s + 1), None
    except (SourceError, asyncio.TimeoutError) as exc:
        reason = (f"{exc.source}: {exc.message}" if isinstance(exc, SourceError) else "ULDK GUGiK: usługa nie odpowiada")
        down = not isinstance(exc, NotFoundError)  # P1: awaria ULDK, nie „brak działki w tym miejscu”
        if down:
            log_source_error("obszar przybliżony", exc if isinstance(exc, SourceError) else SourceError(uldk.SOURCE, reason))
    p = approx_area.approximate_parcel(lon, lat)
    return p, ApproximateArea(
        center=[round(lon, 6), round(lat, 6)], side_m=approx_area.SIDE_M, area_ha=round(approx_area.SIDE_M ** 2 / 1e4, 2),
        reason=reason, note=approx_area.ULDK_DOWN_NOTE if down else approx_area.NOTE,
        voivodeship_note=f"Województwo przybliżone (najbliższy środek województwa): {p.voivodeship}.")


async def _run(parcel_id: str | None, crop: str | None, date: dt.date | None, previous_crop: str | None,
               stale_hits: list, crop_history: str | None = None, cultivated_area_ha: float | None = None,
               lon: float | None = None, lat: float | None = None, geometry: dict | None = None,
               planned_crops: str | list[str] | None = None,
               period: str | None = None, date_from: dt.date | None = None, date_to: dt.date | None = None,
               sowing_date: dt.date | None = None, variants_wait_s: float | None = 1.0,
               ) -> AnalysisResponse:
    t0 = perf_counter()
    today = dt.date.today()
    analysis_date = date or today
    crop, previous_crop = species_to_group(crop), species_to_group(previous_crop)
    validate_params(crop, analysis_date, previous_crop, today)
    crop_hist = parse_history(crop_history)
    try:
        planned = choice_mod.parse_planned(planned_crops)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "message": f"Nieznana uprawa w planie siewu: {exc}. Podaj 1–3 uprawy (crop_id albo grupa), np. "
                       "„pszenica_ozima,zboza_jare”."}) from exc
    if cultivated_area_ha is not None and not 0 < cultivated_area_ha <= 10_000:
        raise HTTPException(status_code=422, detail={"message": "Powierzchnia uprawy musi być większa od 0 ha."})
    if not crop_hist and previous_crop in CROPS:  # zgodność z A5: sam przedplon = historia 1 roku
        crop_hist = [previous_crop]
    if not previous_crop and crop_hist and crop_hist[0] in CROPS:
        previous_crop = crop_hist[0]
    crop = crop or None
    crop_obj = get_crop(crop) if crop else None
    sowing_note = None
    if crop_obj is not None and sowing_date is not None:  # A21: data siewu rolnika – model wody tej uprawy od niej
        crop_obj, sowing_note = with_sowing(crop_obj, sowing_date)
    steps: list[LoadingStep] = []

    # ── 1. działka (ULDK) ──
    s = perf_counter()
    approx = None
    drawn = geometry is not None
    if drawn and (parcel_id or lon is not None or lat is not None):
        raise HTTPException(status_code=422, detail={"message": "Podaj albo obrys pola (geometry), albo numer działki, "
                                                                 "albo punkt na mapie – nie kilka naraz."})
    if drawn:
        try:
            p = await drawn_field.resolve(geometry)
        except drawn_field.DrawnError as exc:
            raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    elif parcel_id:
        try:
            p = await asyncio.wait_for(resolve_parcel(parcel_id, None, None), timeout=settings.uldk_timeout_s * 2 + 1)
        except SourceError as exc:
            raise http_error(exc) from exc
        except asyncio.TimeoutError as exc:
            raise http_error(SourceError("ULDK GUGiK", "usługa nie odpowiada")) from exc
    elif lon is not None and lat is not None:
        p, approx = await _resolve_point(lon, lat)
    else:
        raise HTTPException(status_code=422, detail={"message": "Podaj numer działki albo punkt na mapie (lon, lat)."})
    steps.append(_step("parcel", "Obrys pola narysowany przez rolnika" if drawn else "Szukam działki (ULDK GUGiK)",
                       "done" if approx is None else "error",
                       note=None if approx is None else "obszar przybliżony – " + approx.reason,
                       ms=int((perf_counter() - s) * 1000)))
    c = p.geom_4326.centroid
    rp = p.geom_4326.representative_point()
    # A11: satelita tylko z cache (analiza < 30 s); brak → „pending”, liczenie w tle, frontend dociąga /api/satellite
    sat = satellite_mod.cached_result(p.geom_4326, analysis_date)
    if sat is None:
        sat = satellite_mod.pending()
        satellite_mod.start_background(p.geom_4326, analysis_date)

    # ── 2. źródła równolegle, z łącznym limitem czasu ──
    remaining = max(3.0, ANALYSIS_BUDGET_S - (perf_counter() - t0))

    async def timed(name: str, coro):
        st = perf_counter()
        limit = min(remaining, SOURCE_LIMIT_S.get(name, remaining))
        try:
            res = await asyncio.wait_for(coro, timeout=limit)
        except SourceError as exc:
            res = exc
        except asyncio.TimeoutError:
            res = SourceError(name, f"brak odpowiedzi w {limit:.0f} s")
        except Exception as exc:  # noqa: BLE001 – teren (obliczenia na danych z zewnątrz) nie wywraca analizy
            if name != "NMT GUGiK":
                raise
            res = SourceError(name, f"błąd analizy terenu ({exc.__class__.__name__})")
        return res, int((perf_counter() - st) * 1000)

    is_today = analysis_date == today

    async def _terrain_step(p, timed):
        """A9: teren z cache (bez czekania na NMT); brak → liczenie w tle i `terrain = {status: pending}`."""
        if not settings.terrain_background:
            return await timed("NMT GUGiK", terrain_for_parcel(p.geom_2180, p.id))
        st = perf_counter()
        try:
            res = await terrain_mod.cached_terrain(p.geom_2180, p.id)
        except SourceError as exc:
            res = exc
        except Exception as exc:  # noqa: BLE001 – teren nie wywraca analizy
            res = SourceError("NMT GUGiK", f"błąd analizy terenu ({exc.__class__.__name__})")
        if res is None:
            terrain_mod.start_background(p.geom_2180, p.id)
            res = SourceError("NMT GUGiK", TERRAIN_PENDING)
        return res, int((perf_counter() - st) * 1000)

    (
        (w_res, w_ms), (iung_res, iung_ms), (kieg_res, kieg_ms), (fc_res, fc_ms), (sg_res, sg_ms), (sm_res, sm_ms),
        (tr_res, tr_ms),
    ) = await asyncio.gather(
        timed("NASA POWER", load_weather_history(c.x, c.y, analysis_date)),
        timed("IUNG-PIB", iung.soil_for_parcel(p.geom_2180)),
        timed("KIEG / EGiB GUGiK", kieg.classes_for_parcel(p.id, p.geom_2180)) if approx is None and not drawn
        else asyncio.sleep(0, result=(None, 0)),
        timed("Open-Meteo (prognoza)", _forecast_days(c.x, c.y)) if is_today else asyncio.sleep(0, result=(None, 0)),
        timed(soilgrids.SOURCE, soilgrids.texture_budget(rp.x, rp.y)),  # A22: najwyżej 5 s, reszta w tle
        timed(soil_map.SOURCE, soil_map.soil_map_for_parcel(p.geom_2180)),
        _terrain_step(p, timed),
    )
    tr_pending = isinstance(tr_res, SourceError) and tr_res.message == TERRAIN_PENDING
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
    map_sum = None if isinstance(sm_res, SourceError) else soil_consistency.summarize_map(sm_res)
    sm_rep = sm_res if isinstance(sm_res, SourceError) else map_sum.representative
    sm_note = err(sm_res) or (None if sm_rep is not None else "brak konturu w tym miejscu")
    sm_failed = 0 if isinstance(sm_res, SourceError) else getattr(sm_res, "failed", 0)
    if sm_failed:  # A23: mapa odpowiedziała tylko dla części punktów – wynik gleby może się zmienić po dociągnięciu
        sm_note = f"odpowiedź dla {len(sm_res) - sm_failed} z {len(sm_res)} punktów – reszta przy kolejnym przeliczeniu"
    steps.append(_step("soil_map", "Mapa glebowo-rolnicza (GUGiK)", state(sm_res), note=sm_note, ms=sm_ms))
    if is_today:
        steps.append(_step("forecast", "Prognoza pogody (Open-Meteo)", state(fc_res), note=err(fc_res), ms=fc_ms))
    else:
        steps.append(_step("forecast", "Prognoza pogody", "done", note="data historyczna – scenariusz typowej pogody", ms=0))
    steps.append(_step("satellite", "Zdjęcie satelitarne (Sentinel-2)", "done" if sat.status != "pending" else "pending",
                       note=(f"zdjęcie z {sat.date:%d.%m.%Y}" if sat.status == "ok" else
                             "pobierane osobno – GET /api/satellite" if sat.status == "pending" else sat.warning)))
    tr_saved = None if isinstance(tr_res, SourceError) else tr_res.facts.get("saved_note")
    steps.append(_step("terrain", "Analizuję teren (NMT GUGiK)", "pending" if tr_pending else state(tr_res),
                       note=("liczony w tle – GET /api/terrain" if tr_pending else
                             err(tr_res) or ("zapisany wynik analizy NMT" if tr_saved else None)), ms=tr_ms))

    # ── 3. obliczenia ──
    s = perf_counter()
    soil_a = assess_soil(iung_res, kieg_res)
    soil_c, soil_lim = enrich_soil(soil_to_contract(soil_a), sg_res, sm_rep)
    if sm_failed:  # A23
        soil_lim = [f"Mapa glebowo-rolnicza odpowiedziała tylko dla {len(sm_res) - sm_failed} z {len(sm_res)} punktów "
                    "działki – ocena gleby może się zmienić po ponownym przeliczeniu."] + list(soil_lim)
    # zgodność źródeł gleby: mapa glebowo-rolnicza > IUNG > SoilGrids (D49) – kategoria i WOD do modelu
    cons = soil_consistency.assess(soil_a, map_sum, soil_c.texture)
    soil_consistency.apply(soil_a, cons)
    soil_c = soil_c.model_copy(update={"consistency": cons.contract, "wod_mm": soil_a.wod_mm})
    wb = build_history(w, analysis_date, years=settings.history_years)
    sums = season_sums(w, analysis_date, years=settings.history_years)
    recent = recent_balance(w, analysis_date, years=settings.history_years)
    forecast = None if fc_res is None or isinstance(fc_res, SourceError) else fc_res
    no_model = None
    model = field = None
    if soil_a.not_agricultural or soil_a.wod_mm is None:
        no_model = soil_c.non_agricultural_note or "Brak danych o glebie (WOD) – modelu wody w glebie nie policzono."
    else:
        # stan działki (pokrycie referencyjne FAO-56, D50) – zawsze; model uprawy – gdy rolnik ją wybrał
        field = fs.field_state_model(w, soil_a.wod_mm, analysis_date, forecast, years=settings.history_years)
        if crop_obj:
            model = soil_water_model(w, crop_obj, soil_a.wod_mm, analysis_date, forecast,
                                     soil_category=soil_a.dominant_mineral, years=settings.history_years)
    out = None
    if crop_obj:
        out = model_to_contract(model or _no_model_result(crop_obj, analysis_date), crop_obj, analysis_date,
                                no_model_note=no_model)
    ok_calc = bool(model) if crop_obj else bool(field and field.status == "ok")
    # A9b: okres / zakres dat (period=30d|since_sowing|season albo date_from + date_to) – opad IMGW, ET0 NASA
    period_c = None
    try:
        sowing = period_mod.sowing_date(crop_obj, analysis_date)
        win = period_mod.resolve(period, date_from, date_to, analysis_date, sowing)
        if win is not None:
            period_c = period_mod.build(w, win, settings.history_years, model.stress_dates if model else None,
                                        has_crop=crop_obj is not None)
    except period_mod.PeriodError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc
    steps.append(_step("balance", "Liczę bilans wody i wodę w glebie (FAO-56)", "done" if ok_calc else "error",
                       note=no_model, ms=int((perf_counter() - s) * 1000)))

    s = perf_counter()
    prev = previous_crop if previous_crop in CROPS else None
    soil_prof = soil_label.profile(soil_a, map_sum, soil_c.texture)
    # A5e (D79): poza sezonem wybranej uprawy (przed siewem / po zbiorze) – JEDEN stan wody: stan działki (field_state)
    # jako status główny, jedna liczba wody w glebie; stan uprawy (stres, fazy, nawadnianie) tylko w jej sezonie.
    if out is not None and out.crop_season is not None and sowing_date is not None:
        out.crop_season = out.crop_season.model_copy(update={
            "sowing_date": None if sowing_note else sowing_date, "sowing_note": sowing_note})
    crop_off = bool(crop_obj and out is not None and out.crop_season is not None
                    and out.crop_season.phase in CROP_OFF_PHASES and field is not None and field.status == "ok")
    crop_active = bool(crop_obj and out is not None and out.crop_season is not None
                       and out.crop_season.phase in IN_SEASON_PHASES)
    facts = build_facts(None if crop_off else crop_obj, analysis_date, soil_a, None if crop_off else model, wb, sums,
                        soil_c=soil_c, previous_crop=prev, field=field, recent=recent, soil_profile=soil_prof)
    if crop_off:
        ok_calc = True
    # teren z NMT (A6): sekcja kontraktu + fakty dla reguł (requires: terrain)
    terrain_c, terrain_note = None, None
    soil_cat = cons.category_used if cons.contract else soil_a.dominant_mineral
    if tr_pending:
        terrain_note = None
    elif isinstance(tr_res, SourceError):
        terrain_note = f"Brak analizy terenu – {tr_res.source}: {tr_res.message}"
    else:
        terrain_c = terrain_interpret.to_contract(tr_res.facts, soil_prof.group,
                                                  data_date=min(today, analysis_date) if not tr_saved else None,
                                                  saved_note=tr_saved, soil_text=soil_prof.text)
    facts.values.update(terrain_interpret.rule_facts(None if terrain_c is None else tr_res.facts, soil_cat))
    facts.values["terrain_runoff_pct"] = (None if terrain_c is None else
                                          round(terrain_c.zone_share_pct["stok"] + terrain_c.zone_share_pct["sucha_gorka"]))
    facts.values["terrain_wet_pct"] = None if terrain_c is None else round(terrain_c.zone_share_pct["mokry_dolek"])
    # A9: woda w okolicy – z cache (Overpass + IMGW); brak → {status: pending} i pobranie w tle
    hydro_c = hydro_mod.cached(p.geom_4326, terrain_c.outlets if terrain_c else [], analysis_date)
    if hydro_c is None:
        hydro_mod.start_background(p.geom_4326)
        hydro_c = hydro_mod.pending()
    facts.values.update(hydro_mod.rule_facts(hydro_c))
    status = overall_status(facts, soil_c)
    causes = [] if soil_a.not_agricultural else build_causes(facts)
    available = {"terrain"} if terrain_c is not None else set()
    evaluation = evaluate(facts, available=available) if ok_calc and not soil_a.not_agricultural else Evaluation([])
    if analysis_date < today:  # A20: przy dacie historycznej „teraz” = w dniu analizy (też nawadnianie z modelu)
        evaluation.recommendations = [r.model_copy(update={"when_label": HISTORICAL_NOW}) if r.when_label == "teraz"
                                      else r for r in evaluation.recommendations]
    field_c = None
    if field is not None:
        f_status = status if crop_obj is None else reserve_status(field_facts(field, recent), "bez_uprawy")
        field_c = fs.to_contract(field, recent, f_status, analysis_date, w.source)
    sm_status = None if isinstance(sm_res, SourceError) else ("ok" if sm_rep is not None else "brak_konturu")
    rel, _premises, _points = reliability(ConfidenceInputs(
        analysis_date=analysis_date, today=today, parcel_fetched=p.fetched_at.date(), weather_name=w.source,
        weather_resolution=w.resolution, weather_fallback=w_res.fallback_used, weather_notes=w_res.notes,
        precip=w_res.precip,
        weather_until=wb.data_until, forecast_ok=(None if not is_today else forecast is not None),
        forecast_error=err(fc_res), soil=soil_a, model=model, wb=wb,
        hg_share_season=_hg_share(w, sums),
        extra_limitations=soil_lim + (field.limitations if field and (crop_obj is None or crop_off) else []),
        soilgrids="brak" if isinstance(sg_res, SourceError) else "ok", soilgrids_error=err(sg_res),
        soil_map=sm_status or "brak", soil_map_error=err(sm_res),
        soil_map_year=sm_rep.mapped_year if sm_status == "ok" else None,
        stale=list(stale_hits),
        soil_conflict=cons.conflict, approximate=approx is not None, drawn=drawn,
        satellite=sat.status == "ok", satellite_date=sat.date, satellite_status=sat.status,
        terrain=terrain_c is not None,
        terrain_error=None if terrain_c is not None else ("liczony w tle" if tr_pending else terrain_note),
        terrain_saved=bool(tr_saved), terrain_limitations=terrain_c.limitations if terrain_c else [],
        soil_basis_label=soil_consistency.LABELS[cons.contract.basis] if cons.substituted and cons.contract else None,
    ))
    history = wb.history.model_copy(update={"stress_days_by_year": out.stress_days_by_year if out else []})
    no_sat = SourceTag(kind="brak_danych", source="Sentinel-2 L2A")
    fs_level = field_c.status.level if field_c is not None and field_c.status is not None else None
    if out and not crop_off:
        sw_pct, sw_mm, risk7, soil_water = out.soil_water_pct, out.soil_water_mm, out.risk_7d, out.soil_water
        sw_pct, sw_mm = _until_weather(sw_pct, wb.data_until), _until_weather(sw_mm, wb.data_until)
    elif crop_off:  # jedna liczba wody: profil działki (field_state); ryzyko stresu – nie dotyczy poza sezonem
        sw_pct, sw_mm, soil_water = fs.water_indicators(field, analysis_date, fs_level)
        risk7 = RiskIndicator(value=None, unit="dni", label="Nie dotyczy", status="no_data",
                              note=f"{out.crop_season.phase_label} – poza sezonem uprawy; pokazujemy stan wody na działce",
                              source_tag=SourceTag(kind="brak_danych", source=fs.FIELD_SOURCE))
    else:  # bez uprawy – stan działki (pokrycie referencyjne); ryzyko stresu roślin nie dotyczy
        if field is not None:
            sw_pct, sw_mm, soil_water = fs.water_indicators(field, analysis_date, fs_level)
        else:
            tag = SourceTag(kind="brak_danych", source=fs.FIELD_SOURCE)
            sw_pct = Indicator(value=None, unit="%", status="no_data", note=no_model, source_tag=tag)
            sw_mm = Indicator(value=None, unit="mm", status="no_data", note=no_model, source_tag=tag)
            soil_water = SoilWaterState(scope="profil", depth_m=1.0, description=no_model or "brak danych")
        risk7 = RiskIndicator(value=None, unit="dni", label="Nie dotyczy", status="no_data",
                              note="wybierz uprawę, aby ocenić ryzyko stresu roślin na 7 dni",
                              source_tag=SourceTag(kind="brak_danych", source=fs.FIELD_SOURCE))
    indicators = Indicators(
        soil_water_pct=sw_pct,
        soil_water_mm=sw_mm,
        risk_7d=risk7,
        crop_health=_sat_indicator(sat, "ndvi", no_sat),
        plant_moisture=_sat_indicator(sat, "ndmi", no_sat),
        water_balance_season=_balance_indicator(wb),
        soil_capacity=soil_a.soil_capacity,
    )
    steps.append(_step("scoring", "Ocena, pewność, przyczyny i rekomendacje", "done", ms=int((perf_counter() - s) * 1000)))
    # ── ranking „Co tu posiać?” (A5b-2a): 17 upraw × 10 sezonów na pogodzie i glebie tej działki ──
    s = perf_counter()
    suggestions = None
    area_ha = None
    if not soil_a.not_agricultural and soil_a.wod_mm is not None:
        share = soil_a.agricultural_share if soil_a.agricultural_share else 1.0
        if cultivated_area_ha is not None:
            area_ha, area_est, area_note = cultivated_area_ha, False, "Powierzchnia uprawy podana przez rolnika."
        else:
            area_ha, area_est = round(p.area_ha * share, 2), True
            area_note = (f"Oszacowanie: powierzchnia działki z geometrii ULDK ({num(p.area_ha, 2)} ha) × udział gruntów "
                         f"rolnych wg IUNG ({round(100 * share)}%). Podaj własną powierzchnię uprawy, jeśli jest inna.")
        rep_map = map_sum.representative if map_sum else None
        ctx = sugg.Context(
            wod_mm=soil_a.wod_mm, category=soil_cat, complex_code=rep_map.complex_code if rep_map else None,
            voivodeship=p.voivodeship, area_ha=area_ha, area_estimated=area_est, area_note=area_note, history=crop_hist,
            soil_txt=facts.get("soil_txt") or "gleba", soil_group=soil_prof.group,
        )
        try:
            suggestions = await asyncio.to_thread(sugg.build, w, analysis_date, ctx, settings.history_years)
            if suggestions is not None and settings.ranking_variants:
                # A21: widełki z wariantów opadu i gleby – z pamięci albo najwyżej `variants_wait_s`, potem w tle
                pi = w_res.precip
                rng = await variants_mod.ranges(w, w_res.raw_precip, pi.main if pi else None, pi.factor if pi else None,
                                                analysis_date, ctx, settings.history_years, variants_wait_s)
                if rng is None:
                    suggestions = suggestions.model_copy(update={"ranges_pending": True})
                else:
                    suggestions = await asyncio.to_thread(sugg.build, w, analysis_date, ctx, settings.history_years, rng)
        except Exception as exc:  # noqa: BLE001 – ranking nie może wywrócić analizy
            steps.append(_step("suggestions", "Ranking „Co tu posiać?”", "error", note=exc.__class__.__name__))
    suggestions = choice_mod.attach(suggestions, planned, soil_prof.group == "lekka")
    suggestions = prices_mod.attach(suggestions, p.voivodeship, analysis_date)  # A12/A16: ceny sprzed daty analizy
    if suggestions is not None:
        steps.append(_step("suggestions", "Ranking „Co tu posiać?” (17 upraw × 10 sezonów)", "done",
                           ms=int((perf_counter() - s) * 1000)))
    # ── werdykt działki (A5b-2b): 4–6 zdań z policzonych wyników ──
    verdict = None
    if not soil_a.not_agricultural and soil_a.wod_mm is not None:
        chosen = None
        if crop_obj and out is not None and out.crop_season is not None:
            chosen = (crop_obj.label, out.crop_season.phase_label, status, crop_off)
        verdict = verdict_mod.build(soil_prof, soil_a.wod_mm, w, last_usable_day(analysis_date), terrain_c, suggestions,
                                    evaluation.recommendations, field_c.status if field_c else None, chosen,
                                    measured_precip=bool(w_res.precip and w_res.precip.main != "nasa"), satellite=sat,
                                    terrain_pending=tr_pending, hydro=hydro_c,
                                    now_word=HISTORICAL_NOW if analysis_date < today else "teraz")
    steps.append(_step("total", "Cała analiza", "done", ms=int((perf_counter() - t0) * 1000)))

    return AnalysisResponse(
        parcel=parcel_out(p) if approx is None else parcel_out(p).model_copy(update={"zrodlo": DataSource(
            nazwa="Obszar przybliżony (brak granic z ULDK)", url="https://uldk.gugik.gov.pl/", pobrano=None,
            uwagi=approx.note)}),
        crop=crop,
        previous_crop=previous_crop or None,
        analysis_date=analysis_date,
        historical=analysis_date < today,
        generated_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0),
        status=status,
        indicators=indicators,
        crop_season=out.crop_season if out else None,
        soil_water=soil_water,
        irrigation=out.irrigation if out and crop_active else None,  # A5e: zero nawadniania poza sezonem uprawy
        soil=soil_c,
        field_state=field_c,
        terrain=terrain_c if terrain_c is not None else (TerrainPending() if tr_pending else None),
        terrain_note=terrain_note,
        hydro=hydro_c,
        price_now=prices_mod.price_now(analysis_date) if suggestions is not None else None,
        period=period_c,
        verdict=verdict,
        approximate_area=approx,
        suggestions=suggestions,
        crop_history=crop_hist,
        cultivated_area_ha=area_ha,
        planned_crops=planned,
        seasonal_balance_by_year=[SeasonalBalanceYear(year=y, balance_mm=v, current=c) for y, v, c in wb.by_year],
        seasonal_balance_mean_mm=wb.mean_balance_mm,
        seasonal_balance_label=(f"od {format_date_pl(wb.season_start, with_year=False)} do "
                                f"{format_date_pl(wb.data_until, with_year=False)}" if wb.data_until else None),
        weather_data_until=wb.data_until,
        precip_sources=precip_contract(w_res.precip, wb.data_until),
        satellite=sat,
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
    parcel_id: str | None = Query(None, description="Pełny identyfikator działki ULDK (albo „obręb numer”)"),
    lon: float | None = Query(None, description="Punkt na mapie (EPSG:4326) – zamiast parcel_id"),
    lat: float | None = Query(None, description="Punkt na mapie (EPSG:4326) – zamiast parcel_id"),
    crop: str | None = Query(None, description="Uprawa (15 upraw IUNG SMSR); bez uprawy – „Stan działki”"),
    date: dt.date | None = Query(None, description="Data analizy (domyślnie dziś, maks. 10 lat wstecz)"),
    previous_crop: str | None = Query(None, description="Uprawa w poprzednim roku (15 upraw albo 'nie_wiem') – płodozmian"),
    crop_history: str | None = Query(None, description="Historia pola: 1–3 uprawy po przecinku, pierwsza = rok temu "
                                                       "(crop_id z crops.csv albo 'nie_wiem'), np. 'zyto,rzepak'"),
    cultivated_area_ha: float | None = Query(None, description="Powierzchnia uprawy w ha (domyślnie działka × udział gruntów rolnych)"),
    planned_crops: str | None = Query(None, description="Co planujesz posiać: 1–3 uprawy z rankingu po przecinku, np. 'pszenica_ozima,rzepak'"),
    period: Literal["30d", "since_sowing", "season"] | None = Query(None, description="A9b: podsumowanie okresu"),
    date_from: dt.date | None = Query(None, description="A9b: własny zakres – początek"),
    date_to: dt.date | None = Query(None, description="A9b: własny zakres – koniec (≤ data analizy)"),
    sowing_date: dt.date | None = Query(None, description="A21: data siewu wybranej uprawy (RRRR-MM-DD)"),
) -> AnalysisResponse:
    """Pełna analiza wodna działki: ULDK → równolegle pogoda 10 lat, gleba IUNG, klasy EGiB, SoilGrids, mapa
    glebowo-rolnicza, prognoza (dla dziś) → model wody w glebie → ocena → pewność → przyczyny → rekomendacje.
    Awaria jednego źródła = brak danych i niższa pewność; 502 tylko bez działki (ULDK) albo bez pogody.
    Bez `crop` – stan działki (gleba, zapas wody pod pokryciem referencyjnym FAO-56, bilans opad − ET0),
    `crop`, `crop_season`, `irrigation` = null."""
    return await run_analysis(parcel_id, crop, date, previous_crop, crop_history, cultivated_area_ha, lon, lat,
                              planned_crops=planned_crops, period=period, date_from=date_from, date_to=date_to,
                              sowing_date=sowing_date)


@router.post(
    "/analysis",
    response_model=AnalysisResponse,
    responses={404: {"model": ErrorDetail}, 409: {"description": "Kilka działek"},
               422: {"description": "Brak uprawy / zła data / zły obrys pola"}, 502: {"model": ErrorDetail}},
)
async def post_analysis(req: AnalysisRequest) -> AnalysisResponse:
    """To samo co GET /api/analysis, ale parametry w treści – potrzebne dla własnego obrysu pola (`geometry`:
    GeoJSON Polygon w WGS84; zbyt długi na adres URL). Odpowiedź: `parcel.source = "drawn"`, nazwa „Pole narysowane
    przez rolnika”, powierzchnia z kształtu; cała analiza (werdykt, ranking, teren) jak dla działki."""
    return await run_analysis(req.parcel_id, req.crop, req.date, req.previous_crop, req.crop_history,
                              req.cultivated_area_ha, req.lon, req.lat, req.geometry, req.planned_crops,
                              req.period, req.date_from, req.date_to, req.sowing_date)
