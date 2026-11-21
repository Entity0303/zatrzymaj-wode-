"""Przykłady do 3-minutowej oceny jury (B1) i rozgrzewka cache przy starcie (B2).

Przykład to TYLKO parametry zapytania. Wynik zawsze liczy normalne /api/analysis (run_analysis) – nie ma tu
zapisanych wyników ani rekomendacji. Rozgrzewka liczy przykłady w tle, żeby dane ze źródeł były już w cache
(pogoda: daty historyczne 7 dni, „dziś” 6 h; działki i gleby 7 dni – D44).
"""

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass
from time import perf_counter

from app.core.config import settings
from app.schemas.demo import DemoExample
from app.schemas.status import WarmupItem

log = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class Example:
    id: str
    title: str
    description: str
    parcel_id: str
    crop: str
    date: dt.date | None  # None = dziś
    previous_crop: str | None = None


EXAMPLES: tuple[Example, ...] = (
    Example("susza-2018", "Susza 2018",
            "Rekordowo sucha wiosna 2018 r. na Podlasiu: zboża ozime w pełni rozwoju, zboże po zbożu.",
            "201305_2.0038.6/1", "zboza_ozime", dt.date(2018, 6, 10), "zboza_ozime"),
    Example("mokry-rok-2021", "Mokry rok 2021",
            "Ta sama działka w lipcu 2021 r. – porównanie z suszą 2018.",
            "201305_2.0038.6/1", "zboza_ozime", dt.date(2021, 7, 15)),
    Example("kukurydza-dzis", "Kukurydza – stan dziś",
            "Kukurydza na ziarno na Lubelszczyźnie, analiza na dziś z prognozą pogody.",
            "061704_2.0011.383/2", "kukurydza_ziarno", None),
    Example("to-nie-jest-pole", "To nie jest pole",
            "Działka w Kampinosie, w większości las – aplikacja mówi wprost, że ocena suszy rolniczej nie ma zastosowania.",
            "143203_2.0027.112/11", "zboza_ozime", None),
)


def examples(today: dt.date | None = None) -> list[DemoExample]:
    today = today or dt.date.today()
    return [DemoExample(id=e.id, title=e.title, description=e.description, parcel_id=e.parcel_id, crop=e.crop,
                        date=e.date or today, previous_crop=e.previous_crop) for e in EXAMPLES]


# ── rozgrzewka (B2) ─────────────────────────────────────────────────────────────────────────

_state: dict[str, WarmupItem] = {}


def warmup_state() -> list[WarmupItem]:
    if not settings.demo_warmup:
        return [WarmupItem(id=e.id, title=e.title, state="wylaczona") for e in EXAMPLES]
    return [_state.get(e.id) or WarmupItem(id=e.id, title=e.title, state="oczekuje") for e in EXAMPLES]


async def warmup_once() -> list[WarmupItem]:
    """Liczy wszystkie przykłady po kolei przez run_analysis (wypełnia cache źródeł). Błąd = stan „blad”."""
    from app.routers.analysis import run_analysis  # import tu – unikamy cyklu przy starcie aplikacji

    t_all = perf_counter()
    for ex in examples():
        _state[ex.id] = WarmupItem(id=ex.id, title=ex.title, state="w_toku")
        t0 = perf_counter()
        try:
            await run_analysis(ex.parcel_id, ex.crop, ex.date, ex.previous_crop)
            state, error = "gotowe", None
        except Exception as exc:  # noqa: BLE001 – rozgrzewka nigdy nie wywraca aplikacji
            state, error = "blad", getattr(exc, "detail", None) or str(exc) or exc.__class__.__name__
        ms = int((perf_counter() - t0) * 1000)
        _state[ex.id] = WarmupItem(id=ex.id, title=ex.title, state=state, duration_ms=ms,
                                   finished_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0),
                                   error=None if error is None else str(error)[:300])
        log.info("Rozgrzewka: %s – %s w %d ms%s", ex.title, state, ms, f" ({error})" if error else "")
    log.info("Rozgrzewka przykładów zakończona w %.1f s", perf_counter() - t_all)
    return warmup_state()


async def warmup_loop() -> None:
    """Przy starcie i potem co `demo_warmup_interval_h` godzin (w tle – nie blokuje startu)."""
    while True:
        try:
            await warmup_once()
        except Exception:  # noqa: BLE001
            log.exception("Rozgrzewka przykładów nie powiodła się")
        await asyncio.sleep(settings.demo_warmup_interval_h * 3600)


def reset_state() -> None:
    _state.clear()
