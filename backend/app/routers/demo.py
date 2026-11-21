"""GET /api/demo/examples – przykłady do szybkiej oceny (tylko parametry; wynik liczy /api/analysis)."""

from fastapi import APIRouter

from app import demo
from app.schemas.demo import DemoExample

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/examples", response_model=list[DemoExample])
async def get_examples() -> list[DemoExample]:
    """4 przykłady: Susza 2018, Mokry rok 2021, Kukurydza – stan dziś, To nie jest pole.
    Każdy otwiera się normalnym zapytaniem GET /api/analysis z podanymi parametrami."""
    return demo.examples()
