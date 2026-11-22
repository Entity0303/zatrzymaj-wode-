"""Kontrakt GET / POST /api/groundwater (A27) – „Wody gruntowe i zapas z opadów”."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InfiltrationLevel = Literal["dobre", "slabe", "bardzo_slabe"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Infiltration(_M):
    """Ile opadu zostaje w glebie dla roślin – liczone z naszych danych (nie szybkość przesiąkania). A27c: nazwa pola
    `infiltration` została, rolnik widzi „Ile opadu zostaje w glebie: dużo / mało / bardzo mało”."""

    level: InfiltrationLevel
    label_pl: str = Field(description="Ile opadu zostaje w glebie: dużo / mało / bardzo mało")
    sentence_pl: str = Field(description="Jedno zdanie dla rolnika")
    short_pl: str = Field(description="Krótka forma do raportu: 'Z opadów zostaje w glebie … (… mm opadu w 30 dni przy … mm parowania).'")
    precip_30d_mm: float
    et0_30d_mm: float
    precip_60d_mm: float | None = None
    et0_60d_mm: float | None = None
    soil_code: int | None = Field(None, description="Kategoria gleby IUNG: 1–4 = kat. I–IV, 5 = organiczna; null = brak")
    slope_mean_pct: float | None = Field(None, description="Średni spadek terenu w obrysie, % – null, gdy teren nie jest policzony")
    index: float = Field(description="Wskaźnik 0–1,5: (opad / parowanie) × część zatrzymana przez glebę × poprawka na spadek")
    data_until: dt.date = Field(description="Ostatni dzień danych pogodowych (przed datą analizy)")


class FloodZone(_M):
    in_zone: bool = Field(description="Czy środek działki leży na obszarze zagrożonym podtopieniami (PIG-PIB, MOZP)")
    label_pl: str
    water_region: str | None = None


class SourcePig(_M):
    unavailable: bool = False
    note_pl: str | None = Field(None, description="'usługa PIG niedostępna' albo nota o brakującej głębokości")
    depth_available: bool = Field(False, description="Głębokość do zwierciadła – dziś zawsze false (brak usługi punktowej)")


class GroundwaterContext(_M):
    """`unavailable = true` – nie udało się policzyć zapasu z opadów ani sprawdzić PIG-PIB (reszta pól pusta)."""

    unavailable: bool = False
    note_pl: str | None = None
    infiltration: Infiltration | None = None
    flood_zone: FloodZone | None = None
    depth_m: float | None = Field(None, description="Głębokość do pierwszego zwierciadła, m – dziś zawsze null (nie zgadujemy)")
    source_pig: SourcePig = SourcePig()
    flood_after_rain: bool = Field(False, description="Obszar podtopień + mokre obniżenia na działce → ryzyko podtopień po ulewie")
    may_reduce_drought: bool = Field(False, description="Płytka woda gruntowa może zasilać korzenie – susza może być mniejsza niż z bilansu")
    interpretation_pl: str | None = None
    limitation_pl: str = ("„Ile opadu zostaje w glebie” to nasz szacunek z opadu, parowania, kategorii gleby i spadku terenu – progi orientacyjne; "
                          "bilans wody nie uwzględnia wód gruntowych.")
    source: str = "PIG-PIB (obszary zagrożone podtopieniami) · obliczenia własne z opadu, parowania, gleby IUNG i terenu"
    source_url: str = "https://cbdgmapa.pgi.gov.pl/"
    fetched_at: dt.datetime | None = None
    analysis_date: dt.date | None = None


class GroundwaterRequest(_M):
    """Treść POST /api/groundwater – dokładnie jedno z: `parcel_id`, para `lon` + `lat`, `geometry`."""

    parcel_id: str | None = None
    lon: float | None = None
    lat: float | None = None
    geometry: dict | None = Field(None, description="Własny obrys pola (GeoJSON Polygon, WGS84)")
    date: dt.date | None = Field(None, description="Data analizy (domyślnie dziś)")
