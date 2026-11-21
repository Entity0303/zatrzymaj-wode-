"""Open-Meteo — pogoda bieżąca i prognoza dobowa (do 16 dni) dla punktu (CLAUDE.md, źródło 3).

https://open-meteo.com/en/docs  (dane CC BY 4.0, bez klucza API)
Używane: temperatura i kod pogody teraz; dziennie: kod pogody, temp. maks./min.,
suma opadu [mm], parowanie ET0 FAO-56 [mm].

TODO: archiwum ERA5-Land (archive-api.open-meteo.com) jako źródło opcjonalne – w sieci
hackathonu zwraca 429, więc fallback na NASA POWER (weather_power.py).
"""

from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.core.cache import TTLCache
from app.core.config import settings
from app.core.http import SourceError, get_client

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
