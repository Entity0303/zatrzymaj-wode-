"""KONTRAKT: GET /api/search?q= – podpowiedzi pod wyszukiwarką (działki i miejscowości), A5c.

Lista wyników (max 10), każdy z `kind`: `parcel` (działka – identyfikator TERYT albo „obręb + numer”) albo `place`
(miejscowość – sama nazwa). Brak wyników = HTTP 200 + pusta lista + `hint` (nie 404).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


SearchKind = Literal["parcel", "place", "address"]  # A9: address – adres punktowy (PRG / OSM)
PlaceType = Literal["miejscowosc", "gmina", "obreb"]
QueryInterpretation = Literal["parcel_id", "obreb_numer", "name", "empty", "unrecognized"]


class SearchResult(_Contract):
    kind: SearchKind
    id: str = Field(description="parcel: identyfikator ULDK (jak parcel_id); place: id źródła, np. 'prng:139268'")
    label: str = Field(description="Gotowy tekst do listy, np. 'Tczów, gm. Tczów, pow. zwoleński, mazowieckie'")
    name: str = Field(description="parcel: 'obręb numer', np. 'Wnory-Wandy 6/1'; place: nazwa miejscowości")
    lon: float = Field(description="Środek (WGS84) – do przybliżenia mapy; parcel: punkt wewnątrz działki")
    lat: float
    parcel_id: str | None = Field(None, description="Tylko kind = parcel – do GET /api/analysis?parcel_id=")
    type: PlaceType | None = Field(None, description="Tylko kind = place")
    type_label: str | None = Field(None, description="Np. 'wieś', 'miasto', 'osada', 'gmina'")
    gmina: str | None = None
    powiat: str | None = None
    wojewodztwo: str | None = None
    bbox: tuple[float, float, float, float] | None = Field(
        None, description="lon_min, lat_min, lon_max, lat_max (EPSG:4326) – do fitBounds; parcel: obrys działki")
    bbox_approx: bool = Field(False, description="true = bbox wyznaczony wokół punktu (źródło podało tylko punkt)")
    area_ha: float | None = Field(None, description="Tylko kind = parcel – z geometrii")
    locality: str | None = Field(None, description="A9 – tylko address: miejscowość")
    street: str | None = Field(None, description="A9 – tylko address: ulica (null na wsi bez ulic)")
    house_number: str | None = Field(None, description="A9 – tylko address: numer domu")
    source: str = Field(description="Skąd wynik: 'ULDK GUGiK', 'PRNG GUGiK', 'OpenStreetMap Nominatim', 'słownik demo'; "
                                    "address: 'prg' | 'osm'")


class SearchResponse(_Contract):
    query: str
    interpreted_as: QueryInterpretation = Field(description="Jak rozpoznano zapytanie")
    results: list[SearchResult]
    total: int = Field(description="Ile wyników pasuje (lista jest przycięta do 10)")
    truncated: bool = Field(description="true = jest więcej wyników niż pokazano (albo źródło przycięło listę)")
    hint: str | None = Field(None, description="Podpowiedź dla rolnika (brak wyników, za dużo wyników)")
    notices: list[str] = Field(default_factory=list, description="Czego nie udało się sprawdzić (źródło niedostępne)")
    attribution: str | None = Field(None, description="Atrybucja źródła, gdy wymagana (OSM)")
