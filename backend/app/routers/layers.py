"""GET /api/layers/{layer} – warstwy mapy przycięte do obrysu działki.

Kontrakt: app/schemas/layers.py. design/SPEC_UI.md 5.3–5.4.
- teren  – DZIAŁA (A6): strefy z NMT (górka / stok / płasko / dołek) jako poligony przycięte do działki,
- splyw  – DZIAŁA (A6): ścieżki spływu (linie), odpływy z udziałem % (punkty), miejsca retencji (punkty/linie),
           zagłębienia bez odpływu (poligony); rowy i cieki z BDOT10k – w przygotowaniu,
- kondycja / wilgotnosc (Sentinel-2), gleba (IUNG) – SZKIELET, HTTP 501.
Obiekty GeoJSON (EPSG:4326) mają `properties`: `kind`, `color`, `label` (dymek) – tak rysuje je frontend
(features/map/layers/LayerData.tsx). Geometrie uproszczone (~0,4 kroku siatki NMT). Teren z cache (D53).
"""

import asyncio
import datetime as dt

from fastapi import APIRouter, Query

from app.analysis import terrain_interpret
from app.analysis.terrain import terrain_for_parcel
from app.core.http import SourceError, http_error, not_implemented
from app.routers.parcel import resolve_parcel
from app.schemas.analysis import SourceTag
from app.schemas.layers import LayerKey, LayerResponse, PointValue

router = APIRouter(prefix="/api/layers", tags=["warstwy"])
TERRAIN_LIMIT_S = 20.0


@router.get("/{layer}", response_model=LayerResponse, responses={501: {"description": "W budowie"},
                                                                  502: {"description": "Brak działki / NMT"}})
async def get_layer(layer: LayerKey, parcel_id: str = Query(), date: dt.date | None = None) -> LayerResponse:
    """Warstwa „teren” albo „spływ” dla działki (NMT GUGiK, z cache). Pozostałe warstwy – 501 „w budowie”."""
    if layer not in ("teren", "splyw"):
        raise not_implemented(f"Warstwa „{layer}”")
    try:
        p = await resolve_parcel(parcel_id, None, None)
        res = await asyncio.wait_for(terrain_for_parcel(p.geom_2180, p.id), TERRAIN_LIMIT_S)
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


@router.get("/{layer}/point", response_model=PointValue, responses={501: {"description": "W budowie"}})
async def get_layer_point(layer: LayerKey, lon: float, lat: float, date: dt.date | None = None) -> PointValue:
    raise not_implemented(f"Wartość warstwy „{layer}” w punkcie")
