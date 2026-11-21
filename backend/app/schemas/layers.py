"""Kontrakt API: warstwy mapy przycięte do obrysu działki (GET /api/layers/{layer}) – SZKIELET.

design/SPEC_UI.md 5.3: Kondycja upraw (NDVI), Wilgotność roślin (NDMI), Teren (NMT),
Spływ wody (NMT + BDOT10k), Gleba (IUNG). Odpowiednik TS: frontend/src/api/types.ts.

TODO (osoba A): ustalić z osobą B format rastra (PNG + bbox) i obiektów (GeoJSON).
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
    features: dict[str, Any] | None = Field(None, description="GeoJSON FeatureCollection (strzałki spływu, rowy, strefy)")
    value_range: tuple[float, float] | None = Field(None, description="Krańce legendy, np. wysokości 134,7–148,0 m")
    source_tag: SourceTag


class PointValue(BaseModel):
    """Dymek po kliknięciu wewnątrz działki (SPEC 5.4)."""

    layer: LayerKey
    text: str = Field(description="Np. 'Kondycja: słaba (0,31) · zdjęcie 12.06.2026'")
    value: float | None
    source_tag: SourceTag
