"""NASA POWER — dobowe dane meteorologiczne dla punktu (społeczność AG). Główne źródło pogody (D1).

https://power.larc.nasa.gov/docs/services/api/temporal/daily/
Parametry: PRECTOTCORR (opad), T2M_MAX/T2M_MIN, RH2M, WS2M, ALLSKY_SFC_SW_DWN.
Brakujące wartości mają kod -999 (także ostatnie dni przed dziś – opóźnienie źródła).
Rozdzielczość ok. 0,5° × 0,625° (~50 km). 10 lat w jednym zapytaniu ~1,6 s.
"""

import ast
import dataclasses
from datetime import date

import numpy as np

from app.core import clock
from app.analysis.et0 import DailyWeather, apply_et0, densify
from app.core.cache import FOREVER, TTLCache, cached_fetch
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


SERIES_FIELDS = ("dates", "precip", "tmax", "tmin", "rh", "wind2m", "radiation", "et0_provided", "et0", "et0_method")
STABLE_AFTER_DAYS = 7  # dni starsze niż tydzień NASA już nie poprawia (jak w ttl_for)


def slice_weather(w: DailyWeather, start: date, end: date) -> DailyWeather | None:
    """P1: wycinek [start, end] z dłuższej serii – te same wartości dzienne (ET0 liczone osobno dla każdego dnia);
    None, gdy seria nie obejmuje całego zakresu albo ma w nim dziury."""
    s, e = np.datetime64(start, "D"), np.datetime64(end, "D")
    if len(w.dates) == 0 or w.dates[0] > s or w.dates[-1] < e:
        return None
    m = (w.dates >= s) & (w.dates <= e)
    if int(m.sum()) != (end - start).days + 1:
        return None
    return dataclasses.replace(w, **{f: getattr(w, f)[m] for f in SERIES_FIELDS})


def _covering(lon: float, lat: float, start: date, end: date) -> DailyWeather | None:
    """P1: zapisana seria tego samego punktu siatki obejmująca [start, end] (najkrótsza) – bez nowego pobrania przy
    zmianie daty analizy. Tylko dla zakresów kończących się ponad tydzień temu (dane NASA już się nie zmieniają)."""
    if (clock.today_pl() - end).days <= STABLE_AFTER_DAYS:
        return None
    lo, la = round(lon, 1), round(lat, 1)
    cands = []
    for k in _cache.keys():
        try:
            t = ast.literal_eval(k)
            if not (isinstance(t, tuple) and len(t) == 4 and t[0] == lo and t[1] == la):
                continue
            s0, e0 = date.fromisoformat(t[2]), date.fromisoformat(t[3])
        except (ValueError, SyntaxError, TypeError):
            continue
        if s0 <= start and e0 >= end and (s0, e0) != (start, end):
            cands.append(((e0 - s0).days, t))
    for _n, t in sorted(cands):
        w = _cache.get(t)
        cut = None if w is None else slice_weather(w, start, end)
        if cut is not None:
            return cut
    return None


async def fetch(lon: float, lat: float, start: date, end: date) -> DailyWeather:
    """Dane dobowe od `start` do `end` włącznie. SourceError, gdy usługa nie odpowie. P1: brak dokładnego wpisu,
    a jest zapisana dłuższa seria tego punktu – wycinek z niej (bez zapytania do NASA)."""
    key = cache_key(lon, lat, start, end)
    if _cache.get(key) is None and (cut := _covering(lon, lat, start, end)) is not None:
        _cache.set(key, cut, ttl_s=ttl_for(end))
        return cut
    return await cached_fetch(_cache, key, SOURCE_SHORT, lambda: _download(key, start, end), ttl_s=ttl_for(end),
                              breaker_s=120)


def ttl_for(end: date) -> float:
    """Dni zakończone ponad tydzień temu już się nie zmieniają – bez wygasania; bieżące (NASA uzupełnia je
    z opóźnieniem) – 6 h (D53)."""
    recent = (clock.today_pl() - end).days <= 7
    return settings.cache_ttl_current_s if recent else FOREVER


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
