"""Opad dla działki (A7, D82–D83): stacje IMGW jako źródło główne, NASA POWER jako porównanie i rezerwa.

Badanie osoby C (research/precip/REPORT.md): NASA POWER na nizinach zawyża opad o 16–23% względem stacji IMGW w każdym
z 10 lat i nie widzi lokalnych burz → model zaniżał suszę. Zmienia się TYLKO opad; ET0 (parowanie) zostaje z NASA.

- do 3 najbliższych stacji z danymi w promieniu 30 km, ważenie odwrotnością kwadratu odległości (IDW), dla każdego
  dnia tylko stacje z pomiarem; brak stacji → do 50 km (pewność o poziom niżej); brak → NASA jak przed A7 (oznaczone),
- dni bez pomiaru ze stacji (ostatnie tygodnie – archiwum IMGW ma opóźnienie; lata sprzed magazynu): NASA × współczynnik
  działki (suma IMGW / suma NASA z całego wspólnego okresu) – oznaczone,
- zgodność źródeł na SUMACH z okien (doba IMGW 6:00–6:00 ≠ doba modeli): sezon od 1 marca i ostatnie 30 dni,
- miejsce na trzecie źródło (ERA5-Land – dziś pominięte, limit archiwum Open-Meteo): `EXTRA_SOURCES`.

Progi i zdania: rules/precip.yaml.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from app.analysis.et0 import DailyWeather
from app.core.config import settings
from app.core.format import date_pl, num
from app.sources import imgw

RULES = Path(__file__).parent / "rules" / "precip.yaml"
NASA_LABEL = "NASA POWER"
# trzecie źródło (np. ERA5-Land): nazwa → funkcja (w, lon, lat) → tablica opadu na osi w.dates; trafia do okien zgodności
EXTRA_SOURCES: dict = {}
RATING_ORDER = {"brak_danych": -1, "zgodne": 0, "roznia_sie": 1, "mocno_sie_roznia": 2}


@lru_cache
def cfg() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["precip"]


@dataclass
class Window:
    key: str
    label: str
    start: date
    end: date
    imgw_mm: float | None
    nasa_mm: float | None
    difference_pct: float | None  # NASA względem IMGW, %
    rating: str


@dataclass
class PrecipInfo:
    main: str  # imgw | imgw_daleko | nasa
    stations: list[tuple[imgw.StationPick, float]] = field(default_factory=list)  # (stacja, waga IDW)
    factor: float | None = None          # suma IMGW / suma NASA ze wspólnego okresu
    common_days: int = 0
    nasa_vs_imgw_pct: float | None = None
    filled_days: int = 0                 # dni na końcu serii uzupełnione skorygowaną NASA
    filled_from: date | None = None
    filled_earlier_days: int = 0         # dni sprzed magazynu / z dziur – też skorygowana NASA
    windows: list[Window] = field(default_factory=list)
    agreement: str = "brak_danych"
    sentence: str = ""
    confidence_lowered: bool = False
    store_end: date | None = None
    outdated: list[tuple[imgw.StationPick, date | None]] = field(default_factory=list)  # A14: stacje bez danych z ost. roku


def rate(a: float, b: float) -> str:
    t = cfg()["thresholds"]
    spread = abs(a - b) / max((a + b) / 2, t["min_sum_mm"])
    return "zgodne" if spread <= t["agree_ok"] else "roznia_sie" if spread <= t["agree_warn"] else "mocno_sie_roznia"


def window(key: str, dates: np.ndarray, station: np.ndarray, nasa: np.ndarray, start: date, end: date) -> Window:
    """Porównanie sum w oknie – tylko dni z danymi w obu źródłach; za mało takich dni → „brak danych”."""
    label = cfg()["windows"][key]
    m = (dates >= np.datetime64(start)) & (dates <= np.datetime64(end))
    both = m & ~np.isnan(station) & ~np.isnan(nasa)
    if m.sum() == 0 or both.sum() < cfg()["thresholds"]["window_min_valid"] * m.sum():
        return Window(key, label, start, end, None, None, None, "brak_danych")
    a, b = float(station[both].sum()), float(nasa[both].sum())
    diff = None if a <= 0 else round(100.0 * (b - a) / a, 1)
    return Window(key, label, start, end, round(a, 1), round(b, 1), diff, rate(a, b))


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " i " + items[-1]


def _km(d: float) -> str:
    return f"{d:.0f} km"


def sentence(info: PrecipInfo) -> str:
    s, t = cfg()["sentences"], cfg()["thresholds"]
    if info.main == "nasa" and info.outdated:
        p, last = info.outdated[0]
        key = "nasa_outdated_factor" if info.factor is not None else "nasa_outdated"
        return s[key].format(station=p.name, km=_km(p.dist_km), last=date_pl(last),
                             factor=num(info.factor, 2) if info.factor is not None else "")
    if info.main == "nasa":
        return s["nasa_only"] if info.store_end is not None else s["nasa_no_store"]
    names = [f"{p.name} ({_km(p.dist_km)})" for p, _w in info.stations]
    if info.main == "imgw_daleko":
        txt = s["far"].format(stations=_join(names))
    else:
        txt = (s["one"] if len(names) == 1 else s["many"]).format(stations=_join(names))
    pct = info.nasa_vs_imgw_pct
    if pct is not None:
        key = "nasa_same" if abs(pct) <= t["same_pct"] else "nasa_more" if pct > 0 else "nasa_less"
        txt += s[key].format(pct=f"{abs(pct):.0f}")
    if info.agreement == "mocno_sie_roznia":
        txt += s["strong"]
    if info.filled_days > 0 and info.filled_from is not None:
        txt += s["filled"].format(days=info.filled_days, from_=date_pl(info.filled_from))
    return txt


def apply(w: DailyWeather, lon: float, lat: float, analysis_date: date) -> tuple[DailyWeather, PrecipInfo]:
    """Podmienia opad w serii pogody na opad ze stacji IMGW (gdy są) i opisuje źródła. `w` nie jest modyfikowane."""
    st = imgw.store()
    if st is None or len(w.dates) == 0:
        info = PrecipInfo(main="nasa")
        info.sentence = sentence(info)
        return w, info
    store_end = st.end.astype(object)
    main = "imgw"
    picks = imgw.nearest(st, lon, lat, w.dates, settings.imgw_max_stations, settings.imgw_max_km)
    if not picks:
        main = "imgw_daleko"
        picks = imgw.nearest(st, lon, lat, w.dates, settings.imgw_max_stations, settings.imgw_fallback_km)
    if not picks:
        # A14: brak stacji z AKTUALNYMI danymi (≥ 80% dni z ostatnich 12 mies.) – NASA przeliczona do poziomu najbliższej
        # stacji z danymi historycznymi (gdy jest), pewność niżej
        old = imgw.nearest(st, lon, lat, w.dates, 1, settings.imgw_fallback_km, min_recent=0.0)
        info = PrecipInfo(main="nasa", store_end=store_end, confidence_lowered=True)
        if old:
            series = st.series(old[0].idx, w.dates)
            both = ~np.isnan(series) & ~np.isnan(w.precip)
            t = cfg()["thresholds"]
            if both.sum() >= t["factor_min_days"] and w.precip[both].sum() > 0:
                info.factor = round(float(np.clip(series[both].sum() / w.precip[both].sum(), t["factor_min"],
                                                  t["factor_max"])), 3)
                info.common_days = int(both.sum())
                w = replace(w, precip=w.precip * info.factor)
            info.outdated = [(old[0], imgw.last_day(st, old[0].idx))]
        info.sentence = sentence(info)
        return w, info

    t = cfg()["thresholds"]
    dist = [p.dist_km for p in picks]
    station = imgw.idw([st.series(p.idx, w.dates) for p in picks], dist)
    nasa = w.precip
    both = ~np.isnan(station) & ~np.isnan(nasa)
    factor = None
    if both.sum() >= t["factor_min_days"] and nasa[both].sum() > 0:
        factor = float(np.clip(station[both].sum() / nasa[both].sum(), t["factor_min"], t["factor_max"]))
    fill = np.isnan(station) & ~np.isnan(nasa)
    new = np.where(~np.isnan(station), station, nasa * (factor if factor is not None else 1.0))

    info = PrecipInfo(main=main, stations=list(zip(picks, imgw.weights(dist))), factor=None if factor is None else round(factor, 3),
                      common_days=int(both.sum()), store_end=store_end)
    if both.sum() and station[both].sum() > 0:
        info.nasa_vs_imgw_pct = round(100.0 * (nasa[both].sum() - station[both].sum()) / station[both].sum(), 1)
    have = np.flatnonzero(~np.isnan(station))
    if have.size:  # koniec serii bez pomiaru ze stacji (opóźnienie archiwum IMGW)
        tail = fill[have[-1] + 1:]
        info.filled_days = int(tail.sum())
        if info.filled_days:
            info.filled_from = w.dates[have[-1] + 1].astype(object)
        info.filled_earlier_days = int(fill[: have[-1] + 1].sum())
    else:
        info.filled_earlier_days = int(fill.sum())

    # okna porównania kończą się na ostatnim dniu z pomiarem ze stacji (archiwum IMGW ma opóźnienie)
    last = w.dates[have[-1]].astype(object) if have.size else w.dates[-1].astype(object)
    first = w.dates[have[0]].astype(object) if have.size else w.dates[0].astype(object)
    season_start = date(last.year, 3, 1)
    if season_start > last:
        season_start = date(last.year - 1, 3, 1)
    info.windows = [
        window("sezon", w.dates, station, nasa, max(season_start, first), last),
        window("ostatnie_30_dni", w.dates, station, nasa, max(last - timedelta(days=29), first), last),
        window("wielolecie", w.dates, station, nasa, first, last),
    ]
    recent = [x.rating for x in info.windows[:2] if x.rating != "brak_danych"]
    info.agreement = max(recent, key=RATING_ORDER.get) if recent else info.windows[2].rating
    info.confidence_lowered = main == "imgw_daleko" or info.agreement == "mocno_sie_roznia"
    info.sentence = sentence(info)

    w2 = dataclasses.replace(w, precip=new, source=f"IMGW-PIB (opad) + {w.source} (parowanie)")
    return w2, info
