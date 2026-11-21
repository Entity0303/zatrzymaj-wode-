"""Kontrakt API: działka ewidencyjna (GET /api/parcel).

Odpowiednik TypeScript: frontend/src/api/types.ts (Parcel, DataSource, ParcelCandidates).
Zmiany tylko po uzgodnieniu i w obu miejscach naraz (CLAUDE.md – Praca zespołowa).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class DataSource(BaseModel):
    """Źródło danych przy wyniku (CLAUDE.md: źródło, data danych, ograniczenia)."""

    nazwa: str
    url: str
    pobrano: str | None = Field(None, description="Kiedy pobrano dane (ISO 8601)")
    uwagi: str | None = None


class Parcel(BaseModel):
    id: str = Field(description="Pełny identyfikator ULDK, np. 143203_2.0027.112/11")
    wojewodztwo: str
    powiat: str
    gmina: str
    obreb: str
    numer: str
    teryt_gminy: str
    powierzchnia_ha: float = Field(description="Z geometrii w EPSG:2180, nie z ewidencji")
    geometria: dict[str, Any] = Field(description="GeoJSON Polygon/MultiPolygon w EPSG:4326")
    zrodlo: DataSource
    source: Literal["uldk", "drawn", "approximate"] = Field(
        "uldk", description="uldk – działka z ewidencji (ULDK); drawn – pole narysowane przez rolnika; "
                            "approximate – obszar 1 ha wokół punktu (brak granic z ULDK)")
    name: str | None = Field(None, description="Nazwa pola, gdy nie jest działką ewidencyjną, np. 'Pole narysowane przez rolnika'")


class ParcelCandidates(BaseModel):
    """Treść `detail` przy HTTP 409 – kilka działek o tym numerze."""

    message: str
    total: int
    candidates: list[Parcel]


class ErrorDetail(BaseModel):
    """Treść `detail` przy HTTP 404 / 502."""

    source: str | None = None
    message: str
