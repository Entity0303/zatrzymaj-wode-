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
    # A8/A13: 6 działek do pokazu – krótkie tytuły (2–3 słowa), miejscowość w opisie; analiza na dziś, zboża ozime
    Example("dobra-dzialka", "Dobra działka",
            "Wnory-Wandy (Podlasie): gleba średnia, trzyma wodę; 1/3 działki to wilgotne obniżenie – co siać i gdzie "
            "zatrzymać wodę.",
            "201305_2.0038.6/1", "zboza_ozime", None),
    Example("slaba-ziemia", "Słaba ziemia",
            "Pożarowo (Puszcza Notecka): piasek, najbardziej podatny na suszę – pszenica i rzepak odradzane, "
            "bezpieczniej żyto i łubin.",
            "302408_5.0017.70/4", "zboza_ozime", None),
    Example("stok-pogorze", "Stok na Pogórzu",
            "Bachórz (Pogórze Dynowskie): 78% działki to stok, u góry sucha górka – woda spływa i zabiera glebę.",
            "181605_2.0001.1552/2", "zboza_ozime", None),
    Example("obnizenie-pojezierze", "Obniżenie z oczkiem",
            "Muntowo (Pojezierze Mrągowskie): pagórki i obniżenia, w których zbiera się woda – gdzie zatrzymać ją na "
            "polu.",
            "281003_2.0015.79/5", "zboza_ozime", None),
    Example("susza-kujawy", "Susza na Kujawach",
            "Krusza Duchowna (k. Inowrocławia): dobra gleba w najsuchszym regionie Polski – plon ogranicza woda, nie "
            "gleba; stacja IMGW 6 km obok.",
            "040704_2.0019.57", "zboza_ozime", None),
    Example("less-drzewce", "Stok na lessie",
            "Drzewce-Kolonia (gm. Nałęczów): stok i erozja na lessie – górka i stok na 86% działki, woda spływa i "
            "zabiera glebę; pas zieleni w poprzek stoku.",
            "061408_5.0008.203", "zboza_ozime", None),
)


def examples(today: dt.date | None = None) -> list[DemoExample]:
    today = today or dt.date.today()
    return [DemoExample(id=e.id, title=e.title, description=e.description, parcel_id=e.parcel_id, crop=e.crop,
                        date=e.date or today, previous_crop=e.previous_crop) for e in EXAMPLES]


async def ready_examples() -> list[DemoExample]:
    """Przykłady, które jury może bezpiecznie kliknąć (D55). Normalnie – wszystkie. W trybie DEMO_OFFLINE – tylko te,
    które liczą się z samego cache (szybka próba run_analysis, ~0,05 s); przy otwartym bezpieczniku ULDK – tylko
    z działką znaną z cache / app/data/demo_parcels.json. Lista nigdy nie jest pusta z tego powodu (gdy nic nie
    przechodzi – wszystkie, żeby było widać komunikat zamiast pustego ekranu)."""
    from app.core.cache import breaker
    from app.routers.analysis import run_analysis  # import tu – unikamy cyklu
    from app.sources import uldk

    all_ex = examples()
    if settings.demo_offline:
        ok = []
        for e in all_ex:
            try:
                await run_analysis(e.parcel_id, e.crop, e.date, e.previous_crop)
                ok.append(e)
            except Exception:  # noqa: BLE001 – brak danych w cache = przykład ukryty
                continue
        return ok or all_ex
    if breaker(uldk.SOURCE).open:
        known = [e for e in all_ex if uldk.known_by_id(e.parcel_id) is not None]
        return known or all_ex
    return all_ex


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
