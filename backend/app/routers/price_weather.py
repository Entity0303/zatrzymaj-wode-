"""GET /api/price-weather – „Ceny i pogoda na tle lat” (A28): porównanie regionalne, nie dla działki."""

import datetime as dt

from fastapi import APIRouter, HTTPException, Query

from app.analysis import price_weather as PW
from app.schemas.price_weather import PriceWeather

router = APIRouter(prefix="/api", tags=["ceny i pogoda"])


@router.get("/price-weather", response_model=PriceWeather)
async def price_weather(
    region: str = Query(description="Województwo (nazwa albo kod TERYT, np. „podlaskie”, „20”) albo „PL” – cała Polska"),
    crop: str = Query(description="Kod uprawy (np. pszenica_ozima) albo produkt GUS (np. pszenica)"),
    to_year: int | None = Query(None, ge=PW.FIRST_YEAR + 1, le=2100, description="Rok daty analizy – lata 2013 … to_year − 1"),
) -> PriceWeather:
    """Dla lat 2013 … to_year − 1: cena skupu GUS (zł/t), średni plon GUS (t/ha), średnia suma opadów IV–IX ze stacji
    IMGW regionu; `summary_pl` – lata najsuchsze na tle pozostałych (gdy jest ≥ 6 pełnych lat). Uprawa bez cen GUS →
    `unavailable: true` z notą. Dane statyczne – wynik z pamięci."""
    key = PW.region_key(region)
    if key is None:
        raise HTTPException(status_code=422, detail={"message": "Podaj województwo (np. podlaskie) albo PL – całą Polskę."})
    return PriceWeather.model_validate(PW.cached(key, crop.strip(), to_year or dt.date.today().year))
