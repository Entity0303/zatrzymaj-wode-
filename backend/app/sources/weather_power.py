"""NASA POWER — dobowe dane meteorologiczne dla punktu (społeczność AG). Główne źródło pogody (D1).

https://power.larc.nasa.gov/docs/services/api/temporal/daily/
Parametry: PRECTOTCORR (opad), T2M_MAX/T2M_MIN, RH2M, WS2M, ALLSKY_SFC_SW_DWN.
Brakujące wartości mają kod -999 (także ostatnie dni przed dziś – opóźnienie źródła).
Rozdzielczość ok. 0,5° × 0,625° (~50 km). 10 lat w jednym zapytaniu ~1,6 s.
"""

from datetime import date

import numpy as np

from app.analysis.et0 import DailyWeather, apply_et0, densify
from app.core.cache import TTLCache, cached_fetch
from app.core.config import settings
from app.core.http import SourceError, get_with_retry

SOURCE = "NASA POWER (społeczność AG)"
SOURCE_SHORT = "NASA POWER"
SOURCE_URL = "https://power.larc.nasa.gov/"
RESOLUTION = "ok. 50 km"
PARAMS = ["PRECTOTCORR", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN"]

# dane historyczne się nie zmieniają; kilka godzin wystarcza, by doszły świeże dni
_cache: TTLCache[DailyWeather] = TTLCache(ttl_s=6 * 3600, max_items=256, name="NASA POWER")


def _series(param_block: dict, keys: list[str]) -> np.ndarray:
    arr = np.array([param_block.get(k, -999) for k in keys], dtype=float)
    arr[arr <= -998] = np.nan
    return arr


def parse_response(payload: dict) -> DailyWeather:
    try:
        block = payload["properties"]["parameter"]
        lon, lat, *rest = payload["geometry"]["coordinates"]
        keys = sorted(block["PRECTOTCORR"].keys())
        dates = np.array([f"{k[:4]}-{k[4:6]}-{k[6:8]}" for k in keys], dtype="datetime64[D]")
        cols = {
            "precip": _series(block["PRECTOTCORR"], keys),
            "tmax": _series(block["T2M_MAX"], keys),
            "tmin": _series(block["T2M_MIN"], keys),
            "rh": _series(block["RH2M"], keys),
            "wind2m": _series(block["WS2M"], keys),
            "radiation": _series(block["ALLSKY_SFC_SW_DWN"], keys),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceError(SOURCE, "nieoczekiwany format odpowiedzi") from exc
    elev = float(rest[0]) if rest and rest[0] is not None and float(rest[0]) > -998 else 0.0
    dates, cols = densify(dates, cols)
    w = DailyWeather(
        dates=dates,
        lat=float(lat),
        lon=float(lon),
        elevation_m=elev,
        source=SOURCE_SHORT,
        source_url=SOURCE_URL,
        resolution=RESOLUTION,
        **cols,
    )
    return apply_et0(w)


def cache_key(lon: float, lat: float, start: date, end: date) -> tuple:
    """Zaokrąglenie do 0,1° – sąsiednie działki trafiają w to samo zapytanie (rozdzielczość ~50 km)."""
    return (round(lon, 1), round(lat, 1), start.isoformat(), end.isoformat())


async def fetch(lon: float, lat: float, start: date, end: date) -> DailyWeather:
    """Dane dobowe od `start` do `end` włącznie. SourceError, gdy usługa nie odpowie."""
    key = cache_key(lon, lat, start, end)
    return await cached_fetch(_cache, key, SOURCE_SHORT, lambda: _download(key, start, end), ttl_s=ttl_for(end))


def ttl_for(end: date) -> float:
    """Dane sprzed tygodnia już się nie zmieniają – 7 dni; bieżące (NASA uzupełnia je z opóźnieniem) – 6 h."""
    recent = (date.today() - end).days <= 7
    return settings.cache_ttl_current_s if recent else settings.cache_ttl_history_s


async def _download(key: tuple, start: date, end: date) -> DailyWeather:
    params = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "longitude": f"{key[0]:.1f}",
        "latitude": f"{key[1]:.1f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    resp = await get_with_retry(
        settings.nasa_power_url, params, source=SOURCE, timeout_s=settings.nasa_power_timeout_s, retries=1
    )
    try:
        payload = resp.json()
    except ValueError as exc:
        raise SourceError(SOURCE, "odpowiedź nie jest poprawnym JSON") from exc
    return parse_response(payload)


def clear_cache() -> None:
    _cache.clear()
