"""GET /api/layers/{layer} – warstwy mapy przycięte do obrysu działki (SZKIELET, HTTP 501).

Kontrakt: app/schemas/layers.py. design/SPEC_UI.md 5.3–5.4.

TODO (osoba A):
- kondycja / wilgotnosc: Sentinel-2 NDVI/NDMI (sources.sentinel), zdjęcie najbliższe dacie analizy
- teren / splyw: NMT (sources.nmt, analysis.terrain), rowy i cieki (sources.bdot)
- gleba: IUNG (sources.iung)
- GET /api/layers/{layer}/point?lon=&lat= – wartość w punkcie do dymka
"""

import datetime as dt

from fastapi import APIRouter, Query

from app.core.http import not_implemented
from app.schemas.layers import LayerKey, LayerResponse, PointValue

router = APIRouter(prefix="/api/layers", tags=["warstwy"])


@router.get("/{layer}", response_model=LayerResponse, responses={501: {"description": "W budowie"}})
async def get_layer(layer: LayerKey, parcel_id: str = Query(), date: dt.date | None = None) -> LayerResponse:
    raise not_implemented(f"Warstwa „{layer}”")


@router.get("/{layer}/point", response_model=PointValue, responses={501: {"description": "W budowie"}})
async def get_layer_point(layer: LayerKey, lon: float, lat: float, date: dt.date | None = None) -> PointValue:
    raise not_implemented(f"Wartość warstwy „{layer}” w punkcie")
