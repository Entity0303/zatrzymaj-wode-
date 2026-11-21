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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.analysis.et0 import DailyWeather
from app.analysis.soil import assess_soil
from app.analysis.water_balance import build_history, history_range
from app.core.config import settings
from app.core.http import SourceError, http_error, in_poland, not_implemented
from app.routers.parcel import resolve_parcel
from app.schemas.analysis import AnalysisResponse, CropId, History, Indicator, SourceStatus
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
