"""Wspólny ogranicznik zadań w tle (A23): teren i spływ, widełki rankingu, rowy i zbiorniki, zdjęcie satelitarne, SoilGrids.

Najwyżej `settings.background_workers` (BACKGROUND_WORKERS, domyślnie 2) zadań naraz w całej aplikacji – na małym
serwerze (0,5 CPU) kilka obliczeń jednocześnie spowalniało odpowiedzi głównej analizy. Gdy zadań czeka więcej niż
wolnych miejsc, startują w kolejności: teren → widełki → rowy → satelita → SoilGrids (w obrębie rodzaju – według
zgłoszenia). Duplikatów pilnują same moduły (jedno zadanie na działkę / datę – słowniki `_tasks`); tu jest tylko
kolejka, limit i jedna linia logu na start, koniec i błąd z czasem. Analiza główna nie czeka na kolejkę: gdy brak
wolnego miejsca (`busy()`), moduły z budżetem czekania (widełki, SoilGrids) od razu zwracają „w toku”.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import logging
import time
import weakref
from typing import Any, Awaitable

from app.core.config import settings

log = logging.getLogger("uvicorn.error")
PRIORITY = {"teren": 0, "widelki": 1, "rowy": 2, "satelita": 3, "soilgrids": 4}
# Zadania o niskim priorytecie zgłaszane są w analizie ułamek sekundy PRZED terenem (satelita – przed pobraniem źródeł,
# SoilGrids – razem z nimi). Krótka zwłoka przed zajęciem wolnego miejsca daje pierwszeństwo terenowi z tej samej analizy.
GRACE_S = {"satelita": 0.2, "soilgrids": 0.4}
_seq = itertools.count()
# stan na pętlę zdarzeń (testy uruchamiają wiele pętli; przyszłości nie przechodzą między pętlami)
_state: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict]" = weakref.WeakKeyDictionary()


def _st() -> dict:
    loop = asyncio.get_running_loop()
    st = _state.get(loop)
    if st is None:
        st = _state[loop] = {"running": 0, "waiting": []}
    return st


def workers() -> int:
    return max(1, int(settings.background_workers))


def busy(kind: str | None = None) -> bool:
    """Czy nowe zadanie trafiłoby do kolejki: wszystkie miejsca zajęte albo – dla rodzaju ze zwłoką startu
    (satelita, SoilGrids) – zawsze (startują po zwłoce, analiza na nie nie czeka)."""
    st = _st()
    return st["running"] >= workers() or bool(st["waiting"]) or bool(kind and GRACE_S.get(kind))


async def _acquire(kind: str) -> None:
    st = _st()
    if st["running"] < workers() and not st["waiting"]:
        st["running"] += 1
        return
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    heapq.heappush(st["waiting"], (PRIORITY.get(kind, 9), next(_seq), fut))
    try:
        await fut  # miejsce przekazane przez _release (licznik `running` już je obejmuje)
    except asyncio.CancelledError:
        if fut.done() and not fut.cancelled():  # miejsce przyznane tuż przed anulowaniem – oddaj je
            _release()
        raise


def _release() -> None:
    st = _st()
    while st["waiting"]:
        _p, _n, fut = heapq.heappop(st["waiting"])
        if not fut.done():
            fut.set_result(None)  # miejsce przechodzi na czekające zadanie o najwyższym priorytecie
            return
    st["running"] -= 1


async def run(kind: str, label: str, work: Awaitable[Any]) -> Any:
    """Wykonuje `work` (korutynę – jeszcze nieuruchomioną) w wolnym miejscu kolejki tła; loguje start, koniec, błąd."""
    t_wait = time.monotonic()
    try:
        if GRACE_S.get(kind):
            await asyncio.sleep(GRACE_S[kind])
        await _acquire(kind)
    except BaseException:
        if asyncio.iscoroutine(work):
            work.close()
        raise
    waited = time.monotonic() - t_wait
    t0 = time.monotonic()
    log.info("TŁO start %s %s (czekało %.1f s)", kind, label, waited)
    try:
        out = await work
    except asyncio.CancelledError:
        log.info("TŁO przerwane %s %s po %.1f s", kind, label, time.monotonic() - t0)
        raise
    except Exception as exc:  # noqa: BLE001 – log i dalej ten sam błąd
        log.warning("TŁO błąd %s %s po %.1f s: %s: %s", kind, label, time.monotonic() - t0, exc.__class__.__name__,
                    str(getattr(exc, "message", exc))[:160])
        raise
    else:
        log.info("TŁO koniec %s %s w %.1f s", kind, label, time.monotonic() - t0)
        return out
    finally:
        _release()


def reset() -> None:
    _state.clear()
