"""Ewapotranspiracja wskaźnikowa ET0 wg FAO-56 (Allen i in., 1998), dane dobowe.

Główna metoda: Penman-Monteith (równanie 6). Gdy brakuje promieniowania, wilgotności
lub wiatru — Hargreaves (równanie 52). Metoda jest zapamiętana dla każdego dnia:
  "PM" – Penman-Monteith (liczone przez nas),
  "HG" – Hargreaves (liczone przez nas, tylko z temperatury),
  "OM" – ET0 FAO-56 dostarczone przez źródło (archiwum Open-Meteo, ERA5),
  ""   – brak danych (ET0 = NaN).
Wszystko wektorowo (numpy), bez pętli po dniach.
"""

from dataclasses import dataclass, field

import numpy as np

SIGMA = 4.903e-9  # stała Stefana-Boltzmanna [MJ K-4 m-2 dzień-1]
GSC = 0.0820  # stała słoneczna [MJ m-2 min-1]

METHOD_LABELS = {
    "PM": "Penman-Monteith (FAO-56)",
    "HG": "Hargreaves (FAO-56, tylko temperatura)",
    "OM": "ET0 FAO-56 z archiwum Open-Meteo",
}


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
    """ET0 [mm/dzień]. rs – promieniowanie całkowite [MJ m-2 dzień-1], u2 – wiatr na 2 m [m/s].

    Dowolny brak (NaN) na wejściu daje NaN dla tego dnia – wtedy używamy Hargreavesa.
    """
    tmean = (tmax + tmin) / 2
    delta = 4098 * _sat_vp(tmean) / (tmean + 237.3) ** 2
    pressure = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    es = (_sat_vp(tmax) + _sat_vp(tmin)) / 2
    ea = es * np.clip(rh_mean, 0, 100) / 100
    ra = extraterrestrial_radiation(lat_deg, doy)
    rso = (0.75 + 2e-5 * elev_m) * ra
    rns = (1 - 0.23) * rs
    with np.errstate(invalid="ignore", divide="ignore"):
        rs_rso = np.clip(np.where(rso > 0, rs / rso, 1.0), 0.25, 1.0)
    rnl = (
        SIGMA
        * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2)
        * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0)))
        * (1.35 * rs_rso - 0.35)
    )
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * (900 / (tmean + 273)) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return np.maximum(num / den, 0)  # NaN przechodzi dalej (np.maximum(NaN, 0) = NaN)


def et0_hargreaves(tmax: np.ndarray, tmin: np.ndarray, lat_deg: float, doy: np.ndarray) -> np.ndarray:
    """ET0 [mm/dzień] metodą Hargreavesa (FAO-56, równanie 52); Ra przeliczone na mm (×0.408)."""
    tmean = (tmax + tmin) / 2
    ra_mm = 0.408 * extraterrestrial_radiation(lat_deg, doy)
    return np.maximum(0.0023 * (tmean + 17.8) * np.sqrt(np.maximum(tmax - tmin, 0)) * ra_mm, 0)


# ── Dane dobowe wspólne dla źródeł pogody ───────────────────────────────────────────────────


def _nan(n: int) -> np.ndarray:
    return np.full(n, np.nan)


@dataclass
class DailyWeather:
    """Ciągła seria dobowa dla punktu (wszystkie tablice tej samej długości co `dates`).

    Braki = NaN. Pola, których źródło nie podaje, też są NaN (np. Open-Meteo archiwum nie ma
    promieniowania, wilgotności i wiatru).
    """

    dates: np.ndarray  # datetime64[D], kolejne dni bez dziur
    precip: np.ndarray  # mm
    tmax: np.ndarray  # °C
    tmin: np.ndarray  # °C
    lat: float
    lon: float
    elevation_m: float
    source: str
    source_url: str
    resolution: str
    rh: np.ndarray | None = None  # %
    wind2m: np.ndarray | None = None  # m/s
    radiation: np.ndarray | None = None  # MJ m-2 dzień-1
    et0_provided: np.ndarray | None = None  # mm – ET0 podane przez źródło (Open-Meteo)
    et0: np.ndarray = field(default_factory=lambda: np.array([]))  # mm
    et0_method: np.ndarray = field(default_factory=lambda: np.array([]))  # "PM"/"HG"/"OM"/""

    def __post_init__(self) -> None:
        n = len(self.dates)
        for name in ("rh", "wind2m", "radiation", "et0_provided"):
            if getattr(self, name) is None:
                setattr(self, name, _nan(n))

    @property
    def climatic_water_balance(self) -> np.ndarray:
        """Klimatyczny bilans wodny KBW = P − ET0 [mm/dzień]; NaN, gdy brak opadu lub ET0."""
        return self.precip - self.et0

    def method_counts(self, mask: np.ndarray | None = None) -> dict[str, int]:
        m = self.et0_method if mask is None else self.et0_method[mask]
        return {k: int((m == k).sum()) for k in ("PM", "HG", "OM", "")}


def apply_et0(w: DailyWeather) -> DailyWeather:
    """Liczy ET0 dla każdego dnia i zapisuje metodę.

    Kolejność: PM (pełne dane) → ET0 ze źródła (OM) → Hargreaves (tylko temperatura) → brak.
    """
    doy = (w.dates - w.dates.astype("datetime64[Y]")).astype(int) + 1.0
    pm = et0_penman_monteith(w.tmax, w.tmin, w.rh, w.wind2m, w.radiation, w.lat, w.elevation_m, doy)
    hg = et0_hargreaves(w.tmax, w.tmin, w.lat, doy)
    pm_ok, om_ok, hg_ok = ~np.isnan(pm), ~np.isnan(w.et0_provided), ~np.isnan(hg)
    w.et0 = np.select([pm_ok, om_ok, hg_ok], [pm, w.et0_provided, hg], default=np.nan)
    w.et0_method = np.select([pm_ok, om_ok, hg_ok], ["PM", "OM", "HG"], default="")
    return w


def densify(
    dates: np.ndarray, columns: dict[str, np.ndarray]
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Uzupełnia dziury w datach (brakujące dni = NaN), sortuje rosnąco."""
    if len(dates) == 0:
        return dates.astype("datetime64[D]"), columns
    d = np.asarray(dates, dtype="datetime64[D]")
    full = np.arange(d.min(), d.max() + np.timedelta64(1, "D"), dtype="datetime64[D]")
    idx = (d - full[0]).astype(int)
    out = {}
    for k, v in columns.items():
        a = _nan(len(full))
        a[idx] = v
        out[k] = a
    return full, out
