"""Woda w okolicy działki (A9, D92): cieki, rowy, kanały i zbiorniki w promieniu 500 m (OSM Overpass) + najbliższy
wodowskaz IMGW ze stanem niski / średni / wysoki. Liczone w tle (jak teren i satelita) – Overpass bywa wolny.

`toward_outflow`: obiekt leży tam, dokąd woda odpływa z działki (główne miejsce odpływu z analizy terenu): najbliższy
punkt obiektu ≤ 150 m od miejsca odpływu albo w kierunku odpływu (±60°) – wtedy zastawka na rowie ma sens.
BDOT10k (rowy z mapy topograficznej) jest zablokowany z tej sieci, MPHP Wód Polskich wymaga autoryzacji (401) – D92.
"""

from __future__ import annotations

import asyncio
import math
from datetime import date, timedelta

from shapely.geometry import LineString, Point, Polygon, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union

from app.core.cache import offline
from app.core.geo import to_2180, to_wgs84
from app.core.http import SourceError
from app.schemas.analysis import Hydro, HydroFeature, HydroGauge, HydroSource
from app.sources import imgw_hydro, overpass

RADIUS_M = 500.0
MAX_FEATURES = 8
KIND_LABEL = {"rzeka": "Rzeka", "ciek": "Ciek", "row": "Rów melioracyjny", "kanal": "Kanał", "zbiornik": "Zbiornik wodny"}
KIND_COLOR = {"rzeka": "#1F5FA0", "ciek": "#2F80C9", "row": "#4FA3EC", "kanal": "#2F80C9", "zbiornik": "#7FB8E6"}
WATERWAY = {"river": "rzeka", "stream": "ciek", "canal": "kanal", "ditch": "row", "drain": "row"}
STATE_LABEL = {"niski": "stan niski", "sredni": "stan średni", "wysoki": "stan wysoki"}
SOURCES = [HydroSource(name="OpenStreetMap (Overpass API) – © autorzy OpenStreetMap, ODbL", url=overpass.SOURCE_URL),
           HydroSource(name="IMGW-PIB – stany wód (dane publiczne)", url="https://danepubliczne.imgw.pl")]


def search_bbox(parcel_4326: BaseGeometry) -> tuple[float, float, float, float]:
    g = to_wgs84(to_2180(parcel_4326).buffer(RADIUS_M))  # P1: obrys + 500 m, nie więcej
    return tuple(round(v, 4) for v in g.bounds)  # type: ignore[return-value]


# ── obiekty z OSM ──────────────────────────────────────────────────────────────────────────


def _kind(tags: dict) -> str | None:
    if tags.get("waterway") in WATERWAY:
        return WATERWAY[tags["waterway"]]
    if tags.get("natural") == "water" or tags.get("water") or tags.get("landuse") == "reservoir":  # P1: water=*, zbiornik
        return "rzeka" if tags.get("water") in ("river", "canal", "stream") else "zbiornik"
    return None


def _geom(el: dict) -> BaseGeometry | None:
    """Element Overpass (`out geom`) → geometria EPSG:4326 (linia, wielokąt; relacja – z zewnętrznych członów)."""
    def line(pts):
        return [(p["lon"], p["lat"]) for p in pts or [] if "lon" in p and "lat" in p]

    if el.get("type") == "way":
        c = line(el.get("geometry"))
        if len(c) < 2:
            return None
        if _kind(el.get("tags", {})) == "zbiornik" and len(c) >= 4 and c[0] == c[-1]:
            poly = Polygon(c)
            return poly if poly.is_valid else poly.buffer(0)
        return LineString(c)
    if el.get("type") == "relation":
        parts = [LineString(line(m.get("geometry"))) for m in el.get("members", [])
                 if m.get("role") in ("outer", "") and len(line(m.get("geometry"))) >= 2]
        if not parts:
            return None
        polys = [Polygon(p.coords) for p in parts if p.is_ring and len(p.coords) >= 4]
        return unary_union(polys) if polys else unary_union(parts)
    return None


def _azimuth(dx: float, dy: float) -> float:
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def _toward(nearest_2180: Point, outlets: list) -> bool:
    if not outlets:
        return False
    main = max(outlets, key=lambda o: o.share_of_parcel_pct or 0)
    o = to_2180(Point(*main.location))
    d = o.distance(nearest_2180)
    if d <= 150:
        return True
    if main.azimuth_deg is None:
        return False
    diff = abs((_azimuth(nearest_2180.x - o.x, nearest_2180.y - o.y) - main.azimuth_deg + 180) % 360 - 180)
    return diff <= 60 and d <= RADIUS_M


def objects(elements: list, parcel_4326: BaseGeometry, outlets: list) -> list[tuple[HydroFeature, BaseGeometry]]:
    """Obiekty ≤ 500 m od działki – (cecha kontraktu, geometria 4326 przycięta do promienia); nazwane odcinki tej
    samej rzeki / cieku łączone, najbliższe najpierw, maks. 8."""
    parcel = to_2180(parcel_4326)
    zone = parcel.buffer(RADIUS_M)
    groups: dict[tuple, list[BaseGeometry]] = {}
    for el in elements or []:
        tags = el.get("tags") or {}
        kind = _kind(tags)
        g = _geom(el) if kind else None
        if g is None or g.is_empty:
            continue
        g2 = to_2180(g)
        if not g2.intersects(zone):
            continue
        name = tags.get("name")
        key = (kind, name) if name else (kind, f"{el.get('type')}/{el.get('id')}")
        groups.setdefault(key, []).append(g2)
    out = []
    for (kind, name_or_id), geoms in groups.items():
        g2 = unary_union(geoms)
        dist = parcel.distance(g2)
        if dist > RADIUS_M:
            continue
        near = nearest_points(parcel, g2)[1]  # najbliższy punkt obiektu względem działki
        name = None if str(name_or_id).startswith(("way/", "relation/")) else name_or_id
        feat = HydroFeature(kind=kind, name=name, distance_m=round(dist), toward_outflow=_toward(near, outlets))
        out.append((feat, to_wgs84(g2.intersection(zone))))
    out.sort(key=lambda x: (x[0].distance_m, x[0].kind != "row"))
    return out[:MAX_FEATURES]


# ── zdanie ──────────────────────────────────────────────────────────────────────────────────


def _dist_txt(m: float) -> str:
    return "przy samej działce" if m <= 5 else f"{int(round(m))} m od działki"


def sentence(feats: list[HydroFeature], gauge: HydroGauge | None) -> str:
    parts = []
    if feats:
        f = feats[0]
        label = KIND_LABEL[f.kind] + (f" {f.name}" if f.name and f.kind in ("rzeka", "ciek", "kanal") else "")
        s = f"{label} {_dist_txt(f.distance_m)}"
        if f.toward_outflow and f.kind in ("row", "kanal", "ciek"):
            s += ", w kierunku odpływu wody – zastawka może zatrzymać wodę."
        elif f.toward_outflow:
            s += ", w kierunku odpływu wody."
        else:
            s += "."
        parts.append(s)
        ditch = next((x for x in feats[1:] if x.kind in ("row", "kanal") and x.toward_outflow), None)
        if ditch and not f.toward_outflow:
            parts.append(f"Rów melioracyjny {_dist_txt(ditch.distance_m)} w kierunku odpływu – zastawka może zatrzymać "
                         "wodę.")
    else:
        parts.append("W promieniu 500 m od działki nie ma cieków, rowów ani zbiorników (wg OpenStreetMap – małe rowy "
                     "mogą nie być zaznaczone).")
    if gauge:
        parts.append(f"Najbliższy wodowskaz: {gauge.river} – {gauge.name} ({gauge.distance_km:.0f} km) – "
                     f"{STATE_LABEL[gauge.state]}.")
    return " ".join(parts)


# ── wynik ───────────────────────────────────────────────────────────────────────────────────


def _gauge(gs: list | None, parcel_4326: BaseGeometry, on: date) -> HydroGauge | None:
    if not gs or on < date.today() - timedelta(days=1):
        return None  # data historyczna – bieżący stan nie dotyczy (archiwum stanów – tylko percentyle)
    c = parcel_4326.centroid
    hit = imgw_hydro.nearest(gs, c.x, c.y, on.month)
    if hit is None:
        return None
    g, d, st = hit
    return HydroGauge(name=g.name, river=g.river, distance_km=round(d, 1), level_cm=g.level_cm, state=st,
                      date=g.date or on.isoformat())


def build(elements: list, gs: list | None, parcel_4326: BaseGeometry, outlets: list, on: date) -> tuple[Hydro, list]:
    objs = objects(elements, parcel_4326, outlets)
    feats = [f for f, _ in objs]
    gauge = _gauge(gs, parcel_4326, on)
    hydro = Hydro(status="ok" if feats else "none", sentence=sentence(feats, gauge), features=feats, gauge=gauge,
                  sources=SOURCES)
    return hydro, objs


def cached(parcel_4326: BaseGeometry, outlets: list, on: date) -> Hydro | None:
    """Bez sieci: obiekty z cache Overpass (+ wodowskaz z cache IMGW). None = jeszcze nie pobrano (pending)."""
    els = overpass.cached_elements(search_bbox(parcel_4326))
    if els is None:
        return None
    gs = imgw_hydro.cached()
    return build(els, gs, parcel_4326, outlets, on)[0]


_tasks: dict[tuple, asyncio.Task] = {}


async def fetch(parcel_4326: BaseGeometry) -> tuple[list, list | None]:
    els, gs = await asyncio.gather(overpass.water_elements(search_bbox(parcel_4326)), imgw_hydro.gauges(),
                                   return_exceptions=True)
    if isinstance(els, BaseException):
        raise els if isinstance(els, SourceError) else SourceError(overpass.SOURCE, "błąd pobierania")
    return els, None if isinstance(gs, BaseException) else gs


async def live(parcel_4326: BaseGeometry, outlets: list, on: date) -> tuple[Hydro, list]:
    key = search_bbox(parcel_4326)
    task = _tasks.get(key)
    if task is None or task.done():
        task = asyncio.ensure_future(fetch(parcel_4326))
        _tasks[key] = task
    try:
        els, gs = await asyncio.shield(task)
    finally:
        if task.done():
            _tasks.pop(key, None)
    return build(els, gs, parcel_4326, outlets, on)


def start_background(parcel_4326: BaseGeometry) -> None:
    from app.core.config import settings

    if not settings.hydro_background or offline(overpass.SOURCE):
        return
    key = search_bbox(parcel_4326)
    if key in _tasks and not _tasks[key].done():
        return
    try:
        t = asyncio.ensure_future(fetch(parcel_4326))
    except RuntimeError:
        return
    _tasks[key] = t
    t.add_done_callback(lambda tt: tt.exception() if not tt.cancelled() else None)


def pending() -> Hydro:
    return Hydro(status="pending", sentence="Sprawdzam rowy, cieki i zbiorniki w okolicy…", features=[], gauge=None,
                 sources=SOURCES)


def layer(objs: list) -> dict:
    """GeoJSON warstwy „woda” (LineString / Polygon, properties: kind, color, label) – przycięty do promienia 500 m."""
    feats = []
    for f, g in objs:
        label = KIND_LABEL[f.kind] + (f" {f.name}" if f.name else "") + " · " + _dist_txt(f.distance_m)
        for part in getattr(g, "geoms", [g]):
            if part.is_empty or part.geom_type not in ("LineString", "Polygon"):
                continue
            feats.append({"type": "Feature", "geometry": mapping(part),
                          "properties": {"kind": f.kind, "color": KIND_COLOR[f.kind], "label": label,
                                         "toward_outflow": f.toward_outflow}})
    return {"type": "FeatureCollection", "features": feats}


def rule_facts(h: Hydro | None) -> dict:
    """Fakty dla reguł: stan rowu (brak / jest / w_kierunku_odplywu / nieznany) i pewność rekomendacji zastawki."""
    if h is None or h.status == "pending":
        return {"hydro_ditch_state": "nieznany", "hydro_zastawka_conf": "ograniczona",
                "hydro_ditch_txt": "Rowów w okolicy jeszcze nie sprawdziliśmy – zobacz na miejscu, czy rów jest."}
    ditches = [f for f in h.features or [] if f.kind in ("row", "kanal")]
    if not ditches:
        return {"hydro_ditch_state": "brak", "hydro_zastawka_conf": "ograniczona", "hydro_ditch_txt": ""}
    toward = next((f for f in ditches if f.toward_outflow), None)
    f = toward or ditches[0]
    txt = (f"{KIND_LABEL[f.kind]} {_dist_txt(f.distance_m)}" + (", w kierunku odpływu wody (OpenStreetMap)." if toward
                                                                 else " (OpenStreetMap)."))
    return {"hydro_ditch_state": "w_kierunku_odplywu" if toward else "jest",
            "hydro_zastawka_conf": "wysoka" if toward else "srednia", "hydro_ditch_txt": txt}


def clear() -> None:
    _tasks.clear()
