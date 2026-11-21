"""C4 – opady dla działki z kilku niezależnych źródeł + ocena zgodności (research).

Źródła:
- IMGW-PIB, dane publiczne (danepubliczne.imgw.pl): archiwum dobowe OPAD (posterunki opadowe),
  KLIMAT i SYNOP; współrzędne stacji z API /api/data/meteo (wykaz_stacji.csv ich nie ma),
- ERA5-Land (~9 km) przez Open-Meteo Archive API (models=era5_land),
- NASA POWER (PRECTOTCORR, ~50 km) – tak jak backend dziś,
- prognoza: Open-Meteo, kilka modeli w jednym zapytaniu (forecast_models).

Główne funkcje:
- nearest_stations(lon, lat, n=3, max_km=30, start, end) – najbliższe stacje IMGW z opadem w okresie,
- imgw_daily(stations, start, end) – dobowe opady (braki = NaN, „brak zjawiska” = 0),
- combine(lon, lat, start, end) – opad dla działki: IDW ze stacji + ERA5-Land + NASA,
- agreement(series, ...) – zgodność źródeł (sezon IV–IX i ostatnie 30 dni): zgodne / różnią się / mocno się różnią.

Pliki:
- raw/       – miesięczne/roczne ZIP-y z archiwum IMGW (duże, w .gitignore),
- data/      – małe pliki do repo: katalog stacji ze współrzędnymi, indeks archiwum, serie dobowe
               tylko stacji potrzebnych do działek demo, odpowiedzi ERA5-Land i NASA dla działek demo.
"""

from __future__ import annotations

import csv
import io
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
DATA = HERE / "data"
IMGW_ARCH = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/"
IMGW_METEO_API = "https://danepubliczne.imgw.pl/api/data/meteo"
IMGW_SYNOP_API = "https://danepubliczne.imgw.pl/api/data/synop"
ERA5_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
UA = "zatrzymaj-wode-research/0.1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """NIGDY nie podążamy za przekierowaniem: GUGiK przy limicie odpowiada 302 i serwuje plik ~126 MB.
    redirect_request → None sprawia, że urllib zgłasza HTTPError z kodem 3xx; treści 3xx nie czytamy."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

KINDS = {"opad": "o", "klimat": "k", "synop": "s"}  # rodzaj stacji → sufiks pliku
KIND_PRIORITY = {"synop": 0, "klimat": 1, "opad": 2}  # przy tej samej stacji w kilku archiwach

# progi zgodności (względny rozrzut sum = (max − min) / średnia)
AGREE_OK = 0.15
AGREE_WARN = 0.35
MIN_SUM_MM = 20.0  # mianownik rozrzutu nie mniejszy niż 20 mm
LABELS = ("zgodne", "różnią się", "mocno się różnią")


# --------------------------------------------------------------------------------------
# HTTP z cache na dysku
# --------------------------------------------------------------------------------------

def http_get(url: str, timeout: float = 60.0, retries: int = 4, binary: bool = False):
    last = None
    for attempt in range(retries):
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Connection": "close"})
            with _OPENER.open(req, timeout=timeout) as r:
                body = r.read()
            return (body if binary else body.decode("utf-8")), time.monotonic() - t0
        except urllib.error.HTTPError as e:
            last = e
            if 300 <= e.code < 400:  # nie podążamy za przekierowaniem i nie czytamy jego treści
                e.close()
                raise RuntimeError(f"HTTP {e.code} – przekierowanie (usługa ogranicza ruch): {url}") from None
            if e.code == 404:
                raise
            if e.code == 429:  # limit Open-Meteo
                retry_after = float(e.headers.get("Retry-After") or 0)
                if retry_after > 120:  # limit dzienny – nie ma sensu czekać w tej sesji
                    raise RuntimeError(f"limit zapytań (429), ponów za {retry_after / 3600:.1f} h: {url}") from e
                time.sleep(max(10 * (attempt + 1), retry_after))
                continue
            time.sleep(1 + attempt)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"GET nieudany: {url} ({last})")


def cached_json(path: Path, url: str, timeout: float = 60.0,
                allow_network: bool = True) -> tuple[dict, float | None]:
    """Odpowiedź JSON z dysku albo z sieci (zapisana). Zwraca (dane, czas_pobrania | None z cache).
    allow_network=False – tylko cache (np. archiwum Open-Meteo po wyczerpaniu limitu dziennego)."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), None
    if not allow_network:
        raise RuntimeError(f"brak w cache, pobieranie wyłączone: {path.name}")
    text, dt = http_get(url, timeout=timeout)
    data = json.loads(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"_url": url, "_fetched": time.strftime("%Y-%m-%d %H:%M"),
                                "_seconds": round(dt, 2), **data}, ensure_ascii=False), encoding="utf-8")
    return data, dt


# --------------------------------------------------------------------------------------
# Geometria
# --------------------------------------------------------------------------------------

def haversine_km(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


# --------------------------------------------------------------------------------------
# IMGW – katalog stacji, archiwum, serie dobowe
# --------------------------------------------------------------------------------------

def station_catalog(refresh: bool = False) -> dict[str, dict]:
    """Kod stacji (9 cyfr) → {name, lon, lat, elev}. Źródło: API /api/data/meteo (stacje telemetryczne).

    Archiwum IMGW (wykaz_stacji.csv) nie podaje współrzędnych – kod koduje tylko kwadrat 1°×1°
    (np. 249199978 → 49°N, 19°E). Stacje bez współrzędnych w API są pomijane.
    """
    path = DATA / "imgw_stations.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))["stations"]
    text, dt = http_get(IMGW_METEO_API)
    st = {}
    for s in json.loads(text):
        if s.get("lon") and s.get("lat"):
            st[s["kod_stacji"]] = {"name": s["nazwa_stacji"], "lon": float(s["lon"]), "lat": float(s["lat"]),
                                   "elev": float(s["wysokosc_npm"]) if s.get("wysokosc_npm") else None,
                                   "has_precip_sensor": s.get("opad_10min") is not None}
    DATA.mkdir(exist_ok=True)
    path.write_text(json.dumps({"_source": IMGW_METEO_API, "_fetched": time.strftime("%Y-%m-%d %H:%M"),
                                "_seconds": round(dt, 2), "stations": st}, ensure_ascii=False, indent=0),
                    encoding="utf-8")
    return st


def _archive_url(kind: str, year: int, month: int | None = None, synop_id: str | None = None) -> str:
    suf = KINDS[kind]
    if kind == "synop":  # SYNOP: plik roczny na stację (3 ostatnie cyfry kodu = numer WMO 12xxx)
        return f"{IMGW_ARCH}synop/{year}/{year}_{synop_id}_s.zip"
    return f"{IMGW_ARCH}{kind}/{year}/{year}_{month:02d}_{suf}.zip"


def synop_ids_for_year(year: int) -> list[str]:
    """Numery stacji SYNOP z listingu katalogu archiwum (pliki {rok}_{nr}_s.zip)."""
    cache = DATA / "imgw_synop_listing.json"
    lst = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    if str(year) not in lst:
        import re
        text, _ = http_get(f"{IMGW_ARCH}synop/{year}/")
        lst[str(year)] = sorted(set(re.findall(rf'href="{year}_(\d+)_s\.zip"', text)))
        DATA.mkdir(exist_ok=True)
        cache.write_text(json.dumps(lst), encoding="utf-8")
    return lst[str(year)]


def download_archive(kind: str, years: list[int], synop_ids: list[str] | None = None) -> list[Path]:
    """Pobiera ZIP-y archiwum do raw/ (pomija już pobrane). OPAD i KLIMAT – pliki miesięczne dla całej
    Polski (~40–70 kB), SYNOP – pliki roczne tylko dla wskazanych stacji."""
    out = []
    jobs = []
    for y in years:
        if kind == "synop":
            jobs += [(y, None, sid) for sid in (synop_ids or [])]
        else:
            jobs += [(y, m, None) for m in range(1, 13)]
    if kind == "synop" and synop_ids is None:
        jobs = [(y, None, sid) for y in years for sid in synop_ids_for_year(y)]
    for y, m, sid in jobs:
        url = _archive_url(kind, y, m, sid)
        p = RAW / kind / url.rsplit("/", 1)[1]
        if not p.exists():
            try:
                body, _ = http_get(url, binary=True)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                raise
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
            time.sleep(0.2)
        out.append(p)
    return out


# kolumny SMDB / WSMDB (0-indeks) w plikach dobowych
_COLS = {"opad": (5, 6), "klimat": (13, 14), "synop": None}


def _synop_cols(header_len: int) -> tuple[int, int]:
    # s_d: NSP, POST, ROK, MC, DZ, TMAX, WTMAX, TMIN, WTMIN, STD, WSTD, TMNG, WTMNG, SMDB, WSMDB, ...
    return 13, 14


def parse_daily_csv(text: str, kind: str) -> list[tuple[str, str, date, float | None, str]]:
    """Wiersze (kod, nazwa, data, opad_mm | None, status). Status: '' pomiar, '8' brak pomiaru (→ None),
    '9' brak zjawiska (→ 0), 'Z' opad zbiorczy (suma za poprzedzające dni bez pomiaru)."""
    out = []
    ci, wi = _COLS[kind] if kind != "synop" else _synop_cols(0)
    for row in csv.reader(io.StringIO(text)):
        if len(row) <= wi:
            continue
        try:
            d = date(int(row[2]), int(row[3]), int(row[4]))
        except ValueError:
            continue
        st = row[wi].strip()
        if st == "8":
            val = None
        elif st == "9":
            val = 0.0
        else:
            try:
                val = float(row[ci])
            except ValueError:
                val = None
        out.append((row[0].strip(), row[1].strip(), d, val, st))
    return out


def iter_archive_rows(kind: str, paths: list[Path]):
    for p in paths:
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                low = name.lower()
                # *_t_*.csv = dane terminowe (temperatura, wilgotność…) – inne kolumny, bez opadu dobowego
                if not low.endswith(".csv") or "_t_" in low:
                    continue
                text = z.read(name).decode("cp1250", errors="replace")
                yield from parse_daily_csv(text, kind)


def build_index(years: list[int]) -> dict[str, dict]:
    """Indeks archiwum SYNOP + KLIMAT + OPAD: kod → {kind, name, months: liczba miesięcy z danymi}.
    Zapisywany do data/imgw_index.json (mały), żeby nearest_stations działało offline."""
    path = DATA / "imgw_index.json"
    idx: dict[str, dict] = {}
    months: dict[str, set] = {}
    for kind in ("synop", "klimat", "opad"):
        paths = download_archive(kind, years)
        for code, name, d, val, st in iter_archive_rows(kind, paths):
            key = code
            if key not in idx or KIND_PRIORITY[kind] < KIND_PRIORITY[idx[key]["kind"]]:
                idx[key] = {"kind": kind, "name": name}
            if val is not None:
                months.setdefault(key, set()).add((d.year, d.month))
    for k, v in idx.items():
        v["months"] = len(months.get(k, ()))
        ym = sorted(months.get(k, ()))
        v["first"] = f"{ym[0][0]}-{ym[0][1]:02d}" if ym else None
        v["last"] = f"{ym[-1][0]}-{ym[-1][1]:02d}" if ym else None
    path.write_text(json.dumps({"_years": years, "index": idx}, ensure_ascii=False, indent=0), encoding="utf-8")
    return idx


def load_index() -> dict[str, dict]:
    return json.loads((DATA / "imgw_index.json").read_text(encoding="utf-8"))["index"]


@dataclass
class Station:
    code: str
    name: str
    kind: str
    lon: float
    lat: float
    dist_km: float


def nearest_stations(lon: float, lat: float, n: int = 3, max_km: float = 30.0,
                     start: date | None = None, end: date | None = None,
                     min_coverage: float = 0.8, catalog: dict | None = None,
                     index: dict | None = None) -> list[Station]:
    """Najbliższe stacje IMGW z opadem: mają współrzędne (API meteo) i dane w archiwum OPAD/KLIMAT
    przez >= min_coverage miesięcy okresu."""
    catalog = catalog if catalog is not None else station_catalog()
    index = index if index is not None else load_index()
    need = None
    if start and end:
        need = (end.year - start.year) * 12 + end.month - start.month + 1
    cand = []
    for code, meta in index.items():
        c = catalog.get(code)
        if not c:
            continue
        if need and meta.get("months", 0) < min_coverage * need:
            continue
        d = float(haversine_km(lon, lat, c["lon"], c["lat"]))
        if d <= max_km:
            cand.append(Station(code, meta["name"], meta["kind"], c["lon"], c["lat"], round(d, 2)))
    cand.sort(key=lambda s: s.dist_km)
    return cand[:n]


def extract_station_series(stations: list[Station], years: list[int]) -> None:
    """Zapisuje do data/imgw/<kod>.csv tylko serie potrzebnych stacji (mały plik do repo)."""
    want = {s.code: s for s in stations}
    rows: dict[str, list] = {c: [] for c in want}
    for kind in ("synop", "klimat", "opad"):
        paths = download_archive(kind, years)
        for code, name, d, val, st in iter_archive_rows(kind, paths):
            if code in want and want[code].kind == kind:
                rows[code].append((d.isoformat(), "" if val is None else val, st))
    (DATA / "imgw").mkdir(parents=True, exist_ok=True)
    for code, rr in rows.items():
        # ten sam dzień może wystąpić dwa razy (korekty w archiwum) – zostaje wiersz z pomiarem
        best: dict[str, tuple] = {}
        for r in rr:
            if r[0] not in best or (best[r[0]][1] == "" and r[1] != ""):
                best[r[0]] = r
        with open(DATA / "imgw" / f"{code}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["data", "opad_mm", "status"])
            w.writerows(best[k] for k in sorted(best))


def imgw_daily(stations: list[Station], start: date, end: date) -> dict[str, np.ndarray]:
    """Dobowe opady stacji [mm] na osi dni start..end. Braki pomiaru = NaN. Dzień nieobecny w pliku,
    gdy stacja ma dane w tym miesiącu = 0 („brak zjawiska to również brak dnia”); cały miesiąc
    bez danych = NaN."""
    n = (end - start).days + 1
    out = {}
    for s in stations:
        arr = np.full(n, np.nan)
        p = DATA / "imgw" / f"{s.code}.csv"
        if not p.exists():
            out[s.code] = arr
            continue
        months_present = set()
        vals = {}
        for r in csv.DictReader(open(p, encoding="utf-8")):
            d = date.fromisoformat(r["data"])
            months_present.add((d.year, d.month))
            vals[d] = float(r["opad_mm"]) if r["opad_mm"] != "" else np.nan
        for i in range(n):
            d = start + timedelta(days=i)
            if d in vals:
                arr[i] = vals[d]
            elif (d.year, d.month) in months_present:
                arr[i] = 0.0
        out[s.code] = arr
    return out


def idw(series: dict[str, np.ndarray], stations: list[Station], power: float = 2.0) -> np.ndarray:
    """Opad dla punktu: ważenie odwrotnością odległości (1/d^p), dla każdego dnia tylko stacje z danymi."""
    if not stations:
        raise ValueError("brak stacji")
    w = np.array([1.0 / max(s.dist_km, 0.5) ** power for s in stations])
    m = np.vstack([series[s.code] for s in stations])
    ok = ~np.isnan(m)
    ww = w[:, None] * ok
    tot = ww.sum(axis=0)
    val = np.where(tot > 0, np.nansum(np.where(ok, m, 0) * ww, axis=0) / np.where(tot > 0, tot, 1), np.nan)
    return val


# --------------------------------------------------------------------------------------
# ERA5-Land, NASA POWER, prognoza wielomodelowa
# --------------------------------------------------------------------------------------

def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


ERA5_NETWORK = True  # False = tylko cache (sieć hackathonu: limit Open-Meteo wyczerpany)


def era5_land(lon: float, lat: float, start: date, end: date, key: str) -> tuple[np.ndarray, float | None]:
    q = urllib.parse.urlencode({"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
                                "start_date": start.isoformat(), "end_date": end.isoformat(),
                                "daily": "precipitation_sum", "models": "era5_land",
                                "timezone": "Europe/Warsaw"})
    d, dt = cached_json(DATA / "cache" / f"era5land_{key}.json", f"{ERA5_URL}?{q}", timeout=90,
                        allow_network=ERA5_NETWORK)
    return parse_era5(d, start, end), dt


def parse_era5(d: dict, start: date, end: date) -> np.ndarray:
    times = d["daily"]["time"]
    vals = d["daily"]["precipitation_sum"]
    m = {t: (np.nan if v is None else float(v)) for t, v in zip(times, vals)}
    return np.array([m.get(x.isoformat(), np.nan) for x in _days(start, end)])


def nasa_power(lon: float, lat: float, start: date, end: date, key: str) -> tuple[np.ndarray, float | None]:
    q = urllib.parse.urlencode({"parameters": "PRECTOTCORR", "community": "AG",
                                "longitude": f"{lon:.4f}", "latitude": f"{lat:.4f}",
                                "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
                                "format": "JSON"})
    d, dt = cached_json(DATA / "cache" / f"nasa_{key}.json", f"{NASA_URL}?{q}", timeout=90)
    return parse_nasa(d, start, end), dt


def parse_nasa(d: dict, start: date, end: date) -> np.ndarray:
    block = d["properties"]["parameter"]["PRECTOTCORR"]
    out = []
    for x in _days(start, end):
        v = block.get(x.strftime("%Y%m%d"), -999)
        out.append(np.nan if v is None or v <= -998 else float(v))
    return np.array(out)


def forecast_models(lon: float, lat: float, models=("icon_seamless", "ecmwf_ifs025", "gfs_seamless"),
                    days: int = 7) -> tuple[dict, float]:
    """Prognoza dobowego opadu z kilku modeli w JEDNYM zapytaniu Open-Meteo (models=a,b,c)."""
    q = urllib.parse.urlencode({"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
                                "daily": "precipitation_sum", "models": ",".join(models),
                                "forecast_days": days, "timezone": "Europe/Warsaw"})
    text, dt = http_get(f"{FORECAST_URL}?{q}", timeout=20)
    d = json.loads(text)["daily"]
    return {"time": d["time"], **{m: d.get(f"precipitation_sum_{m}") for m in models}}, dt


# --------------------------------------------------------------------------------------
# Łączenie i zgodność
# --------------------------------------------------------------------------------------

@dataclass
class PrecipResult:
    days: list[date]
    series: dict[str, np.ndarray]           # "imgw_idw", "era5_land", "nasa_power"
    stations: list[Station]
    timings_s: dict = field(default_factory=dict)


def combine(lon: float, lat: float, start: date, end: date, key: str,
            n: int = 3, max_km: float = 30.0, fallback_km: float = 50.0) -> PrecipResult:
    """Opad dla działki z 3 źródeł. IMGW = IDW z <= n stacji w promieniu max_km; gdy brak – stacje do
    fallback_km z oznaczeniem „stacje daleko” (niższa pewność); gdy i tam brak – bez IMGW."""
    days = _days(start, end)
    stations = nearest_stations(lon, lat, n=n, max_km=max_km, start=start, end=end)
    note = f"stacje ≤ {max_km:.0f} km"
    if not stations and fallback_km > max_km:
        stations = nearest_stations(lon, lat, n=n, max_km=fallback_km, start=start, end=end)
        note = f"brak stacji ≤ {max_km:.0f} km – użyto stacji do {fallback_km:.0f} km (niższa pewność)"
    if not stations:
        note = f"brak stacji IMGW ≤ {fallback_km:.0f} km"
    series, timings = {}, {"stations_note": note}
    if stations:
        series["imgw_idw"] = idw(imgw_daily(stations, start, end), stations)
    # każde źródło osobno – awaria jednego (np. 429 Open-Meteo) nie wywraca wyniku
    for name, fn in (("era5_land", era5_land), ("nasa_power", nasa_power)):
        try:
            series[name], timings[name] = fn(lon, lat, start, end, key)
        except RuntimeError as exc:
            timings[name] = f"niedostępne: {exc}"[:200]
    return PrecipResult(days, series, stations, timings)


def label_for(spread: float) -> str:
    if not math.isfinite(spread):
        return "brak danych"
    if spread <= AGREE_OK:
        return LABELS[0]
    if spread <= AGREE_WARN:
        return LABELS[1]
    return LABELS[2]


def window_sums(days: list[date], series: dict[str, np.ndarray], start: date, end: date,
                max_missing: float = 0.1) -> dict[str, float]:
    idx = [i for i, d in enumerate(days) if start <= d <= end]
    out = {}
    for k, v in series.items():
        part = v[idx]
        if len(part) == 0 or np.isnan(part).mean() > max_missing:
            out[k] = float("nan")
        else:
            out[k] = float(np.nansum(part) * len(part) / max(1, (~np.isnan(part)).sum()))
    return out


def agreement(days: list[date], series: dict[str, np.ndarray], on: date) -> dict:
    """Zgodność źródeł dla sezonu (1 IV – min(30 IX, data)) i ostatnich 30 dni przed datą.

    Miara: względny rozrzut sum = (max − min) / średnia. Progi: <= 15 % zgodne, <= 35 % różnią się,
    > 35 % mocno się różnią. Dla małych sum (< 20 mm) rozrzut liczony względem 20 mm (jeden zwykły deszcz),
    żeby 1 mm vs 3 mm nie dawało „mocno się różnią”.
    """
    res = {}
    season_start = date(on.year, 4, 1)
    windows = {"ostatnie_30_dni": (on - timedelta(days=29), on)}
    if on >= season_start:
        windows["sezon"] = (season_start, min(on, date(on.year, 9, 30)))
    for name, (a, b) in windows.items():
        sums = window_sums(days, series, a, b)
        good = {k: v for k, v in sums.items() if math.isfinite(v)}
        if len(good) < 2:
            res[name] = {"od": a.isoformat(), "do": b.isoformat(), "sumy_mm": sums,
                         "rozrzut": None, "ocena": "brak danych"}
            continue
        vals = list(good.values())
        mean = max(sum(vals) / len(vals), MIN_SUM_MM)
        spread = (max(vals) - min(vals)) / mean
        res[name] = {"od": a.isoformat(), "do": b.isoformat(),
                     "sumy_mm": {k: round(v, 1) for k, v in good.items()},
                     "rozrzut": round(spread, 3), "ocena": label_for(spread)}
    return res


def sentence(agr: dict) -> str:
    """Jedno zdanie dla rolnika (propozycja dla backendu)."""
    s = agr.get("sezon") or agr.get("ostatnie_30_dni")
    if not s or s["ocena"] == "brak danych":
        return "Za mało danych, żeby porównać źródła opadów."
    sums = s["sumy_mm"]
    lo, hi = min(sums.values()), max(sums.values())
    okres = "od 1 kwietnia" if "sezon" in agr else "w ostatnich 30 dniach"
    if s["ocena"] == "zgodne":
        return f"Stacje IMGW i modele pogody są zgodne: {okres} spadło ok. {round((lo + hi) / 2):.0f} mm."
    if s["ocena"] == "różnią się":
        return f"Źródła różnią się: {okres} od {lo:.0f} do {hi:.0f} mm – przyjmujemy pomiar ze stacji IMGW."
    return (f"Źródła mocno się różnią ({lo:.0f}–{hi:.0f} mm {okres}) – możliwe lokalne burze; "
            f"sprawdź deszczomierz na polu.")
