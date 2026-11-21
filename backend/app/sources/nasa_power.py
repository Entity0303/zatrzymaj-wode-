"""NASA POWER — dobowe dane meteorologiczne dla punktu (społeczność AG).

https://power.larc.nasa.gov/docs/services/api/temporal/daily/
Brakujące wartości mają kod -999.
"""

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from app.analysis.et0 import et0_hargreaves, et0_penman_monteith
from app.config import settings
from app.http import SourceError, get_client

SOURCE = "NASA POWER (społeczność AG)"
PARAMS = ["PRECTOTCORR", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN"]


@dataclass
class DailyWeather:
    dates: list[date]
    precip: np.ndarray  # mm
    tmax: np.ndarray  # °C
    tmin: np.ndarray  # °C
    rh: np.ndarray  # %
    wind2m: np.ndarray  # m/s
    radiation: np.ndarray  # MJ m-2 dzień-1
    elevation_m: float
    lat: float
    lon: float
    et0: np.ndarray = field(default_factory=lambda: np.array([]))  # mm
    et0_method: np.ndarray = field(default_factory=lambda: np.array([]))  # "PM" / "HG" / ""

    @property
    def climatic_water_balance(self) -> np.ndarray:
        """Klimatyczny bilans wodny KBW = P − ET0 [mm/dzień]."""
        return self.precip - self.et0


def _series(param_block: dict, keys: list[str]) -> np.ndarray:
    arr = np.array([param_block.get(k, -999) for k in keys], dtype=float)
    arr[arr <= -998] = np.nan
    return arr


def parse_response(payload: dict) -> DailyWeather:
    try:
        block = payload["properties"]["parameter"]
        lon, lat, *rest = payload["geometry"]["coordinates"]
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceError(SOURCE, "nieoczekiwany format odpowiedzi") from exc
    elev = float(rest[0]) if rest else 0.0
    keys = sorted(block["PRECTOTCORR"].keys())
    dates = [date(int(k[:4]), int(k[4:6]), int(k[6:8])) for k in keys]
    w = DailyWeather(
        dates=dates,
        precip=_series(block["PRECTOTCORR"], keys),
        tmax=_series(block["T2M_MAX"], keys),
        tmin=_series(block["T2M_MIN"], keys),
        rh=_series(block["RH2M"], keys),
        wind2m=_series(block["WS2M"], keys),
        radiation=_series(block["ALLSKY_SFC_SW_DWN"], keys),
        elevation_m=elev,
        lat=float(lat),
        lon=float(lon),
    )
    _compute_et0(w)
    return w


def _compute_et0(w: DailyWeather) -> None:
    doy = np.array([d.timetuple().tm_yday for d in w.dates], dtype=float)
    pm = et0_penman_monteith(w.tmax, w.tmin, w.rh, w.wind2m, w.radiation, w.lat, w.elevation_m, doy)
    hg = et0_hargreaves(w.tmax, w.tmin, w.lat, doy)
    pm_ok = ~np.isnan(pm)
    hg_ok = ~np.isnan(hg)
    w.et0 = np.where(pm_ok, pm, hg)
    w.et0_method = np.where(pm_ok, "PM", np.where(hg_ok, "HG", ""))


async def fetch(lon: float, lat: float, start: date, end: date) -> DailyWeather:
    params = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    try:
        resp = await get_client().get(settings.nasa_power_url, params=params)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise SourceError(SOURCE, f"usługa niedostępna ({exc.__class__.__name__})") from exc
    return parse_response(payload)
