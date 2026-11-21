"""Kontrakt API: raport PDF (paszport wodny) i zgłoszenia stanu rowów/zbiorników – SZKIELET.

design/SPEC_UI.md 10 (raport PDF) i 11 (zgłoszenia). Odpowiednik TS: frontend/src/api/types.ts.
Bez danych osobowych (CLAUDE.md). Nic nie jest wysyłane automatycznie.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analysis import CropId


class ReportRequest(BaseModel):
    parcel_id: str
    crop: CropId
    date: dt.date


class ReportMeta(BaseModel):
    report_id: str
    parcel_id: str
    crop: CropId
    analysis_date: dt.date
    generated_at: dt.datetime
    pdf_url: str


# ── Zgłoszenia rolników (SPEC 11) ───────────────────────────────────────────────────────────

WaterObjectType = Literal["row", "ciek", "zbiornik"]
InfraProblem = Literal[
    "drozny", "zarosniety", "zamulony", "zatkany_przepust", "uszkodzona_zastawka", "uszkodzona_skarpa", "zanieczyszczony"
]
WaterLevel = Literal["brak", "niski", "normalny", "wysoki"]


class InfraReportIn(BaseModel):
    object_type: WaterObjectType
    object_id: str | None = Field(None, description="Id obiektu BDOT10k, jeśli wybrano z mapy")
    lon: float
    lat: float
    problem: InfraProblem
    water_level: WaterLevel | None = None
    description: str | None = Field(None, max_length=500)


class InfraReport(InfraReportIn):
    id: str
    created_at: dt.datetime
    confirmations: int = 0
    addressee: str = Field(description="Ciek → Wody Polskie, Nadzór Wodny; rów → właściciel gruntu lub spółka wodna")
