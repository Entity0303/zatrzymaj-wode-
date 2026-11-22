"""Opad dla działki (A7, D82–D83): stacje IMGW jako źródło główne, NASA POWER jako porównanie i rezerwa.

Badanie osoby C (research/precip/REPORT.md): NASA POWER na nizinach zawyża opad o 16–23% względem stacji IMGW w każdym
z 10 lat i nie widzi lokalnych burz → model zaniżał suszę. Zmienia się TYLKO opad; ET0 (parowanie) zostaje z NASA.

- do 3 najbliższych stacji z danymi w promieniu 30 km, ważenie odwrotnością kwadratu odległości (IDW), dla każdego
  dnia tylko stacje z pomiarem; brak stacji → do 50 km (pewność o poziom niżej); brak → NASA jak przed A7 (oznaczone),
- dni bez pomiaru ze stacji (ostatnie tygodnie – archiwum IMGW ma opóźnienie; lata sprzed magazynu): NASA × współczynnik
  działki (suma IMGW / suma NASA z całego wspólnego okresu) – oznaczone,
- zgodność źródeł na SUMACH z okien (doba IMGW 6:00–6:00 ≠ doba modeli): sezon od 1 marca i ostatnie 30 dni,
- miejsce na trzecie źródło (ERA5-Land – dziś pominięte, limit archiwum Open-Meteo): `EXTRA_SOURCES`,
- A16: rozjazd w sezonie – suma IV–VII ze stacji vs surowa NASA, rok po roku; > 30% → rok oznaczony
  (`disagreement_years`, zdanie w sekcji źródeł),
- A16b: kto się myli – stacje działki vs mediana pozostałych stacji do 50 km: zgodne (±25%) → „nasa” (NASA zawyża /
  zaniża, przyjmujemy pomiar, pewność bez zmian); odstają albo brak sąsiadów → „station” (wynik dla tych lat mniej
  pewny; ≥ 2 takie lata z ostatnich 5 → pewność o poziom niżej).

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
    season_diff_pct: dict[int, float] = field(default_factory=dict)  # A16: rok → (IMGW − NASA) / NASA, IV–VII, %
    disagreement_years: list[int] = field(default_factory=list)       # A16: lata z |różnicą| > progu
    disagreement_lowers: bool = False                                  # A16: ≥ 2 lata „station” z ostatnich 5 sezonów
    season_sums: dict[int, tuple[float, float]] = field(default_factory=dict)  # A16b: rok → (IMGW, NASA) mm, IV–VII
    neighbour_mm: dict[int, float] = field(default_factory=dict)       # A16b: rok → mediana sąsiednich stacji, mm
    disagreement_by: dict[int, str] = field(default_factory=dict)      # A16b: rok → "nasa" | "station"
    details: list[str] = field(default_factory=list)                    # A20: szczegóły źródeł (porównania, lata)

    @property
    def disagreement_source(self) -> str | None:
        """„station”, gdy choć jeden oznaczony rok to odstająca stacja; „nasa”, gdy wszystkie – NASA; brak lat → None."""
        if not self.disagreement_years:
            return None
        return "station" if any(self.disagreement_by.get(y) != "nasa" for y in self.disagreement_years) else "nasa"


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


def _season_masks(dates: np.ndarray):
    """(rok, maska dni IV–VII, liczba dni okresu) – tylko okresy zakończone przed końcem serii."""
    m0, m1 = cfg()["season_disagreement"]["months"]
    if len(dates) == 0:
        return
    yrs = dates.astype("datetime64[Y]").astype(int) + 1970
    mon = dates.astype("datetime64[M]").astype(int) % 12 + 1
    last = dates[-1].astype(object)
    for y in sorted(set(yrs.tolist())):
        end = date(y + (m1 == 12), m1 % 12 + 1, 1) - timedelta(days=1)
        if end > last:  # okres jeszcze się nie skończył przed datą analizy
            continue
        yield y, (yrs == y) & (mon >= m0) & (mon <= m1), (end - date(y, m0, 1)).days + 1


def season_sums(dates: np.ndarray, station: np.ndarray, nasa: np.ndarray) -> dict[int, tuple[float, float]]:
    """A16b: rok → (suma IMGW, suma NASA) [mm] z IV–VII; tylko pełne okresy z ≥ 90% dni w obu źródłach."""
    c = cfg()["season_disagreement"]
    out = {}
    for y, m, n_days in _season_masks(dates):
        both = m & ~np.isnan(station) & ~np.isnan(nasa)
        if both.sum() < c["min_valid"] * n_days or float(nasa[both].sum()) <= 0:
            continue
        out[y] = (round(float(station[both].sum()), 1), round(float(nasa[both].sum()), 1))
    return out


def season_diffs(dates: np.ndarray, station: np.ndarray, nasa: np.ndarray) -> dict[int, float]:
    """A16: rok → (IMGW − NASA) / NASA [%] z sum IV–VII."""
    return {y: round(100.0 * (a - b) / b, 1) for y, (a, b) in season_sums(dates, station, nasa).items()}


def neighbour_medians(st, lon: float, lat: float, exclude: set[int], dates: np.ndarray) -> dict[int, float]:
    """A16b: rok → mediana sum IV–VII stacji do `neighbour_km` od działki (bez stacji użytych do opadu), tylko stacje
    z ≥ 90% dni okresu; mniej niż `neighbour_min` stacji w roku → rok pominięty."""
    c = cfg()["season_disagreement"]
    dist = imgw.haversine_km(lon, lat, st.lon, st.lat)
    idx = [int(i) for i in np.argsort(dist) if dist[i] <= c["neighbour_km"] and int(i) not in exclude]
    if not idx:
        return {}
    series = [st.series(i, dates) for i in idx]
    out = {}
    for y, m, n_days in _season_masks(dates):
        sums = [float(s[m].sum()) for s in series if (m & ~np.isnan(s)).sum() >= c["min_valid"] * n_days
                and not np.isnan(s[m]).any()]
        if len(sums) >= c["neighbour_min"]:
            out[y] = round(float(np.median(sums)), 1)
    return out


def classify_disagreement(info: PrecipInfo) -> None:
    """A16b: dla oznaczonych lat – „nasa” (stacje zgodne z sąsiadami ±25%) albo „station”; pewność niżej tylko przy
    ≥ 2 latach „station” z ostatnich 5 sezonów."""
    c = cfg()["season_disagreement"]
    info.disagreement_by = {}
    for y in info.disagreement_years:
        med = info.neighbour_mm.get(y)
        a = info.season_sums.get(y, (None, None))[0]
        ok = med is not None and med > 0 and a is not None and abs(a - med) / med * 100 <= c["neighbour_agree_pct"]
        info.disagreement_by[y] = "nasa" if ok else "station"
    last5 = sorted(info.season_diff_pct)[-c["recent_years"]:]
    info.disagreement_lowers = sum(info.disagreement_by.get(y) == "station" for y in last5) >= c["recent_min"]


def _years_text(years: list[int]) -> str:
    """[2023, 2024] → „latach 2023–2024”, [2023] → „2023 r.”, [2018, 2023, 2024] → „latach 2018, 2023–2024”."""
    if len(years) == 1:
        return f"{years[0]} r."
    runs, start = [], years[0]
    for a, b in zip(years, years[1:] + [None]):
        if b != a + 1:
            runs.append(f"{start}" if start == a else f"{start}–{a}")
            start = b
    return "latach " + _join(runs)


def disagreement_sentence(info: PrecipInfo) -> str:
    """A16b: lata „nasa” – „dane satelitarne NASA pokazują ok. X% więcej… – przyjmujemy pomiar ze stacji”; lata
    „station” – zdanie o mniej pewnym wyniku (A16). Liczby i lata z danych."""
    st_years = [y for y in info.disagreement_years if info.disagreement_by.get(y) != "nasa"]
    return _nasa_sentence(info) + _station_sentence(info, st_years)


def _nasa_sentence(info: PrecipInfo) -> str:
    s = cfg()["sentences"]
    nasa_years = [y for y in info.disagreement_years if info.disagreement_by.get(y) == "nasa"]
    txt = ""
    if nasa_years:
        rel = [(b - a) / a * 100 for a, b in (info.season_sums[y] for y in nasa_years) if a > 0]  # NASA względem stacji
        if rel:
            pct = int(5 * round(sum(abs(r) for r in rel) / len(rel) / 5)) or 5
            same = all(r > 0 for r in rel) or all(r < 0 for r in rel)
            txt += s["disagree_nasa"].format(years=_years_text(nasa_years), pct=pct,
                                             direction=("więcej" if rel[0] > 0 else "mniej") if same else "inaczej")
    return txt


def _station_sentence(info: PrecipInfo, years: list[int]) -> str:
    if not years:
        return ""
    s = cfg()["sentences"]
    diffs = [info.season_diff_pct[y] for y in years]
    pct = int(5 * round(sum(abs(d) for d in diffs) / len(diffs) / 5)) or 5  # „ok. 40%” – zaokrąglenie do 5
    many_st, many_y = int(len(info.stations) > 1), int(len(years) > 1)
    if all(d < 0 for d in diffs) or all(d > 0 for d in diffs):
        return s["disagree"].format(years=_years_text(years), who=s["disagree_who"][many_st], pct=pct,
                                    direction="mniej" if diffs[0] < 0 else "więcej", which=s["disagree_which"][many_y])
    return s["disagree_mixed"].format(years=_years_text(years), who_mixed=s["disagree_who_mixed"][many_st], pct=pct,
                                      which=s["disagree_which"][many_y])


def _km(d: float) -> str:
    return f"{d:.0f} km"


def _span(days: int) -> str:
    """49 → „Ostatnie 7 tygodni”, 3 → „Ostatnie 3 dni”, 1 → „Ostatni dzień” (od 14 dni – w tygodniach)."""
    if days == 1:
        return "Ostatni dzień"
    if days < 14:
        return f"Ostatnie {days} dni"
    wk = round(days / 7)
    word = "tygodnie" if wk % 10 in (2, 3, 4) and wk % 100 not in (12, 13, 14) else "tygodni"
    return f"Ostatnie {wk} {word}"


def texts(info: PrecipInfo) -> tuple[str, list[str]]:
    """A20: (zdanie główne – najwyżej 2 zdania dla rolnika, szczegóły źródeł). Liczby z danych."""
    s, t = cfg()["sentences"], cfg()["thresholds"]
    if info.main == "nasa" and info.outdated:
        p, last = info.outdated[0]
        key = "nasa_outdated_factor" if info.factor is not None else "nasa_outdated"
        return s[key].format(station=p.name, km=_km(p.dist_km), last=date_pl(last),
                             factor=num(info.factor, 2) if info.factor is not None else ""), []
    if info.main == "nasa":
        return (s["nasa_only"] if info.store_end is not None else s["nasa_no_store"]), []
    names = [f"{p.name} ({_km(p.dist_km)})" for p, _w in info.stations]
    if info.main == "imgw_daleko":
        main = s["far"].format(stations=_join(names))
    else:
        main = (s["one"] if len(names) == 1 else s["many"]).format(stations=_join(names))
    extra: list[str] = []  # kandydaci na drugie zdanie – od najważniejszego
    if info.agreement == "mocno_sie_roznia":
        extra.append(s["strong"])
    st_years = [y for y in info.disagreement_years if info.disagreement_by.get(y) != "nasa"]
    if st_years:
        extra.append(_station_sentence(info, st_years))
    if info.filled_days > 0 and info.filled_from is not None:
        extra.append(s["filled"].format(span=_span(info.filled_days),
                                        target=s["filled_target"][int(len(info.stations) > 1)]))
    details: list[str] = []
    pct = info.nasa_vs_imgw_pct
    if pct is not None:
        key = "nasa_same" if abs(pct) <= t["same_pct"] else "nasa_more" if pct > 0 else "nasa_less"
        details.append(s[key].format(pct=f"{abs(pct):.0f}").strip())
    nasa_part = _nasa_sentence(info)
    if nasa_part:
        details.append(nasa_part.strip())
    if info.filled_days > 0 and info.filled_from is not None:
        details.append(f"Dane NASA od {date_pl(info.filled_from)} ({info.filled_days} dni) przeliczone współczynnikiem "
                       f"stacji{' ×' + num(info.factor, 2) if info.factor is not None else ''}.")
    details += [x.strip() for x in extra[1:]]
    return main + (extra[0] if extra else ""), details


def sentence(info: PrecipInfo) -> str:
    return texts(info)[0]


def apply(w: DailyWeather, lon: float, lat: float, analysis_date: date) -> tuple[DailyWeather, PrecipInfo]:
    """Podmienia opad w serii pogody na opad ze stacji IMGW (gdy są) i opisuje źródła. `w` nie jest modyfikowane."""
    st = imgw.store()
    if st is None or len(w.dates) == 0:
        info = PrecipInfo(main="nasa")
        info.sentence, info.details = texts(info)
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
        info.sentence, info.details = texts(info)
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
    sd = cfg()["season_disagreement"]
    info.season_sums = season_sums(w.dates, station, nasa)
    info.season_diff_pct = {y: round(100.0 * (a - b) / b, 1) for y, (a, b) in info.season_sums.items()}
    info.disagreement_years = [y for y, d in info.season_diff_pct.items() if abs(d) > sd["max_pct"]]
    if info.disagreement_years:
        info.neighbour_mm = neighbour_medians(st, lon, lat, {p.idx for p in picks}, w.dates)
    classify_disagreement(info)
    info.confidence_lowered = main == "imgw_daleko" or info.agreement == "mocno_sie_roznia" or info.disagreement_lowers
    info.sentence, info.details = texts(info)

    w2 = dataclasses.replace(w, precip=new, source=f"IMGW-PIB (opad) + {w.source} (parowanie)")
    return w2, info
