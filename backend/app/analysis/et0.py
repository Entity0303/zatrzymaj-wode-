"""Ewapotranspiracja wskaźnikowa ET0 wg FAO-56 (Allen i in., 1998), dane dobowe.

Główna metoda: Penman-Monteith (równanie 6). Gdy brakuje promieniowania, wilgotności
lub wiatru — Hargreaves (równanie 52), co jest oznaczane w wyniku.

TODO (osoba A): test porównujący Hargreavesa z Penmanem-Monteithem na danych NASA POWER.
"""

import numpy as np

SIGMA = 4.903e-9  # stała Stefana-Boltzmanna [MJ K-4 m-2 dzień-1]
GSC = 0.0820  # stała słoneczna [MJ m-2 min-1]


def _sat_vp(t: np.ndarray) -> np.ndarray:
    """Ciśnienie pary nasyconej [kPa], równanie 11."""
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def extraterrestrial_radiation(lat_deg: float, doy: np.ndarray) -> np.ndarray:
    """Promieniowanie pozaziemskie Ra [MJ m-2 dzień-1], równania 21–25."""
    phi = np.deg2rad(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi / 365 * doy)
    delta = 0.409 * np.sin(2 * np.pi / 365 * doy - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    return (24 * 60 / np.pi) * GSC * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws)
    )


def et0_penman_monteith(
    tmax: np.ndarray,
    tmin: np.ndarray,
    rh_mean: np.ndarray,
    u2: np.ndarray,
    rs: np.ndarray,
    lat_deg: float,
    elev_m: float,
    doy: np.ndarray,
) -> np.ndarray:
    """ET0 [mm/dzień]. rs – promieniowanie całkowite [MJ m-2 dzień-1], u2 – wiatr na 2 m [m/s]."""
    tmean = (tmax + tmin) / 2
    delta = 4098 * _sat_vp(tmean) / (tmean + 237.3) ** 2
    pressure = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    es = (_sat_vp(tmax) + _sat_vp(tmin)) / 2
    ea = es * np.clip(rh_mean, 0, 100) / 100
    ra = extraterrestrial_radiation(lat_deg, doy)
    rso = (0.75 + 2e-5 * elev_m) * ra
    rns = (1 - 0.23) * rs
    rs_rso = np.clip(np.divide(rs, rso, out=np.ones_like(rs), where=rso > 0), 0.25, 1.0)
    rnl = (
        SIGMA
        * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2)
        * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0)))
        * (1.35 * rs_rso - 0.35)
    )
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * (900 / (tmean + 273)) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return np.maximum(num / den, 0)


def et0_hargreaves(tmax: np.ndarray, tmin: np.ndarray, lat_deg: float, doy: np.ndarray) -> np.ndarray:
    """ET0 [mm/dzień] metodą Hargreavesa (FAO-56, równanie 52); Ra przeliczone na mm (×0.408)."""
    tmean = (tmax + tmin) / 2
    ra_mm = 0.408 * extraterrestrial_radiation(lat_deg, doy)
    return np.maximum(0.0023 * (tmean + 17.8) * np.sqrt(np.maximum(tmax - tmin, 0)) * ra_mm, 0)
