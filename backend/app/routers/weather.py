"""GET /api/forecast – pogoda teraz + prognoza dobowa (Open-Meteo) do paska pogody i karty „Prognoza 7 dni”."""

from fastapi import APIRouter, HTTPException, Query

from app.core.http import SourceError, http_error, in_poland
from app.schemas.parcel import DataSource, ErrorDetail
from app.schemas.weather import CurrentWeather, Forecast, ForecastDay
from app.sources import weather_openmeteo as open_meteo

router = APIRouter(prefix="/api", tags=["pogoda"])


@router.get("/forecast", response_model=Forecast, responses={404: {"model": ErrorDetail}, 502: {"model": ErrorDetail}})
async def get_forecast(lon: float, lat: float, days: int = Query(7, ge=1, le=16)) -> Forecast:
    if not in_poland(lon, lat):
        raise HTTPException(
            status_code=404, detail=ErrorDetail(source=open_meteo.SOURCE, message="Punkt leży poza Polską.").model_dump()
        )
    try:
        fc = await open_meteo.fetch(lon, lat)
    except SourceError as exc:
        raise http_error(exc) from exc
    desc, icon = open_meteo.describe(fc.current_code)
    out_days: list[ForecastDay] = []
    for d in fc.days[:days]:
        d_desc, d_icon = open_meteo.describe(d.code)
        balance = None if d.precip_mm is None or d.et0_mm is None else round(d.precip_mm - d.et0_mm, 2)
        out_days.append(
            ForecastDay(
                data=d.day.isoformat(),
                opis=d_desc,
                ikona=d_icon,
                temp_max=d.tmax,
                temp_min=d.tmin,
                opad_mm=d.precip_mm,
                parowanie_mm=d.et0_mm,
                bilans_mm=balance,
            )
        )
    balances = [d.bilans_mm for d in out_days]
    return Forecast(
        lon=fc.lon,
        lat=fc.lat,
        teraz=CurrentWeather(
            czas=fc.current_time.isoformat() if fc.current_time else None,
            temperatura=fc.current_temp,
            opis=desc,
            ikona=icon,
            dzien=fc.is_day,
        ),
        dni=out_days,
        # suma tylko gdy wszystkie dni mają dane – brak danych nie może udawać zera
        bilans_okresu_mm=round(sum(balances), 1) if balances and None not in balances else None,
        zrodlo=DataSource(
            nazwa=open_meteo.SOURCE,
            url=open_meteo.SOURCE_URL,
            uwagi="Parowanie: ET0 FAO-56 z modelu Open-Meteo. Prognoza dla punktu, rozdzielczość modelu kilka km.",
        ),
    )
