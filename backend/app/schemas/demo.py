"""GET /api/demo/examples – gotowe przykłady do 3-minutowej oceny (tylko parametry zapytania).

Wynik przykładu zawsze liczy normalne GET /api/analysis – żadnych zapisanych wyników ani rekomendacji.
"""

import datetime as dt

from pydantic import Field

from app.schemas.analysis import Contract, CropId, PreviousCropId


class DemoExample(Contract):
    id: str = Field(description="Np. 'susza-2018'")
    title: str = Field(description="Np. 'Susza 2018'")
    description: str = Field(description="Co pokazuje przykład – jedno zdanie")
    parcel_id: str
    crop: CropId
    date: dt.date = Field(description="Data analizy (dla przykładów „dziś” – bieżąca data serwera)")
    previous_crop: PreviousCropId | None = None
