"""IMGW-PIB – opady dobowe ze stacji (A7, D82). Dane publiczne: https://danepubliczne.imgw.pl (to NIE jest GUGiK).

Port prototypu osoby C (research/precip/precip.py, bez merge c/research):
- archiwum dobowe OPAD i KLIMAT – pliki miesięczne dla całej Polski, SYNOP – plik roczny na stację,
- CSV w cp1250 bez nagłówka; opad SMDB + status: '' pomiar, '8' brak pomiaru (→ brak), '9' brak zjawiska (→ 0 mm),
  'Z' opad zbiorczy (wartość zostaje); w ZIP-ach SYNOP / KLIMAT pliki `*_t_*.csv` to dane terminowe – pomijamy,
- dnia nie ma w pliku, a stacja ma dane w tym miesiącu → 0 mm; miesiąc bez danych → brak,
- doba opadowa 6:00–6:00 UTC – źródła porównujemy na sumach z okien, nie dzień po dniu,
- współrzędne: archiwum ich nie ma – katalog z API /api/data/meteo (app/data/imgw/stations.json, zapis osoby C).

W aplikacji NIE ma zapytań do IMGW w czasie analizy: opady wszystkich stacji ze współrzędnymi są w zwartym magazynie
`app/data/imgw/opady.npz` (int16, dziesiąte części mm, −1 = brak), budowanym przez `scripts/build_imgw.py`
(pobieranie przez core/http.request – bez przekierowań). Działa offline i na hostingu bez pobierania.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import settings

SOURCE = "IMGW-PIB (stacje)"
SOURCE_URL = "https://danepubliczne.imgw.pl/"
ARCHIVE_URL = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/"
DATA_DIR = Path(__file__).parents[1] / "data" / "imgw"
STATIONS_FILE = DATA_DIR / "stations.json"
STORE_FILE = DATA_DIR / "opady.npz"

KINDS = {"opad": "o", "klimat": "k", "synop": "s"}  # rodzaj stacji → sufiks pliku
KIND_PRIORITY = {"synop": 0, "klimat": 1, "opad": 2}  # ta sama stacja w kilku archiwach: najlepsza jakość wygrywa
KIND_LABEL = {"synop": "stacja synoptyczna", "klimat": "stacja klimatologiczna", "opad": "posterunek opadowy"}
_COLS = {"opad": (5, 6), "klimat": (13, 14), "synop": (13, 14)}  # kolumny SMDB / WSMDB (od 0)
MISSING = -1  # w magazynie int16


def archive_url(kind: str, year: int, month: int | None = None, synop_id: str | None = None) -> str:
    if kind == "synop":  # plik roczny na stację (numer = 3 ostatnie cyfry kodu)
        return f"{ARCHIVE_URL}synop/{year}/{year}_{synop_id}_s.zip"
    return f"{ARCHIVE_URL}{kind}/{year}/{year}_{month:02d}_{KINDS[kind]}.zip"


def parse_daily_csv(text: str, kind: str) -> list[tuple[str, str, date, float | None, str]]:
    """Wiersze (kod, nazwa, data, opad_mm | None, status). '8' → None, '9' → 0, 'Z' – wartość zostaje."""
    out = []
    ci, wi = _COLS[kind]
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


def zip_rows(content: bytes, kind: str):
    """Wiersze dobowe z jednego ZIP-a archiwum; pliki terminowe (`*_t_*.csv`) są pomijane – mają inne kolumny."""
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for name in z.namelist():
            low = name.lower()
            if not low.endswith(".csv") or "_t_" in low:
                continue
            yield from parse_daily_csv(z.read(name).decode("cp1250", errors="replace"), kind)


def haversine_km(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def station_catalog() -> dict[str, dict]:
    """Kod stacji (9 cyfr) → {name, lon, lat, elev} – stacje ze współrzędnymi (API IMGW /api/data/meteo)."""
    return json.loads(STATIONS_FILE.read_text(encoding="utf-8"))["stations"]


# ── magazyn opadów ──────────────────────────────────────────────────────────────────────────


@dataclass
class Store:
    codes: np.ndarray       # kody stacji (str)
    names: np.ndarray
    kinds: np.ndarray
    lon: np.ndarray
    lat: np.ndarray
    start: np.datetime64    # pierwszy dzień magazynu
    data: np.ndarray        # int16 [dni × stacje], dziesiąte mm, −1 = brak
    built: str = ""

    @property
    def days(self) -> int:
        return self.data.shape[0]

    @property
    def end(self) -> np.datetime64:
        return self.start + np.timedelta64(self.days - 1, "D")

    def series(self, idx: int, dates: np.ndarray) -> np.ndarray:
        """Opad stacji [mm] na osi `dates` (datetime64[D]); poza magazynem i przy braku pomiaru – NaN."""
        out = np.full(len(dates), np.nan)
        pos = (dates - self.start).astype(int)
        ok = (pos >= 0) & (pos < self.days)
        raw = self.data[pos[ok], idx].astype(float)
        raw[raw < 0] = np.nan
        out[ok] = raw / 10.0
        return out


def save_store(path: Path, codes, names, kinds, lon, lat, start: date, data: np.ndarray, built: str) -> None:
    np.savez_compressed(path, codes=np.array(codes), names=np.array(names), kinds=np.array(kinds),
                        lon=np.array(lon, dtype=np.float32), lat=np.array(lat, dtype=np.float32),
                        start=np.array(start.isoformat()), data=data.astype(np.int16), built=np.array(built))


def read_store(path: Path) -> Store:
    with np.load(path, allow_pickle=False) as z:
        return Store(codes=z["codes"], names=z["names"], kinds=z["kinds"], lon=z["lon"].astype(float),
                     lat=z["lat"].astype(float), start=np.datetime64(str(z["start"]), "D"), data=z["data"],
                     built=str(z["built"]))


@lru_cache(maxsize=2)
def _load(path: str, mtime: float) -> Store:
    return read_store(Path(path))


def store() -> Store | None:
    """Magazyn opadów (None: wyłączony w ustawieniach albo brak pliku – wtedy opad z NASA, jak przed A7)."""
    if not settings.imgw_enabled:
        return None
    p = Path(settings.imgw_store or STORE_FILE)
    if not p.exists():  # braku pliku nie zapamiętujemy – magazyn może zostać dobudowany
        return None
    return _load(str(p), p.stat().st_mtime)


def clear_cache() -> None:
    _load.cache_clear()


@dataclass
class StationPick:
    idx: int
    code: str
    name: str
    kind: str
    lon: float
    lat: float
    dist_km: float
    coverage: float  # udział dni z pomiarem w oknie analizy (część wspólna z magazynem)


def nice_name(name: str) -> str:
    """„KOŁUDA WIELKA” → „Kołuda Wielka”, „LUBLIN-RADAWIEC” → „Lublin-Radawiec”."""
    return "-".join(" ".join(w.capitalize() for w in part.split(" ")) for part in name.strip().split("-"))


def nearest(st: Store, lon: float, lat: float, dates: np.ndarray, n: int = 3, max_km: float = 30.0,
            min_coverage: float = 0.8) -> list[StationPick]:
    """Najbliższe stacje z danymi: w promieniu `max_km`, z pomiarem w ≥ `min_coverage` dni części wspólnej okna
    `dates` i magazynu. Najbliższe najpierw, najwyżej `n`."""
    if len(dates) == 0:
        return []
    pos = (dates - st.start).astype(int)
    pos = pos[(pos >= 0) & (pos < st.days)]
    if len(pos) == 0:
        return []
    dist = haversine_km(lon, lat, st.lon, st.lat)
    out = []
    for i in np.argsort(dist):
        if dist[i] > max_km:
            break
        cov = float((st.data[pos[0]: pos[-1] + 1, i] >= 0).mean())
        if cov >= min_coverage:
            out.append(StationPick(int(i), str(st.codes[i]), nice_name(str(st.names[i])), str(st.kinds[i]),
                                   float(st.lon[i]), float(st.lat[i]), round(float(dist[i]), 1), round(cov, 3)))
            if len(out) >= n:
                break
    return out


def idw(series: list[np.ndarray], dist_km: list[float], power: float = 2.0) -> np.ndarray:
    """Opad dla punktu: wagi 1/d^p; dla każdego dnia liczą się tylko stacje z pomiarem; żadna → NaN."""
    if not series:
        raise ValueError("brak stacji")
    w = np.array([1.0 / max(d, 0.5) ** power for d in dist_km])
    m = np.vstack(series)
    ok = ~np.isnan(m)
    ww = w[:, None] * ok
    tot = ww.sum(axis=0)
    return np.where(tot > 0, np.nansum(np.where(ok, m, 0) * ww, axis=0) / np.where(tot > 0, tot, 1), np.nan)


def weights(dist_km: list[float], power: float = 2.0) -> list[float]:
    w = np.array([1.0 / max(d, 0.5) ** power for d in dist_km])
    return [round(float(x), 3) for x in w / w.sum()]


class StoreBuilder:
    """Składa magazyn z wierszy archiwum (używa scripts/build_imgw.py; logika osobno, żeby dało się ją testować):
    - stacja w kilku archiwach → zostaje rodzaj o najwyższej jakości (synop > klimat > opad),
    - ten sam dzień dwa razy (korekty) → zostaje wiersz z pomiarem,
    - miesiąc z danymi: dni nieobecne w pliku = 0 mm („brak zjawiska”); miesiąc bez danych = brak."""

    def __init__(self, start: date, end: date, catalog: dict[str, dict]):
        self.start, self.end, self.catalog = start, end, catalog
        self.st: dict[str, dict] = {}

    def add(self, kind: str, rows) -> None:
        for code, name, d, val, _status in rows:
            if code not in self.catalog or not (self.start <= d <= self.end):
                continue
            s = self.st.get(code)
            if s is None or KIND_PRIORITY[kind] < KIND_PRIORITY[s["kind"]]:
                s = self.st[code] = {"kind": kind, "name": name, "values": {}, "months": set()}
            elif s["kind"] != kind:
                continue  # stacja jest już w lepszym archiwum
            k = (d - self.start).days
            if val is None:
                s["values"].setdefault(k, MISSING)
            else:
                s["values"][k] = int(round(val * 10))
                s["months"].add((d.year, d.month))

    def finish(self) -> tuple[list[str], np.ndarray, dict]:
        """(kody, macierz int16 [dni × stacje], indeks) – macierz przycięta do ostatniego dnia z jakimkolwiek pomiarem."""
        from datetime import timedelta

        n_days = (self.end - self.start).days + 1
        codes = sorted(c for c, s in self.st.items() if s["months"])
        data = np.full((n_days, len(codes)), MISSING, dtype=np.int16)
        index = {}
        for j, c in enumerate(codes):
            s = self.st[c]
            for (y, m) in s["months"]:
                a = date(y, m, 1)
                b = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
                i0, i1 = max(0, (a - self.start).days), min(n_days - 1, (b - self.start).days)
                data[i0: i1 + 1, j] = 0
            for k, v in s["values"].items():
                data[k, j] = v
            ym = sorted(s["months"])
            index[c] = {"name": s["name"], "kind": s["kind"], "months": len(ym),
                        "first": f"{ym[0][0]}-{ym[0][1]:02d}", "last": f"{ym[-1][0]}-{ym[-1][1]:02d}",
                        "valid_days": int((data[:, j] >= 0).sum())}
        if len(codes):
            data = data[: int(np.flatnonzero((data >= 0).any(axis=1)).max()) + 1]
        return codes, data, index
