"""Kontrakt API: warstwy mapy przycięte do obrysu działki (GET /api/layers/{layer}).
„teren” i „splyw” działają od A6 (NMT); pozostałe – szkielet (501). Przykłady: frontend/src/mocks/layers.*.sample.json.

design/SPEC_UI.md 5.3: Kondycja upraw (NDVI), Wilgotność roślin (NDMI), Teren (NMT),
Spływ wody (NMT + BDOT10k), Gleba (IUNG). Odpowiednik TS: frontend/src/api/types.ts.

Obiekty (GeoJSON, EPSG:4326) – `properties` (A6, uzgodnione z LayerData.tsx B):
- `kind`: teren – gorka | stok | plasko | dolek; spływ – flow (linia) | outflow (punkt, „tu woda ucieka”) |
  retencja (punkt, miejsce na oczko) | pas_buforowy (linia) | spot (poligon, zagłębienie bez odpływu),
- `color` (hex), `label` (dymek), dodatkowo: teren – `zone`, `share_pct`; odpływ – `share_pct`, `direction`.
"""

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.analysis import SourceTag

LayerKey = Literal["kondycja", "wilgotnosc", "teren", "splyw", "gleba"]


class RasterOverlay(BaseModel):
    """Obraz PNG (przezroczysty poza obrysem) nakładany na mapę w granicach bbox."""

    image_url: str
    bbox: tuple[float, float, float, float] = Field(description="lon_min, lat_min, lon_max, lat_max (EPSG:4326)")


class LayerResponse(BaseModel):
    parcel_id: str
    layer: LayerKey
    analysis_date: dt.date
    raster: RasterOverlay | None = None
    features: dict[str, Any] | None = Field(None, description="GeoJSON FeatureCollection (strefy terenu, ścieżki spływu, "
                                            "odpływy, miejsca retencji); properties: kind, color, label")
    value_range: tuple[float, float] | None = Field(None, description="Krańce legendy, np. wysokości 134,7–148,0 m")
    source_tag: SourceTag


class PointValue(BaseModel):
    """Dymek po kliknięciu wewnątrz działki (SPEC 5.4)."""

    layer: LayerKey
    text: str = Field(description="Np. 'Kondycja: słaba (0,31) · zdjęcie 12.06.2026'")
    value: float | None
    source_tag: SourceTag
