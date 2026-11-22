"""KONTRAKT: GET /api/price-weather – „Ceny i pogoda na tle lat” (A28; porównanie regionalne, nie dla działki).
Odpowiednik w frontend/src/api/types.ts: `PriceWeather`, `PriceWeatherYear`."""

from pydantic import BaseModel, Field


class PriceWeatherYear(BaseModel):
    year: int
    precip_mm: float | None = Field(None, description="Średnia suma opadów IV–IX ze stacji IMGW regionu, mm")
    price_pln_t: float | None = Field(None, description="Cena skupu GUS, zł/t (średnia roczna)")
    yield_t_ha: float | None = Field(None, description="Średni plon GUS w regionie, t/ha")
    yield_dev_pct: float | None = Field(None, description="A28b: odchylenie plonu od trendu (Theil–Sen), %")
    price_dev_pct: float | None = Field(None, description="A28b: odchylenie ceny od trendu (Theil–Sen), %")


class PriceWeather(BaseModel):
    region_label: str = Field(description="Np. 'woj. podlaskie' albo 'Polska'")
    crop_label: str
    unavailable: bool = Field(False, description="Uprawa bez cen skupu GUS – wtedy `note_pl` z powodem, puste `years`")
    years: list[PriceWeatherYear] = Field(default_factory=list, description="Lata 2013 … to_year − 1")
    dry_years: list[int] = Field(default_factory=list, description="Lata najsuchsze (dolne 25% opadów IV–IX)")
    summary_pl: str | None = Field(None, description="Wniosek z danych; null, gdy pełnych lat jest mniej niż 6")
    note_pl: str | None = None
    sources: list[str] = Field(default_factory=list)
    price_excluded_years: list[int] = Field(default_factory=list, description="A28c: lata pominięte we wniosku o CENIE "
                                            "(szok rynkowy, np. 2022); plon i wykres obejmują je normalnie")
