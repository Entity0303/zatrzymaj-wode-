"""Teren dla rolnika (A6): wynik analizy NMT (analysis/terrain.py) → sekcja `terrain` kontraktu, ocena stref
z glebą (rules/teren_gleba.yaml, D58), zdania prostym językiem, fakty do reguł rekomendacji (progi oczka D59)
i warstwy mapy /api/layers/teren i /api/layers/splyw (GeoJSON przycięty do działki, uproszczony).

Wejście = `facts` + `geojson` z `analyze_surface` (ten sam format co research/terrain/out/*.json – zapisane
wyniki osoby C działają tak samo jak świeże obliczenia).
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from app.core.format import num, plural, volume_m3
from app.schemas.analysis import (
    SourceTag,
    Terrain,
    TerrainDepression,
    TerrainDetails,
    TerrainOutlet,
    TerrainZone,
)

RULES_FILE = Path(__file__).parent / "rules" / "teren_gleba.yaml"
ZONE_ORDER = ("sucha_gorka", "stok", "plasko", "mokry_dolek")
FRONT_KIND = {"sucha_gorka": "gorka", "stok": "stok", "plasko": "plasko", "mokry_dolek": "dolek"}  # LayerData.tsx
SOURCE = "NMT GUGiK"
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

# ── progi oczka / zbiornika (D59) ───────────────────────────────────────────────────────────
POND_MAIN_MIN_DEPTH_M = 0.3  # zagłębienie wyraźne (3× precyzja NMT), nie szum
POND_MIN_CATCHMENT_M2 = 5000.0  # zlewnia ≥ 0,5 ha – inaczej z ulewy 20 mm spłynie ledwie kilkanaście m³
POND_MAIN_MIN_PARCEL_HA = 0.5  # na mniejszej działce oczko zajmie zbyt dużą część pola
POND_OPTION_MIN_PARCEL_HA = 0.3
SMALL_POND_MAX_M2 = 500.0  # A18: „małe oczko” tylko do 500 m², większe – „oczko”
WET_SPOT_MIN_AREA_M2 = 500.0  # mokradło / podmokły fragment – realne zagłębienie bez odpływu w działce
CULVERT_MIN_OUTLET_SHARE = 50.0  # zastawka: główny odpływ odprowadza ≥ 50% działki …
CULVERT_MIN_INFLOW_RATIO = 1.0  # … i na działkę spływa woda z co najmniej takiej samej powierzchni z zewnątrz


@lru_cache
def rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def soil_group(category: int | None) -> str:
    """Grupa z samej kategorii I–IV (gdy brak etykiety ważonej z analysis/soil_label.py)."""
    return {1: "lekka", 2: "lekka", 3: "srednia", 4: "ciezka"}.get(category, "nieznana")


def zones(facts: dict, group: str | None) -> list[TerrainZone]:
    r = rules()
    group = group if group in r["soil_groups"] else "nieznana"
    shares = facts.get("zone_share_pct") or {}
    out = []
    for key in ZONE_ORDER:
        share = float(shares.get(key) or 0.0)
        rating = sentence = None
        if share >= 1.0:
            rule = r["teren_gleba"][key][group]
            rating, sentence = rule["rating"], rule["sentence"].format(pct=round(share))
        out.append(TerrainZone(key=key, label=r["labels"][key], share_pct=round(share, 1), color=r["colors"][key],
                               rating=rating, sentence=sentence))
    return out


def _fmt(v: float, nd: int = 0) -> str:
    return num(v, nd)


def summary(facts: dict) -> str:
    """2–3 zdania bez żargonu: ukształtowanie, którędy ucieka woda (i skąd przychodzi), zagłębienia."""
    slope = facts.get("slope_mean_pct") or 0.0
    relief = facts.get("relief_m")
    shape_txt = ("prawie płaska" if slope < 2 else "lekko nachylona" if slope < 5 else "nachylona" if slope < 10
                 else "stroma")
    s1 = f"Działka jest {shape_txt}"
    if relief is not None:
        s1 += f" – różnica wysokości {_fmt(relief, 1)} m, średni spadek {_fmt(slope, 1)}%."
    else:
        s1 += "."
    parts = [s1]
    outs = facts.get("outlets") or []
    if facts.get("main_flow_direction") and outs:
        main = outs[0]
        share = round(main["share_of_parcel_pct"] or 0)
        if len(outs) == 1:
            tail = " – tędy odpływa woda z całej działki" if share >= 95 else f" ({share}% działki)"
            s2 = f"Woda spływa na {facts['main_flow_direction']} i opuszcza działkę w jednym miejscu{tail}"
        else:
            s2 = (f"Woda spływa na {facts['main_flow_direction']}; działkę opuszcza w {len(outs)} miejscach, "
                  f"najwięcej ({share}% działki) na {main['direction']}")
        ratio = facts.get("inflow_from_outside_ratio") or 0.0
        inflow = facts.get("inflow_from_outside_m2") or 0.0
        if ratio >= 1.0 and inflow > 0:
            s2 += f"; spływa tu też woda z ok. {_fmt(inflow / 10_000, 1)} ha pól i terenów powyżej"
        parts.append(s2 + ".")
    n = facts.get("n_depressions") or 0
    if n:
        d = facts.get("largest_depression") or {}
        vol = d.get("volume_m3")
        word = plural(n, "zagłębienie", "zagłębienia", "zagłębień")
        verb = plural(n, "jest", "są", "jest")
        parts.append(f"Na działce {verb} {n} {word} bez odpływu, gdzie zbiera się woda"
                     + (f" (największe zmieści ok. {volume_m3(vol)})." if vol else "."))
    else:  # o zagłębieniach bez odpływu mówimy tylko, gdy są (D66); obniżenia (strefa) – osobno
        wet = (facts.get("zone_share_pct") or {}).get("mokry_dolek") or 0.0
        if wet >= 5:
            parts.append(f"W obniżeniach ({round(wet)}% działki) zbiera się woda spływająca z wyższych miejsc.")
    return " ".join(parts)


def to_contract(facts: dict, group: str | None, data_date: dt.date | None = None,
                saved_note: str | None = None, soil_text: str | None = None) -> Terrain:
    r = rules()
    group = group if group in r["soil_groups"] else "nieznana"
    glabel = soil_text or r["soil_groups"][group]
    largest = facts.get("largest_depression")
    method = facts.get("method") or {}
    lim = list(facts.get("limitations") or [])
    if (facts.get("nmt_missing_pct") or 0) >= 1 and not any("uzupełnion" in x for x in lim):  # A23
        lim.append("Część wysokości uzupełniona z sąsiednich punktów (usługa NMT nie odesłała wszystkich) – "
                   "szczegóły rzeźby w tych miejscach są przybliżone.")
    if saved_note:
        lim.insert(0, saved_note)
    conf = facts.get("confidence") or "srednia"
    conf = {"średnia": "srednia", "niska": "ograniczona"}.get(conf, conf)
    if conf not in ("wysoka", "srednia", "ograniczona"):
        conf = "srednia"
    return Terrain(
        zones=zones(facts, group),
        zone_share_pct={k: float((facts.get("zone_share_pct") or {}).get(k) or 0.0) for k in ZONE_ORDER},
        soil_group=group, soil_group_label=glabel,
        summary=summary(facts),
        relief_m=facts.get("relief_m"), elev_min_m=facts.get("elev_min_m"), elev_max_m=facts.get("elev_max_m"),
        slope_mean_pct=facts.get("slope_mean_pct"), slope_max_pct=facts.get("slope_max_pct"),
        main_flow_direction=facts.get("main_flow_direction"),
        main_flow_direction_short=facts.get("main_flow_direction_short"),
        main_flow_azimuth_deg=facts.get("main_flow_azimuth_deg"),
        outlets=[TerrainOutlet(direction=o["direction"], direction_short=o["direction_short"],
                               azimuth_deg=o.get("azimuth_deg"), share_of_parcel_pct=o.get("share_of_parcel_pct") or 0.0,
                               location=o["location_lonlat"]) for o in facts.get("outlets") or []],
        inflow_from_outside_m2=facts.get("inflow_from_outside_m2"),
        inflow_from_outside_ratio=facts.get("inflow_from_outside_ratio"),
        depressions_count=int(facts.get("n_depressions") or 0),
        depressions_volume_m3=facts.get("depressions_total_volume_m3"),
        largest_depression=TerrainDepression(
            area_m2=largest.get("area_m2"), max_depth_m=largest.get("max_depth_m"), volume_m3=largest.get("volume_m3"),
            catchment_m2=largest.get("catchment_m2"), location=largest.get("location_lonlat")) if largest else None,
        details=TerrainDetails(
            grid_step_m=facts.get("grid_step_m") or 0.0, smoothing_sigma_m=facts.get("smoothing_sigma_m") or 0.0,
            nmt_points=facts.get("nmt_points"), nmt_missing_pct=facts.get("nmt_missing_pct"),
            twi_mean=facts.get("twi_mean"), twi_p90=facts.get("twi_p90"), steep_share_pct=facts.get("steep_share_pct"),
            flow_consistency=facts.get("flow_consistency"),
            method=", ".join(f"{k}: {v}" for k, v in method.items()) or "NMT GUGiK"),
        confidence=conf,
        limitations=lim,
        source_tag=SourceTag(kind="pomiar", date=data_date, source="NMT GUGiK (wysokości ±0,1 m) + obliczenia"),
    )


# ── fakty do reguł rekomendacji (analysis/rules/retencja.yaml, requires: [terrain]) ────────


def rule_facts(facts: dict | None, soil_category: int | None) -> dict[str, Any]:
    """Fakty `terrain_*` dla silnika reguł. Brak terenu → same None (warunki fałszywe)."""
    keys = ("terrain_pond", "pond_place_txt", "pond_lead_txt", "pond_noun", "pond_noun_cap", "pond_where_short",
            "pond_inflow_runoff_m3", "pond_area_m2", "pond_catchment_ha",
            "pond_depth_m", "outlet_direction", "outlet_share_pct", "inflow_ratio", "inflow_ha", "buffer_strip",
            "buffer_length_m", "steep_share_pct", "slope_max_pct", "wet_spot_area_m2", "wet_zone_pct",
            "culvert_candidate", "terrain_relief_m", "parcel_area_ha_terrain")
    v: dict[str, Any] = {k: None for k in keys}
    if not facts:
        return v
    area_ha = facts.get("parcel_area_ha") or 0.0
    v["parcel_area_ha_terrain"] = area_ha
    v["terrain_relief_m"] = facts.get("relief_m")
    v["slope_max_pct"] = facts.get("slope_max_pct")
    v["steep_share_pct"] = facts.get("steep_share_pct")
    v["wet_zone_pct"] = (facts.get("zone_share_pct") or {}).get("mokry_dolek")
    outs = facts.get("outlets") or []
    if outs:
        v["outlet_direction"] = outs[0]["direction"]
        v["outlet_share_pct"] = outs[0].get("share_of_parcel_pct")
    v["inflow_ratio"] = facts.get("inflow_from_outside_ratio")
    v["inflow_ha"] = round((facts.get("inflow_from_outside_m2") or 0.0) / 10_000, 1)
    v["culvert_candidate"] = bool(outs and (v["outlet_share_pct"] or 0) >= CULVERT_MIN_OUTLET_SHARE
                                  and (v["inflow_ratio"] or 0) >= CULVERT_MIN_INFLOW_RATIO)
    props = facts.get("proposals") or []
    pond = next((p for p in props if p["type"].startswith("oczko")), None)
    strip = next((p for p in props if p["type"] == "pas_buforowy"), None)
    v["buffer_strip"] = strip is not None
    v["buffer_length_m"] = strip.get("length_m") if strip else None
    if pond:
        catch = pond.get("catchment_m2") or 0.0
        in_dep = pond["type"] == "oczko_w_zaglebieniu"
        deep = (pond.get("max_depth_m") or 0.0) >= POND_MAIN_MIN_DEPTH_M
        if in_dep and deep and catch >= POND_MIN_CATCHMENT_M2 and area_ha >= POND_MAIN_MIN_PARCEL_HA:
            v["terrain_pond"] = "glowna"
        elif catch >= POND_MIN_CATCHMENT_M2 and area_ha >= POND_OPTION_MIN_PARCEL_HA:
            v["terrain_pond"] = "opcja"
        # A18: bez tautologii i bez sprzeczności „nie ma zagłębienia … w zagłębieniu”
        v["pond_place_txt"] = "w zagłębieniu bez odpływu" if in_dep else "przy miejscu, gdzie wypływa z działki"
        ha = num(round(catch / 10_000, 1))
        v["pond_lead_txt"] = (f"Woda z ok. {ha} ha spływa do płytkiego zagłębienia na działce." if in_dep else
                              f"Na działce nie ma zagłębienia bez odpływu, ale woda z ok. {ha} ha spływa do miejsca, "
                              "gdzie wypływa z działki.")
        v["pond_where_short"] = "w płytkim zagłębieniu" if in_dep else "przy odpływie"
        small = (pond.get("suggested_pond_area_m2") or 0.0) <= SMALL_POND_MAX_M2
        v["pond_noun"] = "małe oczko" if small else "oczko"
        v["pond_noun_cap"] = v["pond_noun"].capitalize()
        v["pond_inflow_runoff_m3"] = pond.get("inflow_runoff_m3")
        v["pond_area_m2"] = pond.get("suggested_pond_area_m2")
        v["pond_catchment_ha"] = round(catch / 10_000, 1)
        v["pond_depth_m"] = pond.get("max_depth_m")
    largest = facts.get("largest_depression") or {}
    if (largest.get("area_in_parcel_m2") or 0.0) >= WET_SPOT_MIN_AREA_M2:
        v["wet_spot_area_m2"] = largest.get("area_in_parcel_m2")
    return v


# ── warstwy mapy (GET /api/layers/teren, /api/layers/splyw) ─────────────────────────────────


def _clip_simplify(geom: dict, parcel: BaseGeometry | None, tol_deg: float) -> dict | None:
    g = shape(geom)
    if parcel is not None and g.geom_type in ("Polygon", "MultiPolygon", "LineString", "MultiLineString"):
        g = g.intersection(parcel)
    if g.is_empty:
        return None
    g = g.simplify(tol_deg, preserve_topology=True)
    return mapping(g) if not g.is_empty else None


def _round(obj):
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, (list, tuple)):
        return [_round(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    return obj


def layer_teren(geojson: dict, facts: dict, parcel_4326: BaseGeometry | None, soil_group_key: str | None = None) -> dict:
    """Strefy (poligony) przycięte do działki, z kolorem i etykietą (dymek: nazwa + udział; zdanie z oceną
    gleby – tylko gdy podano kategorię gleby, w panelu jest pełna ocena z `terrain.zones`)."""
    tol = max(0.5, (facts.get("grid_step_m") or 5.0) * 0.4) / 111_000  # ~0,4 kroku siatki
    zone_info = {z.key: z for z in zones(facts, soil_group_key)}
    feats = []
    for f in geojson.get("features", []):
        p = f["properties"]
        if p.get("layer") != "zone":
            continue
        z = zone_info.get(p.get("zone"))
        geom = _clip_simplify(f["geometry"], parcel_4326, tol)
        if z is None or geom is None:
            continue
        feats.append({"type": "Feature", "geometry": _round(geom), "properties": {
            "kind": FRONT_KIND[z.key], "zone": z.key, "color": z.color, "share_pct": z.share_pct,
            "rating": z.rating if soil_group_key else None,
            "label": f"{z.label} · {round(z.share_pct)}% działki" + (f" – {z.sentence}" if soil_group_key and z.sentence else "")}})
    return {"type": "FeatureCollection", "features": feats}


def layer_splyw(geojson: dict, facts: dict, parcel_4326: BaseGeometry | None) -> dict:
    """Ścieżki spływu (linie), odpływy (punkty z udziałem %), proponowane miejsca retencji (punkty/linie)."""
    tol = max(0.5, (facts.get("grid_step_m") or 5.0) * 0.4) / 111_000
    near = parcel_4326.buffer(15 / 111_000) if parcel_4326 is not None else None  # ścieżki tuż przy granicy też
    feats = []
    for f in geojson.get("features", []):
        p = f["properties"]
        layer = p.get("layer")
        if layer == "flow_path":
            geom = _clip_simplify(f["geometry"], near, tol)
            if geom:
                feats.append({"type": "Feature", "geometry": _round(geom), "properties": {
                    "kind": "flow", "color": "#2F7FC1", "label": "Kierunek spływu wody",
                    "upstream_m2": p.get("max_upstream_m2")}})
        elif layer == "outlet":
            feats.append({"type": "Feature", "geometry": _round(f["geometry"]), "properties": {
                "kind": "outflow", "color": "#E5675C", "share_pct": p.get("share_of_parcel_pct"),
                "direction": p.get("direction"),
                "label": f"Tu woda ucieka z działki – {round(p.get('share_of_parcel_pct') or 0)}% działki "
                         f"(kierunek: {p.get('direction')})"}})
        elif layer == "proposal":
            if p.get("type", "").startswith("oczko"):
                label = (f"Miejsce na oczko / zbiornik: z ulewy 20 mm spłynie tu ok. "
                         f"{round(p.get('inflow_runoff_m3') or 0)} m³ wody")
                kind = "retencja"
            else:
                label = f"Pas zieleni w poprzek stoku (ok. {round(p.get('length_m') or 0)} m)"
                kind = "pas_buforowy"
            feats.append({"type": "Feature", "geometry": _round(f["geometry"]), "properties": {
                "kind": kind, "color": "#2E5B3F", "proposal": p.get("type"), "label": label}})
        elif layer == "depression":
            geom = _clip_simplify(f["geometry"], parcel_4326, tol)
            if geom:
                feats.append({"type": "Feature", "geometry": _round(geom), "properties": {
                    "kind": "spot", "color": "#2F80C9", "volume_m3": p.get("volume_m3"),
                    "label": f"Tu zbiera się woda – zagłębienie ok. {round(p.get('volume_m3') or 0)} m³"}})
    return {"type": "FeatureCollection", "features": feats}
