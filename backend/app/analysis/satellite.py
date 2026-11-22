"""Sentinel-2 dla działki (A11, D86–D88): tryb na żywo w budżecie, szereg czasowy (tylko cache), zdanie, warstwy mapy.

- Na żywo (GET /api/satellite, ok. 15 s i 10 MB): ostatnia czysta scena z 60 dni przed datą analizy (≥ 70% ważnych
  pikseli w obrysie wg SCL) + najbliższa czysta scena z tej samej pory rok wcześniej (±20 dni). Kandydaci: najpierw
  sceny prawie bezchmurne (≤ 10% chmur całej sceny) od najnowszej, potem reszta wg chmur; po pierwszej dobrej koniec.
  Najpierw maska SCL (~30 kB), pasma tylko dla sceny, która przeszła. Brak czystej → ostatnia z ≥ 20% ważnych
  pikseli z ostrzeżeniem; nic → `brak_danych` (bez błędu HTTP).
- Szereg 12 mies. (1 punkt / 15 dni) – NIE na żywo: `scripts/warm_demo.py` / `scripts/warm_satellite.py`, w cache.
- /api/analysis bierze wynik tylko z cache (`cached_result`); brak → `status: pending` (analiza < 30 s, KOWR).
Progi, zdania, kolory: rules/satellite.yaml.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import struct
import zlib
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import shapely
import yaml
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry

from app.core.cache import FOREVER, TTLCache, offline
from app.core.config import settings
from app.core.http import SourceError
from app.schemas.analysis import Satellite, SatelliteScene, SatelliteSeriesPoint, SourceTag
from app.sources import sentinel as S

log = logging.getLogger(__name__)
RULES = Path(__file__).parent / "rules" / "satellite.yaml"
NOTE = ("Sentinel-2 L2A (ESA Copernicus, przez Earth Search / AWS), piksel 10 m. NDVI = kondycja roślin, NDMI = "
        "wilgotność roślin – mediany w obrysie; chmury, cienie i śnieg wycięte maską SCL. Progi orientacyjne.")

# wynik na żywo (dict) i szereg (list) – trwały cache (D53); klucz z kształtu działki i daty analizy
_cache: TTLCache[dict] = TTLCache(ttl_s=None, max_items=512, name=S.SOURCE_SHORT)
_tasks: dict[tuple, asyncio.Task] = {}


@lru_cache
def cfg() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))["satellite"]


def geom_key(geom_4326: BaseGeometry) -> str:
    g = shapely.set_precision(geom_4326, 1e-6)
    return hashlib.sha1(g.wkt.encode()).hexdigest()[:16]


# ── siatka działki w układzie sceny ─────────────────────────────────────────────────────────


@dataclass
class Grid:
    epsg: int
    rows: tuple[int, int]      # okno 10 m (parzyste – zgodne z siatką 20 m SCL / B11)
    cols: tuple[int, int]
    mask: np.ndarray           # obrys na siatce 10 m
    bbox_4326: tuple[float, float, float, float]


@lru_cache(maxsize=16)
def _tr(epsg_from: int, epsg_to: int) -> Transformer:
    return Transformer.from_crs(epsg_from, epsg_to, always_xy=True)


def grid_for(geom_4326: BaseGeometry, scene: S.Scene, margin_m: float = 20.0) -> Grid:
    g = shapely.transform(geom_4326, lambda x, y: _tr(4326, scene.epsg).transform(x, y), interleaved=False)
    xmin, ymin, xmax, ymax = g.bounds
    t10 = scene.assets["red"].transform
    r0, r1, c0, c1 = S.pixel_window(t10, (xmin - margin_m, ymin - margin_m, xmax + margin_m, ymax + margin_m))
    r0, c0 = r0 - r0 % 2, c0 - c0 % 2
    r1, c1 = r1 + r1 % 2, c1 + c1 % 2
    xs = t10[2] + (np.arange(c0, c1) + 0.5) * t10[0]
    ys = t10[5] + (np.arange(r0, r1) + 0.5) * t10[4]
    X, Y = np.meshgrid(xs, ys)
    mask = shapely.contains_xy(g, X, Y)
    if not mask.any():  # działka mniejsza niż piksel – piksel ze środkiem działki
        c = g.centroid
        mask[np.unravel_index(np.argmin((X - c.x) ** 2 + (Y - c.y) ** 2), X.shape)] = True
    ex = [t10[2] + c0 * t10[0], t10[2] + c1 * t10[0]]
    ey = [t10[5] + r1 * t10[4], t10[5] + r0 * t10[4]]
    lon, lat = _tr(scene.epsg, 4326).transform([ex[0], ex[1], ex[0], ex[1]], [ey[0], ey[0], ey[1], ey[1]])
    return Grid(scene.epsg, (r0, r1), (c0, c1), mask,
                (round(min(lon), 6), round(min(lat), 6), round(max(lon), 6), round(max(lat), 6)))


@dataclass
class Point:
    scene: S.Scene
    valid_pct: float
    cloud_pct: float
    snow_pct: float
    ndvi: float | None = None
    ndmi: float | None = None
    arrays: dict | None = None   # ndvi, ndmi, valid (do warstw)
    grid: Grid | None = None


async def scene_point(scene: S.Scene, geom: BaseGeometry, stats: S.Stats, bands: bool, swir: bool = True,
                      min_red_pct: float | None = None) -> Point:
    """Maska SCL (zawsze) i – gdy `bands` – NDVI / NDMI w obrysie (`swir=False` – tylko NDVI, mniej bajtów).
    `min_red_pct`: najpierw samo pasmo czerwone – gdy za mało pikseli z odbiciem > 0 (zbyt ciemne zimą), bez NIR / B11."""
    gr = grid_for(geom, scene)
    (r0, r1), (c0, c1) = gr.rows, gr.cols
    shape = (r1 - r0, c1 - c0)
    scl20 = await S.read_window(scene.assets["scl"].href, (r0 // 2, r1 // 2), (c0 // 2, c1 // 2), stats)
    scl = S.upsample2(scl20, shape)
    sh = S.scl_shares(scl, gr.mask)
    p = Point(scene, round(sh["valid_pct"], 1), round(sh["cloud_pct"], 1), round(sh["snow_pct"], 1), grid=gr)
    if not bands:
        return p
    a = scene.assets
    if min_red_pct is not None:
        red_dn = await S.read_window(a["red"].href, (r0, r1), (c0, c1), stats)
        red_ok = (S.reflectance(red_dn, a["red"].scale, a["red"].offset) > 0) & np.isin(scl, S.SCL_VALID) & gr.mask
        share = 100.0 * float(red_ok.sum()) / max(int(gr.mask.sum()), 1)
        if share < min_red_pct:
            p.valid_pct = round(share, 1)
            return p
        jobs = [S.read_window(a["nir"].href, (r0, r1), (c0, c1), stats)]
    else:
        jobs = [S.read_window(a["red"].href, (r0, r1), (c0, c1), stats),
                S.read_window(a["nir"].href, (r0, r1), (c0, c1), stats)]
    if swir:
        jobs.append(S.read_window(a["swir16"].href, (r0 // 2, r1 // 2), (c0 // 2, c1 // 2), stats))
    got = await asyncio.gather(*jobs)
    if min_red_pct is not None:
        got = [red_dn, *got]
    red_dn, nir_dn = got[0], got[1]
    sw = (S.reflectance(S.upsample2(got[2], shape), a["swir16"].scale, a["swir16"].offset) if swir else None)
    ndvi, ndmi = S.indices(S.reflectance(red_dn, a["red"].scale, a["red"].offset),
                           S.reflectance(nir_dn, a["nir"].scale, a["nir"].offset), sw)
    valid = np.isin(scl, S.SCL_VALID) & gr.mask & np.isfinite(ndvi)
    p.ndvi, p.ndmi = S.median_in(ndvi, valid), S.median_in(ndmi, valid)
    # udział widocznej działki po odrzuceniu pikseli zbyt ciemnych do policzenia NDVI (odbicie ≤ 0 – niskie słońce zimą)
    p.valid_pct = round(100.0 * float(valid.sum()) / max(int(gr.mask.sum()), 1), 1)
    p.arrays = {"ndvi": ndvi, "ndmi": ndmi, "valid": valid, "inside": gr.mask}
    return p


def order_candidates(scenes: list[S.Scene]) -> list[S.Scene]:
    """Najpierw sceny z umiarkowanym zachmurzeniem całej sceny (≤ 40%) od najnowszej – o działce decyduje maska SCL –
    potem reszta wg chmur."""
    clear = cfg()["live"]["clear_scene_cloud_pct"]
    return sorted(scenes, key=lambda s: (s.cloud > clear, -s.date.toordinal() if s.cloud <= clear else s.cloud))


def _within_budget(stats: S.Stats, share: float = 1.0) -> bool:
    return stats.seconds < settings.sentinel_budget_s * share and stats.mb < settings.sentinel_budget_mb * share


async def pick(scenes: list[S.Scene], geom: BaseGeometry, stats: S.Stats, max_checks: int,
               allow_fallback: bool, swir: bool = True) -> tuple[Point | None, str | None]:
    """Pierwsza scena, w której ≥ 70% działki jest widoczne: najpierw maska SCL (tanio), potem pasma – i ponownie udział
    pikseli, dla których da się policzyć NDVI (zimą przy niskim słońcu część ma odbicie ≤ 0). Brak takiej sceny →
    najlepsza z ≥ 20% z ostrzeżeniem (`allow_fallback`) albo None."""
    c = cfg()["live"]
    best_scl: Point | None = None
    best_full: Point | None = None
    for sc in scenes[:max_checks]:
        if not _within_budget(stats, 0.7):
            break
        p = await scene_point(sc, geom, stats, bands=False)
        if p.valid_pct < c["min_valid_pct"]:
            if best_scl is None or p.valid_pct > best_scl.valid_pct:
                best_scl = p
            continue
        full = await scene_point(sc, geom, stats, bands=True, swir=swir, min_red_pct=c["fallback_min_valid_pct"])
        if full.ndvi is not None and full.valid_pct >= c["min_valid_pct"]:
            return full, None
        if full.ndvi is not None and (best_full is None or full.valid_pct > best_full.valid_pct):
            best_full = full
    if not allow_fallback:
        return None, None
    if best_full is not None and best_full.valid_pct >= c["fallback_min_valid_pct"]:
        return best_full, (f"Brak w pełni czystego zdjęcia – liczymy z {best_full.valid_pct:.0f}% działki "
                           f"(zdjęcie z {best_full.scene.date:%d.%m.%Y}).")
    if best_scl is not None and best_scl.valid_pct >= c["fallback_min_valid_pct"] and _within_budget(stats, 0.85):
        full = await scene_point(best_scl.scene, geom, stats, bands=True, swir=swir)
        if full.ndvi is not None and full.valid_pct >= c["fallback_min_valid_pct"]:
            return full, (f"Brak bezchmurnego zdjęcia – pokazujemy najlepsze dostępne z {full.scene.date:%d.%m.%Y} "
                          f"(widać {full.valid_pct:.0f}% działki).")
    return None, None


@dataclass
class LiveResult:
    now: Point | None
    last_year: Point | None
    warning: str | None
    stats: S.Stats
    searched: int


async def compute_live(geom: BaseGeometry, on: date) -> LiveResult:
    c = cfg()["live"]
    stats = S.Stats()
    bbox = geom.bounds
    tol = c["last_year_tolerance_days"]
    ly_start = on - timedelta(days=365 + c["days_back"] + tol)
    ly_end = on - timedelta(days=365 - tol)
    now_scenes, ly_scenes = await asyncio.gather(
        S.search(bbox, on - timedelta(days=c["days_back"]), on, stats),
        S.search(bbox, ly_start, ly_end, stats), return_exceptions=True)
    if isinstance(now_scenes, BaseException):
        raise now_scenes
    now, warning = await pick(order_candidates(now_scenes), geom, stats, c["max_scl_checks"], allow_fallback=True)
    last = None
    if now is not None and not isinstance(ly_scenes, BaseException) and _within_budget(stats, 0.75):
        target = now.scene.date - timedelta(days=365)
        cand = sorted((s for s in ly_scenes if abs((s.date - target).days) <= tol),
                      key=lambda s: (s.cloud > c["clear_scene_cloud_pct"], abs((s.date - target).days), s.cloud))
        # rok temu – tylko NDVI (bez pasma B11): porównanie zieleni, a budżet zostaje w ok. 10 MB; po czasie – bez porównania
        left = settings.sentinel_budget_s - stats.seconds
        try:
            # rok temu wystarczy ≥ 20% widocznej działki (porównanie median zieleni)
            last, _ = await asyncio.wait_for(pick(cand, geom, stats, c["max_scl_checks_last_year"], allow_fallback=True,
                                                  swir=False), max(2.0, left))
        except (asyncio.TimeoutError, SourceError):
            last = None
    return LiveResult(now, last, warning, stats, len(now_scenes))


async def compute_series(geom: BaseGeometry, on: date) -> tuple[list[SatelliteSeriesPoint], S.Stats]:
    """Szereg 12 mies.: w każdym oknie 15 dni najmniej zachmurzona scena, która przeszła maskę SCL (najwyżej 2 próby)."""
    c = cfg()["series"]
    stats = S.Stats()
    start = on - timedelta(days=30 * c["months"] + 5)
    scenes = await S.search(geom.bounds, start, on, stats, max_cloud=c["max_scene_cloud_pct"], limit=200)
    out: list[SatelliteSeriesPoint] = []
    b0 = start
    while b0 <= on:
        b1 = b0 + timedelta(days=c["bin_days"] - 1)
        cand = sorted((s for s in scenes if b0 <= s.date <= b1), key=lambda s: s.cloud)
        for sc in cand[: c["max_scl_checks_per_bin"]]:
            try:
                p = await scene_point(sc, geom, stats, bands=False)
                if p.valid_pct < cfg()["live"]["min_valid_pct"]:
                    continue
                full = await scene_point(sc, geom, stats, bands=True)
            except SourceError as exc:  # pojedyncza scena niedostępna – szereg liczymy dalej
                log.warning("Sentinel-2 szereg: %s – %s", sc.id, exc.message)
                continue
            if full.ndvi is not None:
                out.append(SatelliteSeriesPoint(date=sc.date, ndvi=full.ndvi, ndmi=full.ndmi, valid_pct=full.valid_pct))
                break
        b0 = b1 + timedelta(days=1)
    return sorted(out, key=lambda x: x.date), stats


# ── zdanie i poziom ─────────────────────────────────────────────────────────────────────────


def classify(value: float | None, table: list[dict]) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    for row in table:
        if value < row["max"]:
            return row["key"], row["label"]
    return table[-1]["key"], table[-1]["label"]


def describe(ndvi: float | None, ndmi: float | None, ly_ndvi: float | None, scene_date: date | None,
             valid_pct: float | None = None, partial: bool = False) -> dict:
    """Zdanie, klasy i poziom – z WARTOŚCI (D87): klasa NDVI, porównanie z tą samą porą rok temu, NDMI tylko w sezonie
    przy gęstym łanie. Poza sezonem wysoki NDVI = oziminy / międzyplon, nie „niska zieleń”."""
    c = cfg()
    s = c["sentences"]
    if ndvi is None or scene_date is None:
        return {"sentence": None, "level": None, "ndvi_class": None, "ndvi_label": None, "ndmi_class": None,
                "ndmi_label": None, "trend": None, "change": None, "in_season": None}
    season = scene_date.month in c["season_months"]
    nk, nl = classify(ndvi, c["ndvi"])
    mk, ml = classify(ndmi, c["ndmi"]) if season and ndmi is not None and ndvi >= c["ndmi_min_ndvi"] else (None, None)
    change = None if ly_ndvi is None else round(ndvi - ly_ndvi, 3)
    thr = c["ndvi_change"]
    trend = None if change is None else "lepiej" if change > thr else "gorzej" if change < -thr else "podobnie"
    txt = s["prefix"].format(date=f"{scene_date:%d.%m.%Y}")
    txt += (s["state_season"] if season else s["state_off"])[nk]
    if trend is None:
        txt += s["compare"]["none"]
    elif trend == "gorzej" and mk == "sucho":
        txt += s["stress_worse"]
    else:
        txt += s["compare"]["better" if trend == "lepiej" else "similar" if trend == "podobnie" else
                            ("worse" if season else "worse_off")]
        if mk == "sucho":
            txt += s["stress"]
    if mk == "dobrze" and trend != "gorzej":
        txt += s["wet"]
    if partial and valid_pct is not None:
        txt += s["partial"].format(valid=valid_pct)
    if season:
        if trend == "gorzej" and mk == "sucho":
            level = "bad"
        elif trend == "gorzej" or mk == "sucho" or (nk in ("gleba", "slaba") and scene_date.month in (5, 6, 7)):
            level = "warn"
        else:
            level = "ok"
    else:
        anomaly = change is not None and change < -c["ndvi_change_anomaly_off_season"]
        level = "warn" if anomaly else "info"
    return {"sentence": txt, "level": level, "ndvi_class": nk, "ndvi_label": nl, "ndmi_class": mk, "ndmi_label": ml,
            "trend": trend, "change": change, "in_season": season}


# ── warstwy PNG ─────────────────────────────────────────────────────────────────────────────


def _hex(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def colorize(values: np.ndarray, stops: list) -> np.ndarray:
    xs = np.array([s[0] for s in stops], float)
    cols = np.array([_hex(s[1]) for s in stops], float)
    v = np.clip(np.nan_to_num(values, nan=xs[0]), xs[0], xs[-1])
    return np.stack([np.interp(v, xs, cols[:, k]) for k in range(3)], axis=-1).astype(np.uint8)


def png_rgba(rgba: np.ndarray) -> bytes:
    """Minimalny koder PNG (RGBA 8 bit) – zlib + struct, bez dodatkowych bibliotek."""
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def layer_png(values: np.ndarray, valid: np.ndarray, inside: np.ndarray, key: str, scale: int = 8) -> bytes:
    """Piksel 10 m = `scale` px (ostre krawędzie); poza obrysem przezroczyste, chmury / braki – białe."""
    c = cfg()["colors"]
    rgb = colorize(values, c[key]["stops"])
    alpha = np.where(inside, 235, 0).astype(np.uint8)
    cloud = inside & ~valid
    rgb[cloud] = _hex(c["cloud"])
    alpha[cloud] = 200
    rgba = np.dstack([rgb, alpha])
    rgba = np.repeat(np.repeat(rgba, scale, axis=0), scale, axis=1)
    return png_rgba(rgba)


def layers_from(p: Point) -> dict:
    a = p.arrays
    return {"bbox": list(p.grid.bbox_4326),
            "kondycja": base64.b64encode(layer_png(a["ndvi"], a["valid"], a["inside"], "kondycja")).decode(),
            "wilgotnosc": base64.b64encode(layer_png(a["ndmi"], a["valid"], a["inside"], "wilgotnosc")).decode(),
            "date": p.scene.date.isoformat()}


# ── wynik, cache, kontrakt ──────────────────────────────────────────────────────────────────


def _scene(p: Point) -> SatelliteScene:
    return SatelliteScene(date=p.scene.date, scene_id=p.scene.id, ndvi=p.ndvi, ndmi=p.ndmi, valid_pct=p.valid_pct,
                          cloud_pct=p.cloud_pct)


def to_contract(res: LiveResult) -> Satellite:
    tag = SourceTag(kind="pomiar" if res.now else "brak_danych", date=res.now.scene.date if res.now else None,
                    source=S.SOURCE)
    if res.now is None:
        return Satellite(status="brak_danych", sentence=cfg()["sentences"]["none"].format(days=cfg()["live"]["days_back"]),
                         warning=f"Brak bezchmurnego zdjęcia z ostatnich {cfg()['live']['days_back']} dni.", note=NOTE,
                         downloaded_mb=round(res.stats.mb, 2), compute_s=round(res.stats.seconds, 1), source_tag=tag)
    n, ly = res.now, res.last_year
    d = describe(n.ndvi, n.ndmi, ly.ndvi if ly else None, n.scene.date, n.valid_pct, partial=res.warning is not None)
    return Satellite(
        status="ok", date=n.scene.date, scene_id=n.scene.id, ndvi=n.ndvi, ndmi=n.ndmi, ndvi_class=d["ndvi_class"],
        ndvi_label=d["ndvi_label"], ndmi_class=d["ndmi_class"], ndmi_label=d["ndmi_label"], valid_pct=n.valid_pct,
        cloud_pct=n.cloud_pct, last_year=_scene(ly) if ly else None, ndvi_change=d["change"], trend=d["trend"],
        level=d["level"], in_season=d["in_season"], sentence=d["sentence"], warning=res.warning,
        layers=["kondycja", "wilgotnosc"], downloaded_mb=round(res.stats.mb, 2), compute_s=round(res.stats.seconds, 1),
        note=NOTE, source_tag=tag)


FAIL_TTL_S = 1800.0      # A8: awaria źródła – 30 min (dziś awarie nie trafiają do cache)
NO_IMAGE_TTL_S = 43_200.0  # A15: „brak bezchmurnego zdjęcia” to nie awaria – 12 h, potem ponowna próba


def _ttl(on: date) -> float:
    return settings.sentinel_cache_ttl_today_s if on >= date.today() else FOREVER


def _store(geom: BaseGeometry, on: date, sat: Satellite, layers: dict | None) -> None:
    k = geom_key(geom)
    # brak sceny (często: budżet czasu przy wolnym S3 / duża działka) – krótko, potem ponowna próba (A8)
    ttl = _ttl(on) if sat.status == "ok" else NO_IMAGE_TTL_S
    _cache.set(("live", k, on.isoformat()), {"satellite": sat.model_dump(mode="json"), "layers": layers}, ttl)
    prev = _lookup(("latest", k))
    if prev is None or prev["on"] <= on.isoformat():  # „latest” nie cofa się do starszej daty (przykład historyczny)
        _cache.set(("latest", k), {"on": on.isoformat()}, FOREVER)
    if sat.status == "ok" and sat.date is not None:  # indeks zapisanych scen działki (A8, D90)
        idx = [x for x in (_lookup(("index", k)) or {}).get("entries", []) if x["on"] != on.isoformat()]
        idx.append({"on": on.isoformat(), "scene": sat.date.isoformat()})
        _cache.set(("index", k), {"entries": idx[-50:]}, FOREVER)


def _lookup(key: tuple) -> dict | None:
    hit = _cache.get(key)
    if hit is not None:
        return hit
    stale = _cache.get_stale(key)
    return stale[0] if stale else None


def _entry(geom: BaseGeometry, on: date) -> dict | None:
    """Wpis pod dokładną datą analizy, a gdy go nie ma – NAJNOWSZA zapisana scena z datą ≤ data analizy (najwyżej
    `days_back` dni wcześniej), np. scena 16.11 dla analizy 22.11 (A8, D90). Dla daty historycznej scena nigdy nie jest
    późniejsza niż ta data."""
    k = geom_key(geom)
    hit = _lookup(("live", k, on.isoformat()))
    if hit is not None and hit["satellite"].get("status") != "ok" and _cache.get(("live", k, on.isoformat())) is None:
        hit = None  # przeterminowana porażka – nie zwracamy jej jako wyniku
    if hit is not None and hit["satellite"].get("status") == "ok":
        return hit
    cands = list((_lookup(("index", k)) or {}).get("entries", []))
    latest = _lookup(("latest", k))  # wpisy sprzed indeksu
    if latest and not any(x["on"] == latest["on"] for x in cands):
        e = _lookup(("live", k, latest["on"]))
        if e and e["satellite"].get("date"):
            cands.append({"on": latest["on"], "scene": e["satellite"]["date"]})
    days = cfg()["live"]["days_back"]
    if not cands:  # wpisy sprzed indeksu – zapisane dni wstecz od daty analizy
        for d in range(1, days + 1):
            day = (on - timedelta(days=d)).isoformat()
            e = _lookup(("live", k, day))
            if e and e["satellite"].get("date"):
                cands.append({"on": day, "scene": e["satellite"]["date"]})
    ok = [x for x in cands if x.get("scene") and 0 <= (on - date.fromisoformat(x["scene"])).days <= days]
    for x in sorted(ok, key=lambda x: (x["scene"], x["on"]), reverse=True):
        e = _lookup(("live", k, x["on"]))
        if e is not None and e["satellite"].get("status") == "ok":
            return e
    return hit


def _with_series(sat: Satellite, geom: BaseGeometry, on: date) -> Satellite:
    k = geom_key(geom)
    ser = _lookup(("series", k, on.isoformat()))
    if ser is None:
        latest = _lookup(("series_latest", k))
        if latest and abs((on - date.fromisoformat(latest["on"])).days) <= 10:
            ser = _lookup(("series", k, latest["on"]))
    if ser:
        pts = [SatelliteSeriesPoint.model_validate(x) for x in ser["points"]]
        return sat.model_copy(update={"series": pts, "series_note": f"{len(pts)} zdjęć bez chmur z 12 miesięcy "
                                                                    "(1 na 15 dni)"})
    return sat


def cached_result(geom: BaseGeometry, on: date) -> Satellite | None:
    """Wynik z cache (bez sieci) – używa /api/analysis i raport."""
    e = _entry(geom, on)
    if e is None:
        return None
    sat = Satellite.model_validate(e["satellite"]).model_copy(update={"cached": True})
    return _with_series(sat, geom, on)


def cached_layers(geom: BaseGeometry, on: date) -> dict | None:
    e = _entry(geom, on)
    return e.get("layers") if e else None


def pending() -> Satellite:
    return Satellite(status="pending", sentence=cfg()["sentences"]["pending"],
                     note="Zdjęcie satelitarne liczone osobno (GET /api/satellite) – analiza nie czeka.",
                     source_tag=SourceTag(kind="brak_danych", source=S.SOURCE))


async def live(geom: BaseGeometry, on: date) -> Satellite:
    """Wynik na żywo (z cache, jeśli jest). Awaria źródła → `brak_danych` z ostrzeżeniem, nie wyjątek."""
    hit = cached_result(geom, on)
    if hit is not None:
        return hit
    key = ("task", geom_key(geom), on.isoformat())
    task = _tasks.get(key)
    if task is None or task.done():
        task = asyncio.ensure_future(_compute_and_store(geom, on))
        _tasks[key] = task
    try:
        return _with_series(await asyncio.shield(task), geom, on)
    finally:
        if task.done():
            _tasks.pop(key, None)


async def _compute_and_store(geom: BaseGeometry, on: date) -> Satellite:
    if not settings.sentinel_enabled:  # bez zapytań – tylko zapisane sceny (komunikat neutralny dla rolnika)
        return Satellite(status="brak_danych", warning="Brak zapisanego zdjęcia satelitarnego tej działki.", note=NOTE,
                         source_tag=SourceTag(kind="brak_danych", source=S.SOURCE))
    if offline():
        return Satellite(status="brak_danych", warning="Brak zapisanego zdjęcia satelitarnego tej działki.",
                         note=NOTE, source_tag=SourceTag(kind="brak_danych", source=S.SOURCE))
    try:
        res = await asyncio.wait_for(compute_live(geom, on), settings.sentinel_budget_s + 10)
    except (SourceError, asyncio.TimeoutError) as exc:
        msg = exc.message if isinstance(exc, SourceError) else "przekroczony czas pobierania"
        return Satellite(status="brak_danych", warning=f"Zdjęcia satelitarne niedostępne: {msg}.", note=NOTE,
                         source_tag=SourceTag(kind="brak_danych", source=S.SOURCE))
    sat = to_contract(res)
    _store(geom, on, sat, layers_from(res.now) if res.now is not None else None)
    log.info("Sentinel-2: %s – %s, %.1f s, %.2f MB, %d zapytań", geom_key(geom), sat.status, res.stats.seconds,
             res.stats.mb, res.stats.requests)
    return sat


def start_background(geom: BaseGeometry, on: date) -> None:
    """Analiza bez wyniku w cache uruchamia liczenie w tle (frontend i tak dociągnie /api/satellite – dostanie gotowe)."""
    if not settings.sentinel_background or not settings.sentinel_enabled or offline():
        return
    key = ("task", geom_key(geom), on.isoformat())
    if key in _tasks and not _tasks[key].done():
        return
    try:
        t = asyncio.ensure_future(_compute_and_store(geom, on))
    except RuntimeError:
        return
    _tasks[key] = t
    t.add_done_callback(lambda tt: tt.exception() if not tt.cancelled() else None)


async def warm_series(geom: BaseGeometry, on: date) -> tuple[int, S.Stats]:
    pts, stats = await compute_series(geom, on)
    k = geom_key(geom)
    _cache.set(("series", k, on.isoformat()), {"points": [p.model_dump(mode="json") for p in pts]}, FOREVER)
    _cache.set(("series_latest", k), {"on": on.isoformat()}, FOREVER)
    return len(pts), stats


def clear_cache() -> None:
    _cache.clear()
    _tasks.clear()


# ── A15: słowa dla rolnika zamiast NDVI / NDMI (progi – rules/satellite.yaml, jedno miejsce) ─────────

NDVI_WORD = {"gleba": "goła ziemia", "slaba": "słaba", "umiarkowana": "średnia", "gesta": "gęsta zieleń"}
NDMI_WORD = {"sucho": "niska", "srednio": "umiarkowana", "dobrze": "dobra"}


def plant_words(ndvi: float | None, ndmi: float | None, scene_date: date | None) -> tuple[str | None, str | None]:
    """(kondycja roślin, wilgotność roślin) słowami – te same progi co zdanie z satelity (describe)."""
    if ndvi is None or scene_date is None:
        return None, None
    c = cfg()
    kond = NDVI_WORD[classify(ndvi, c["ndvi"])[0]]
    if scene_date.month not in c["season_months"]:
        wilg = "poza sezonem"
    elif ndmi is None or ndvi < c["ndmi_min_ndvi"]:
        wilg = "nie oceniamy przy rzadkich roślinach"
    else:
        wilg = NDMI_WORD[classify(ndmi, c["ndmi"])[0]]
    return kond, wilg
