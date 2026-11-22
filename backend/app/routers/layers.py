"""GET /api/layers/{layer} – warstwy mapy przycięte do obrysu działki.

Kontrakt: app/schemas/layers.py. design/SPEC_UI.md 5.3–5.4.
- teren  – DZIAŁA (A6): strefy z NMT (górka / stok / płasko / dołek) jako poligony przycięte do działki,
- splyw  – DZIAŁA (A6): ścieżki spływu (linie), odpływy z udziałem % (punkty), miejsca retencji (punkty/linie),
           zagłębienia bez odpływu (poligony); rowy i cieki z BDOT10k – w przygotowaniu,
- kondycja / wilgotnosc – DZIAŁA (A11): NDVI / NDMI z ostatniej czystej sceny Sentinel-2 jako mały PNG (data URI,
  piksel 10 m, przezroczysty poza obrysem, chmury białe) + bbox EPSG:4326 + legenda; z cache albo liczone na żywo,
- gleba (IUNG) – SZKIELET, HTTP 501.
Obiekty GeoJSON (EPSG:4326) mają `properties`: `kind`, `color`, `label` (dymek) – tak rysuje je frontend
(features/map/layers/LayerData.tsx). Geometrie uproszczone (~0,4 kroku siatki NMT). Teren z cache (D53).
"""

import asyncio
import datetime as dt

from fastapi import APIRouter, Query

from app.analysis import terrain_interpret
from app.analysis import terrain as terrain_mod
from app.core.http import SourceError, http_error, not_implemented
from app.routers.parcel import resolve_parcel
from app.schemas.analysis import AnalysisRequest, SourceTag
from app.schemas.layers import LayerKey, LayerResponse, LegendStop, PointValue, RasterOverlay

router = APIRouter(prefix="/api/layers", tags=["warstwy"])
TERRAIN_LIMIT_S = 30.0  # A9: teren liczony na żywo (gdy analiza zwróciła pending) – do ok. 20 s


@router.get("/{layer}", response_model=LayerResponse, responses={501: {"description": "W budowie"},
                                                                  502: {"description": "Brak działki / NMT"}})
async def get_layer(layer: LayerKey, parcel_id: str = Query(), date: dt.date | None = None) -> LayerResponse:
    """Warstwy: teren, spływ (NMT GUGiK, z cache), kondycja (NDVI) i wilgotność roślin (NDMI) – Sentinel-2.
    Gleba – 501 „w budowie”."""
    if layer in ("kondycja", "wilgotnosc"):
        return await satellite_layer(layer, parcel_id, date)
    if layer == "woda":
        return await water_layer(parcel_id, date)
    if layer not in ("teren", "splyw"):
        raise not_implemented(f"Warstwa „{layer}”")
    try:
        p = await resolve_parcel(parcel_id, None, None)
        res = await asyncio.wait_for(terrain_mod.live(p.geom_2180, p.id), TERRAIN_LIMIT_S)  # A9: wspólne zadanie
    except SourceError as exc:
        raise http_error(exc) from exc
    except asyncio.TimeoutError as exc:
        raise http_error(SourceError("NMT GUGiK", f"brak odpowiedzi w {TERRAIN_LIMIT_S:.0f} s")) from exc
    parcel_4326 = p.geom_4326
    saved = res.facts.get("saved_note")
    if layer == "teren":
        features = terrain_interpret.layer_teren(res.geojson, res.facts, parcel_4326)
        lo, hi = res.facts.get("elev_min_m"), res.facts.get("elev_max_m")
        value_range = (lo, hi) if lo is not None and hi is not None else None
    else:
        features = terrain_interpret.layer_splyw(res.geojson, res.facts, parcel_4326)
        value_range = None
    return LayerResponse(
        parcel_id=p.id, layer=layer, analysis_date=date or dt.date.today(), features=features,
        value_range=value_range,
        source_tag=SourceTag(kind="pomiar", date=None if saved else dt.date.today(),
                             source="NMT GUGiK" + (" (zapisany wynik z 21.11.2026)" if saved else "")),
    )


async def water_layer(parcel_id: str, date: dt.date | None) -> LayerResponse:
    """A9: cieki, rowy, kanały, zbiorniki ≤ 500 m od działki (OSM) – GeoJSON przycięty do promienia."""
    from app.analysis import hydro as hydro_mod
    from app.routers.hydro import hydro_for

    try:
        p = await resolve_parcel(parcel_id, None, None)
    except SourceError as exc:
        raise http_error(exc) from exc
    on = date or dt.date.today()
    _hydro, objs = await hydro_for(p, on)
    legend = [LegendStop(value=i, color=hydro_mod.KIND_COLOR[k], label=hydro_mod.KIND_LABEL[k])
              for i, k in enumerate(("rzeka", "ciek", "row", "kanal", "zbiornik"))]
    return LayerResponse(parcel_id=p.id, layer="woda", analysis_date=on, features=hydro_mod.layer(objs), legend=legend,
                         legend_title="Woda w okolicy (500 m)", note="© autorzy OpenStreetMap (ODbL)",
                         source_tag=SourceTag(kind="pomiar", date=on, source="OpenStreetMap (Overpass API)"))


SAT_LEGEND = {"kondycja": ("NDVI – kondycja roślin", (0.0, 0.9)), "wilgotnosc": ("NDMI – wilgotność roślin", (-0.4, 0.4))}


@router.post("/{layer}", response_model=LayerResponse, responses={404: {"description": "Brak zdjęcia"}})
async def post_layer(layer: LayerKey, req: AnalysisRequest) -> LayerResponse:
    """A9: warstwy satelitarne dla pola narysowanego – treść `{geometry, date}` (albo parcel_id / lon+lat)."""
    from app.routers.satellite import resolve_any

    if layer not in ("kondycja", "wilgotnosc"):
        raise not_implemented(f"Warstwa „{layer}” (POST)")
    p = await resolve_any(req.parcel_id, req.lon, req.lat, req.geometry)
    return await satellite_layer(layer, p.id, req.date, parcel=p)


async def satellite_layer(layer: str, parcel_id: str, date: dt.date | None, parcel=None) -> LayerResponse:
    """Kondycja upraw (NDVI) / Wilgotność roślin (NDMI): PNG z ostatniej czystej sceny (A11). Brak sceny → 404
    (frontend: „warstwa niedostępna”), nie 5xx."""
    from fastapi import HTTPException

    from app.analysis import satellite as satellite_mod

    try:
        p = parcel or await resolve_parcel(parcel_id, None, None)
    except SourceError as exc:
        raise http_error(exc) from exc
    on = date or dt.date.today()
    sat = await satellite_mod.live(p.geom_4326, on)
    lay = satellite_mod.cached_layers(p.geom_4326, on)
    if sat.status != "ok" or not lay:
        raise HTTPException(status_code=404, detail={"source": "Sentinel-2 L2A", "message": sat.warning
                                                     or "Brak bezchmurnego zdjęcia satelitarnego działki."})
    c = satellite_mod.cfg()["colors"][layer]
    title, rng = SAT_LEGEND[layer]
    value = sat.ndvi if layer == "kondycja" else sat.ndmi
    return LayerResponse(
        parcel_id=p.id, layer=layer, analysis_date=on,
        raster=RasterOverlay(image_url="data:image/png;base64," + lay[layer], bbox=tuple(lay["bbox"])),
        value_range=rng, legend=[LegendStop(value=v, color=col) for v, col in c["stops"]], legend_title=title,
        legend_left=c["left"], legend_right=c["right"], value=value, scene_date=sat.date,
        note=(f"{title}: mediana {value:.2f} · zdjęcie z {sat.date:%d.%m.%Y}" if value is not None else None),
        source_tag=SourceTag(kind="pomiar", date=sat.date, source="Sentinel-2 L2A (Earth Search)"),
    )


@router.get("/{layer}/point", response_model=PointValue, responses={501: {"description": "W budowie"}})
async def get_layer_point(layer: LayerKey, lon: float, lat: float, date: dt.date | None = None) -> PointValue:
    raise not_implemented(f"Wartość warstwy „{layer}” w punkcie")
