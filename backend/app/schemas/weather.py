"""Kontrakt API: pogoda teraz + prognoza dobowa (GET /api/forecast).

Odpowiednik TypeScript: frontend/src/api/types.ts (Forecast, ForecastDay).
"""

from typing import Literal

from pydantic import BaseModel

from app.schemas.parcel import DataSource

WeatherIcon = Literal["sun", "cloud-sun", "cloud", "fog", "drizzle", "rain", "snow", "storm", "unknown"]


class CurrentWeather(BaseModel):
    czas: str | None
    temperatura: float | None
    opis: str
    ikona: WeatherIcon
    dzien: bool


class ForecastDay(BaseModel):
    data: str
    opis: str
    ikona: WeatherIcon
    temp_max: float | None
    temp_min: float | None
    opad_mm: float | None
    parowanie_mm: float | None
    bilans_mm: float | None


class Forecast(BaseModel):
    lon: float
    lat: float
    teraz: CurrentWeather
    dni: list[ForecastDay]
    bilans_okresu_mm: float | None
    zrodlo: DataSource
