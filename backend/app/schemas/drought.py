"""Kontrakt GET / POST /api/drought-context (A26) – tło suszowe z Europejskiego Obserwatorium Suszy (EDO, Copernicus)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CdiClass = Literal["brak", "obserwacja", "ostrzeżenie", "alarm", "regeneracja"]
SmaClass = Literal["w_normie", "sucho", "bardzo_sucho", "wilgotno"]
AgriRiskClass = Literal["brak", "niskie", "srednie", "wysokie"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Cdi(_M):
    class_: CdiClass = Field(alias="class", description="Klasa łącznego wskaźnika suszy (CDI v4.1)")
    label_pl: str = Field(description="brak suszy / obserwacja / ostrzeżenie przed suszą / alarm suszowy / regeneracja po suszy")
    date: dt.date = Field(description="Pierwszy dzień dekady, z której pochodzi wskaźnik (≤ data analizy)")
    decade_label: str = Field(description="Np. 'dekada 11–20.06.2018'")


class SoilMoistureAnomaly(_M):
    value: float | None = Field(None, description="Środek przedziału anomalii z legendy (np. −2,5 dla ≤ −2); null = brak danych")
    class_: SmaClass | None = Field(None, alias="class")
    label_pl: str = Field(description="w normie / sucho / bardzo sucho / wilgotno / brak danych")
    date: dt.date


class AgriRisk(_M):
    class_: AgriRiskClass = Field(alias="class")
    label_pl: str = Field(description="bez wskazanego ryzyka / niskie / średnie / wysokie (ryzyko skutków suszy dla rolnictwa)")
    date: dt.date


class DroughtContext(_M):
    """Tło suszowe dla okolicy działki. `unavailable = true` – usługa nie odpowiedziała (reszta pól pusta)."""

    unavailable: bool = False
    note_pl: str | None = Field(None, description="Powód braku danych – po polsku, dla rolnika")
    cdi: Cdi | None = None
    soil_moisture_anomaly: SoilMoistureAnomaly | None = None
    agri_risk: AgriRisk | None = None
    sentence: str | None = Field(None, description="Zdanie dla rolnika; z `our_status` – porównanie z naszą oceną")
    agrees: bool | None = Field(None, description="Czy tło EDO jest zgodne z naszą oceną (gdy podano our_status)")
    resolution_note: str = "Wskaźnik regionalny (siatka ok. 5–10 km) – kontekst dla okolicy, nie dla samej działki."
    source: str = "Copernicus European Drought Observatory (EDO), JRC"
    source_url: str = "https://drought.emergency.copernicus.eu/"
    fetched_at: dt.datetime | None = None
    analysis_date: dt.date | None = None


class DroughtContextRequest(_M):
    """Treść POST /api/drought-context – dokładnie jedno z: `parcel_id`, para `lon` + `lat`, `geometry`."""

    parcel_id: str | None = None
    lon: float | None = None
    lat: float | None = None
    geometry: dict | None = Field(None, description="Własny obrys pola (GeoJSON Polygon, WGS84)")
    date: dt.date | None = Field(None, description="Data analizy (domyślnie dziś)")
    our_status: str | None = Field(None, description="Nasz stopień: ok | warn | risk | danger albo nagłówek statusu")
