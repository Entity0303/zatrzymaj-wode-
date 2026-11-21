"""Open-Meteo — pogoda bieżąca i prognoza dobowa (do 16 dni) dla punktu (CLAUDE.md, źródło 3).

https://open-meteo.com/en/docs  (dane CC BY 4.0, bez klucza API)
Używane: temperatura i kod pogody teraz; dziennie: kod pogody, temp. maks./min.,
suma opadu [mm], parowanie ET0 FAO-56 [mm].

Archiwum (archive-api.open-meteo.com) – źródło ZAPASOWE historii pogody, używane tylko gdy
NASA POWER nie odpowie; ma dzienny limit na IP (429 = niedostępność) – patrz fetch_archive().
"""

from dataclasses import dataclass
from datetime import date, datetime

import httpx
import numpy as np

from app.analysis.et0 import DailyWeather, apply_et0, densify

from app.core.cache import TTLCache
from app.core.config import settings
from app.core.http import SourceError, get_client, get_with_retry

SOURCE = "Open-Meteo (prognoza)"
SOURCE_URL = "https://open-meteo.com/"

_cache: TTLCache["Forecast"] = TTLCache(ttl_s=30 * 60, max_items=1024)

# Kody pogody WMO -> (opis po polsku, ikona). Ikony to klucze rozumiane przez frontend.
WMO: dict[int, tuple[str, str]] = {
    0: ("Bezchmurnie", "sun"),
    1: ("Przeważnie słonecznie", "sun"),
    2: ("Częściowe zachmurzenie", "cloud-sun"),
    3: ("Pochmurno", "cloud"),
    45: ("Mgła", "fog"),
    48: ("Mgła osadzająca szadź", "fog"),
    51: ("Lekka mżawka", "drizzle"),
    53: ("Mżawka", "drizzle"),
    55: ("Gęsta mżawka", "drizzle"),
    56: ("Marznąca mżawka", "drizzle"),
    57: ("Gęsta marznąca mżawka", "drizzle"),
    61: ("Słaby deszcz", "rain"),
    63: ("Deszcz", "rain"),
    65: ("Silny deszcz", "rain"),
    66: ("Marznący deszcz", "rain"),
    67: ("Silny marznący deszcz", "rain"),
    71: ("Słaby śnieg", "snow"),
    73: ("Śnieg", "snow"),
    75: ("Silny śnieg", "snow"),
    77: ("Ziarnisty śnieg", "snow"),
    80: ("Przelotny deszcz", "rain"),
    81: ("Przelotne opady deszczu", "rain"),
    82: ("Gwałtowne ulewy", "rain"),
    85: ("Przelotny śnieg", "snow"),
    86: ("Silne opady śniegu", "snow"),
    95: ("Burza", "storm"),
    96: ("Burza z gradem", "storm"),
    99: ("Silna burza z gradem", "storm"),
}


def describe(code: int | None) -> tuple[str, str]:
    if code is None:
        return ("Brak danych", "unknown")
    return WMO.get(int(code), ("Nieznany stan pogody", "unknown"))


@dataclass
class Day:
    day: date
    code: int | None
    tmax: float | None
    tmin: float | None
    precip_mm: float | None
    et0_mm: float | None


@dataclass
class Forecast:
    lat: float
    lon: float
    current_time: datetime | None
    current_temp: float | None
    current_code: int | None
    is_day: bool
    days: list[Day]


def _num(seq: list, i: int) -> float | None:
    try:
        v = seq[i]
    except (IndexError, TypeError):
        return None
    return None if v is None else float(v)


def parse_response(payload: dict) -> Forecast:
    try:
        daily = payload["daily"]
        times = daily["time"]
        cur = payload.get("current") or {}
        days = [
            Day(
                day=date.fromisoformat(t),
                code=None if _num(daily.get("weather_code"), i) is None
                else int(daily["weather_code"][i]),
                tmax=_num(daily.get("temperature_2m_max"), i),
                tmin=_num(daily.get("temperature_2m_min"), i),
                precip_mm=_num(daily.get("precipitation_sum"), i),
                et0_mm=_num(daily.get("et0_fao_evapotranspiration"), i),
            )
            for i, t in enumerate(times)
        ]
        return Forecast(
            lat=float(payload["latitude"]),
            lon=float(payload["longitude"]),
            current_time=datetime.fromisoformat(cur["time"]) if cur.get("time") else None,
            current_temp=None if cur.get("temperature_2m") is None else float(cur["temperature_2m"]),
            current_code=None if cur.get("weather_code") is None else int(cur["weather_code"]),
            is_day=bool(cur.get("is_day", 1)),
            days=days,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceError(SOURCE, "nieoczekiwany format odpowiedzi") from exc


async def fetch(lon: float, lat: float, days: int = 16) -> Forecast:
    # zaokrąglenie do ~1 km: lepsze trafienia w cache, a rozdzielczość modelu i tak jest większa
    key = (round(lon, 2), round(lat, 2), days)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    params = {
        "latitude": f"{key[1]:.2f}",
        "longitude": f"{key[0]:.2f}",
        "current": "temperature_2m,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_sum,et0_fao_evapotranspiration",
        "timezone": "Europe/Warsaw",
        "forecast_days": str(days),
    }
    try:
        resp = await get_client().get(
            settings.open_meteo_forecast_url, params=params, timeout=httpx.Timeout(10.0)
        )
    except httpx.TimeoutException as exc:
        raise SourceError(SOURCE, "usługa nie odpowiada (przekroczono 10 s)") from exc
    except httpx.TransportError as exc:
        raise SourceError(SOURCE, f"brak połączenia z usługą ({exc.__class__.__name__})") from exc
    if resp.status_code == 429:
        raise SourceError(SOURCE, "przekroczony limit zapytań – spróbuj za chwilę")
    if resp.status_code >= 400:
        raise SourceError(SOURCE, f"usługa zwróciła błąd HTTP {resp.status_code}")
    fc = parse_response(resp.json())
    _cache.set(key, fc)
    return fc


def clear_cache() -> None:
    _cache.clear()


# ── Archiwum (ERA5) – ZAPASOWE źródło historii pogody, gdy NASA POWER nie odpowie (D1) ──────
# https://open-meteo.com/en/docs/historical-weather-api – limit dzienny na IP; 429 = niedostępność.

ARCHIVE_SOURCE = "Open-Meteo – archiwum (ERA5)"
ARCHIVE_SOURCE_SHORT = "Open-Meteo archiwum"
ARCHIVE_URL = "https://open-meteo.com/en/docs/historical-weather-api"
ARCHIVE_RESOLUTION = "ok. 10–25 km"
ARCHIVE_DAILY = "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max,temperature_2m_min"

_archive_cache: TTLCache[DailyWeather] = TTLCache(ttl_s=6 * 3600, max_items=256)


def parse_archive(payload: dict) -> DailyWeather:
    """Seria dobowa z archiwum. Brak promieniowania/wilgotności/wiatru → ET0 ze źródła („OM”),
    a gdy go brak – Hargreaves z temperatury (apply_et0)."""
    try:
        daily = payload["daily"]
        dates = np.array(daily["time"], dtype="datetime64[D]")

        def col(name: str) -> np.ndarray:
            return np.array([np.nan if v is None else v for v in daily.get(name, [None] * len(dates))], dtype=float)

        cols = {
            "precip": col("precipitation_sum"),
            "tmax": col("temperature_2m_max"),
            "tmin": col("temperature_2m_min"),
            "et0_provided": col("et0_fao_evapotranspiration"),
        }
        lat, lon = float(payload["latitude"]), float(payload["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceError(ARCHIVE_SOURCE, "nieoczekiwany format odpowiedzi") from exc
    dates, cols = densify(dates, cols)
    w = DailyWeather(
        dates=dates,
        lat=lat,
        lon=lon,
        elevation_m=float(payload.get("elevation") or 0.0),
        source=ARCHIVE_SOURCE_SHORT,
        source_url=ARCHIVE_URL,
        resolution=ARCHIVE_RESOLUTION,
        **cols,
    )
    return apply_et0(w)


async def fetch_archive(lon: float, lat: float, start: date, end: date) -> DailyWeather:
    key = (round(lon, 1), round(lat, 1), start.isoformat(), end.isoformat())
    hit = _archive_cache.get(key)
    if hit is not None:
        return hit
    params = {
        "latitude": f"{key[1]:.1f}",
        "longitude": f"{key[0]:.1f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ARCHIVE_DAILY,
        "timezone": "Europe/Warsaw",
    }
    resp = await get_with_retry(
        settings.open_meteo_archive_url,
        params,
        source=ARCHIVE_SOURCE,
        timeout_s=settings.open_meteo_archive_timeout_s,
        retries=0,  # źródło zapasowe – bez ponawiania, żeby zmieścić się w 30 s
    )
    try:
        w = parse_archive(resp.json())
    except ValueError as exc:
        raise SourceError(ARCHIVE_SOURCE, "odpowiedź nie jest poprawnym JSON") from exc
    _archive_cache.set(key, w)
    return w


def clear_archive_cache() -> None:
    _archive_cache.clear()
